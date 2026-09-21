"""Standard-library coordination of installers and live plugin sessions."""
from __future__ import annotations
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import uuid
import time
import threading


class MaintenanceBusy(RuntimeError):
    pass


def state_dir() -> Path:
    # Store-app virtualization can give Codex a different LOCALAPPDATA from the
    # installer. USERPROFILE/Path.home gives both processes the same lock/policy.
    return Path(os.environ.get('SDA_MAINTENANCE_DIR') or
                str(Path.home() / '.systematic-document-analysis' / 'maintenance'))


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _file_lock(name, *, shared=False):
    """Sessions share an OS lock; installation requires exclusive access.

    Locks are released on process exit, including crashes. All installations
    for the user share this gate; no PID guessing or stale file removal.
    """
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open('a+b') as stream:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt

            class Overlapped(ctypes.Structure):
                _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                            ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                            ('hEvent', wintypes.HANDLE)]

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            lock = kernel.LockFileEx
            lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            lock.restype = wintypes.BOOL
            unlock = kernel.UnlockFileEx
            unlock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.POINTER(Overlapped)]
            unlock.restype = wintypes.BOOL
            handle = msvcrt.get_osfhandle(stream.fileno())
            overlap = Overlapped()
            if not lock(handle, 1 | (0 if shared else 2), 0, 1, 0, ctypes.byref(overlap)):
                raise MaintenanceBusy('Close other plugin sessions and retry; setup or a session is active.')
            try:
                yield
            finally:
                unlock(handle, 0, 1, 0, ctypes.byref(overlap))
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except OSError as exc:
                raise MaintenanceBusy('Close other plugin sessions and retry; setup or a session is active.') from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def update_pending() -> bool:
    """An OS-held intent lock is the request; a crashed installer leaves none."""
    try:
        with _file_lock('update.lock', shared=True):
            return False
    except MaintenanceBusy:
        return True


_draining = threading.Event()


def draining() -> bool:
    return _draining.is_set()


def request_drain() -> None:
    _draining.set()


@contextmanager
def maintenance_lock(*, shared=False):
    if shared and update_pending():
        raise MaintenanceBusy('An update is in progress. Start a new conversation after installation finishes.')
    with _file_lock('sessions.lock', shared=shared):
        # Close the race with an installer that requested shutdown during entry.
        if shared and update_pending():
            raise MaintenanceBusy('An update is in progress. Start a new conversation after installation finishes.')
        yield


@contextmanager
def installation_lock(*, wait_seconds=60, notify=None):
    """Drain cooperating sessions, then hold exclusive access for installation.

    This never kills processes. Older sessions time out with manual instructions.
    The separate intent lock excludes competing installers and reconnects.
    """
    with _file_lock('update.lock'):
        deadline = time.monotonic() + wait_seconds
        announced = False
        with ExitStack() as stack:
            while True:
                try:
                    stack.enter_context(maintenance_lock())
                    break
                except MaintenanceBusy as exc:
                    if not announced and notify:
                        notify('Closing plugin connections; waiting for current work to be saved. '
                               'No new documents will start. The host apps stay open.')
                        announced = True
                    if time.monotonic() >= deadline:
                        raise MaintenanceBusy(
                            'Plugin connections have not closed; no installation files changed. '
                            'Let current work finish and retry. Sessions from 0.8.4 or earlier '
                            'cannot close automatically: close their plugin connections, or fully '
                            'exit Claude Code and Codex once, then rerun installer.cmd. '
                            'No processes were forcibly terminated.') from exc
                    time.sleep(min(0.2, max(0, deadline-time.monotonic())))
            yield


def packaged_process() -> bool:
    """True inside a packaged (MSIX/Store) app such as the Codex desktop app.

    Such processes have file-system virtualization: writes below LOCALAPPDATA
    land in the package's LocalCache and later mask the real files. Installers
    and updaters must not run there.
    """
    if os.name != 'nt':
        return False
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    length = ctypes.c_uint32(0)
    result = kernel.GetCurrentPackageFullName(ctypes.byref(length), None)
    return result != 15700  # APPMODEL_ERROR_NO_PACKAGE


PACKAGED_MESSAGE = ('This command runs inside the Codex desktop app, where files written below %LOCALAPPDATA% are '
                    'redirected into the app\'s LocalCache and would mask the real installation. Run installer.cmd or '
                    'update.cmd by double-clicking it in Explorer or from a normal terminal. No files changed.')


def update_status() -> dict:
    """Cached diagnostics only; no network or credentials."""
    try:
        settings = read_json(state_dir() / 'updates.json')
        status = read_json(state_dir() / 'last-check.json')
        return {'mode': settings.get('mode', 'notify'), **status}
    except (OSError, ValueError):
        return {'mode': 'unknown', 'message': 'Update settings could not be read. Run update.cmd.'}
