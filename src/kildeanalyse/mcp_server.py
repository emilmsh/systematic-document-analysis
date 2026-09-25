"""Felles MCP-server for ChatGPT desktop/Codex og Claude Code.

Verktøyene returnerer lesbar tekst. Kjørekomponenten håndhever reglene; vertsappene
kan ikke skrive direkte til lagringen gjennom disse verktøyene.
"""
from __future__ import annotations

import sys
import anyio

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.stdio import stdio_server

from . import VERSJON, tjeneste
from .konfig import datamappe
from .lager import Lager
from .maintenance import maintenance_lock, update_pending, request_drain, draining
from .stdio_input import PipeInput


class UpdatingMCPServer(MCPServer):
    """Finish active tool calls and workers before closing the plugin connection."""
    active_calls = 0

    async def call_tool(self, name, arguments, context=None):
        if draining() or update_pending():
            request_drain()
            raise ToolError('Plugin update in progress. Start a new conversation after installation finishes.')
        self.active_calls += 1
        try:
            return await super().call_tool(name, arguments, context)
        finally:
            self.active_calls -= 1

    async def run_stdio_async(self):
        # Also protect direct `python -m ...` launches, not only start_server.py.
        with maintenance_lock(shared=True):
            async with anyio.create_task_group() as group:
                async def watch_update():
                    while True:
                        if update_pending():
                            request_drain()
                        if draining() and not self.active_calls and not any(
                                worker.is_alive() for worker in list(tjeneste._traader.values())):
                            print('[Systematic Document Analysis] Connection closed for update. '
                                  'Start a new conversation after installation.', file=sys.stderr, flush=True)
                            group.cancel_scope.cancel()
                            return
                        await anyio.sleep(0.2)
                group.start_soon(watch_update)
                try:
                    async with stdio_server(stdin=PipeInput()) as (reader, writer):
                        await self._lowlevel_server.run(reader, writer,
                            self._lowlevel_server.create_initialization_options())
                finally:
                    group.cancel_scope.cancel()


server = UpdatingMCPServer(
    name='systematic-document-analysis', version=VERSJON,
    instructions='Repeat one agreed task independently over selected files using CLI/API workers. '
                 'Use the systematic-document-analysis skill for the workflow. '
                 'Tool results describe recorded execution; never fabricate approvals, results or reviews.'
)

def _lager():
    return Lager(datamappe())

from .english_tools import register
register(server, _lager)


def main() -> None:
    # stdio-transport: stdout er reservert for protokollen; all logging går til stderr.
    print(f"kildeanalyse MCP-server {VERSJON} starter (datamappe {datamappe()})", file=sys.stderr, flush=True)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
