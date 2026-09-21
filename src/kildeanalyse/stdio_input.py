"""Cancellable pipe input: the MCP SDK's blocking Windows readline cannot drain.

Only the stdio transport reads this descriptor. Poll for available bytes before
reading; cancellation never abandons a thread holding a buffered stdin lock.
"""
import os
import sys

import anyio


class PipeInput:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            self.ctypes = ctypes
            self.handle = msvcrt.get_osfhandle(self.fd)
            self.available = wintypes.DWORD()
            self.peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
            self.peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                 wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            self.peek.restype = wintypes.BOOL

    def _read(self):
        if os.name == 'nt':
            if not self.peek(self.handle, None, 0, None, self.ctypes.byref(self.available), None):
                error = self.ctypes.get_last_error()
                if error in (109, 232):  # broken/closing pipe: client EOF
                    return b''
                raise OSError(error, 'Unable to read MCP stdin pipe')
            if not self.available.value:
                return None
            count = min(65536, self.available.value)
        else:
            import select
            if not select.select([self.fd], [], [], 0)[0]:
                return None
            count = 65536
        return os.read(self.fd, count)

    async def __aiter__(self):
        buffer = bytearray()
        while True:
            chunk = self._read()
            if chunk is None:
                await anyio.sleep(0.05)
                continue
            if not chunk:
                if buffer:
                    yield buffer.decode('utf-8', errors='replace')
                return
            buffer.extend(chunk)
            while (end := buffer.find(b'\n')) >= 0:
                line = bytes(buffer[:end+1])
                del buffer[:end+1]
                yield line.decode('utf-8', errors='replace')
            await anyio.sleep(0)
