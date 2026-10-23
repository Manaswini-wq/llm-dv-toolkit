"""MCP Server for Design Verification tools.

Implements the Model Context Protocol (MCP) to expose DV verification
tools (coverage queries, regression status, waveform analysis) to LLM agents.

Protocol: JSON-RPC 2.0 over stdio transport.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from llm_dv_toolkit.mcp_server.tools.coverage_tool import CoverageTool
from llm_dv_toolkit.mcp_server.tools.regression_tool import RegressionTool
from llm_dv_toolkit.mcp_server.tools.waveform_tool import WaveformTool
from llm_dv_toolkit.mcp_server.resources.testplan_resource import TestPlanResource
from llm_dv_toolkit.utils.config import Config


class MCPServer:
    """MCP Server implementing JSON-RPC 2.0 protocol over stdio."""

    SERVER_NAME = "dv-verification-toolkit"
    SERVER_VERSION = "1.0.0"
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.coverage_tool = CoverageTool(config.coverage_db_path)
        self.regression_tool = RegressionTool(config.regression_dir)
        self.waveform_tool = WaveformTool()
        self.testplan_resource = TestPlanResource(config.project_root)

        self._tools: dict[str, dict[str, Any]] = {
            "query_coverage": {
                "description": "Query functional coverage data by group name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_name": {"type": "string", "description": "Coverage group name (empty for all)"},
                        "threshold": {"type": "number", "description": "Minimum coverage % to filter"},
                    },
                },
                "handler": self.coverage_tool.query_coverage,
            },
            "get_coverage_holes": {
                "description": "Find uncovered bins (0 hits) across all coverage groups",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.coverage_tool.get_holes,
            },
            "get_regression_status": {
                "description": "Get current regression pass/fail summary",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.regression_tool.get_status,
            },
            "get_failing_tests": {
                "description": "List all failing tests with error details",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.regression_tool.get_failing_tests,
            },
            "get_test_history": {
                "description": "Get pass/fail history for a specific test",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test_name": {"type": "string", "description": "Name of the test"},
                    },
                    "required": ["test_name"],
                },
                "handler": self.regression_tool.get_test_history,
            },
            "get_signal_values": {
                "description": "Extract signal values from VCD waveform file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "vcd_path": {"type": "string"},
                        "signal_path": {"type": "string"},
                        "start_time": {"type": "integer"},
                        "end_time": {"type": "integer"},
                    },
                    "required": ["vcd_path", "signal_path"],
                },
                "handler": self.waveform_tool.get_signal_values,
            },
            "find_signal_transitions": {
                "description": "Find times when a signal transitions to a specific value",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "vcd_path": {"type": "string"},
                        "signal_path": {"type": "string"},
                        "target_value": {"type": "string"},
                    },
                    "required": ["vcd_path", "signal_path", "target_value"],
                },
                "handler": self.waveform_tool.find_transitions,
            },
        }

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                    },
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION,
                    },
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {"name": name, "description": t["description"], "inputSchema": t["inputSchema"]}
                        for name, t in self._tools.items()
                    ]
                }
            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                if tool_name not in self._tools:
                    raise ValueError(f"Unknown tool: {tool_name}")
                handler = self._tools[tool_name]["handler"]
                tool_result = await handler(**args) if asyncio.iscoroutinefunction(handler) else handler(**args)
                result = {"content": [{"type": "text", "text": json.dumps(tool_result, indent=2, default=str)}]}
            elif method == "resources/list":
                result = {"resources": self.testplan_resource.list_resources()}
            elif method == "resources/read":
                uri = params.get("uri", "")
                result = {"contents": [self.testplan_resource.read_resource(uri)]}
            elif method == "notifications/initialized":
                return {}  # No response for notifications
            elif method == "ping":
                result = {}
            else:
                raise ValueError(f"Unknown method: {method}")

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            }

    async def run_stdio(self) -> None:
        """Run server on stdio transport (for MCP integration)."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                header = await reader.readline()
                if not header:
                    break
                # Read Content-Length header
                content_length = 0
                while header.strip():
                    if header.startswith(b"Content-Length:"):
                        content_length = int(header.split(b":")[1].strip())
                    header = await reader.readline()

                if content_length > 0:
                    body = await reader.readexactly(content_length)
                else:
                    body = await reader.readline()

                if not body:
                    break

                request = json.loads(body.decode())
                response = await self.handle_request(request)

                if response:
                    response_bytes = json.dumps(response).encode()
                    out = f"Content-Length: {len(response_bytes)}\r\n\r\n".encode() + response_bytes
                    writer.write(out)
                    await writer.drain()

            except (json.JSONDecodeError, asyncio.IncompleteReadError):
                continue
            except Exception:
                break


def main() -> None:
    """Entry point for MCP server."""
    config = Config.from_env()
    server = MCPServer(config)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
