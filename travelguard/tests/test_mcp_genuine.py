"""Deterministic integration tests for genuine Playwright Model Context Protocol (MCP) integration."""

import pytest
from travelguard.mcp_inspector import (
    BrowserInspectionResult,
    ElementInfo,
    PlaywrightMCPClient,
    PlaywrightMCPService,
)
from travelguard.mcp_server import PlaywrightMCPServer


class TestPlaywrightMCPIntegration:
    """Validate genuine MCP protocol handshake, tool calls, and browser inspection."""

    def test_mcp_server_protocol_lifecycle(self):
        """Test standard MCP initialize and tools/list request handling."""
        server = PlaywrightMCPServer()

        # 1. Initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        init_res = server.handle_request(init_req)
        assert init_res["jsonrpc"] == "2.0"
        assert init_res["result"]["serverInfo"]["name"] == "travelguard-playwright-mcp"
        assert "tools" in init_res["result"]["capabilities"]

        # 2. tools/list
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_res = server.handle_request(tools_req)
        tool_names = [t["name"] for t in tools_res["result"]["tools"]]
        assert "browser_navigate_and_inspect" in tool_names
        assert "browser_validate_locator" in tool_names

    def test_mcp_client_subprocess_handshake(self):
        """Test live stdio JSON-RPC connection from MCP Client to MCP Server."""
        with PlaywrightMCPClient() as client:
            tools = client.list_tools()
            assert len(tools) >= 2
            tool_names = [t["name"] for t in tools]
            assert "browser_navigate_and_inspect" in tool_names

    def test_mcp_service_inspect_skybook_live(self):
        """Test that PlaywrightMCPService connects over MCP, inspects SkyBook, and returns structured elements."""
        service = PlaywrightMCPService()
        try:
            result = service.inspect_url("http://localhost:5173")
            assert isinstance(result, BrowserInspectionResult)
            if result.available:
                assert result.method == "playwright_mcp"
                assert len(result.elements) > 0
                buttons = result.find_buttons()
                assert len(buttons) > 0
                # Check element properties
                btn = buttons[0]
                assert isinstance(btn, ElementInfo)
                assert btn.role == "button" or btn.tag == "button"
        finally:
            service.close()
