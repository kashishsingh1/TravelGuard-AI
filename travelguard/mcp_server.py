"""Model Context Protocol (MCP) Server for Playwright Browser Automation.

Conforms to the Model Context Protocol (MCP) specification:
- Transport: stdio (stdin / stdout JSON-RPC 2.0)
- Protocol methods:
    * initialize: reports capabilities and server info
    * notifications/initialized: client acknowledgement
    * tools/list: registers browser automation tools
    * tools/call: executes tool calls and returns structured MCP content blocks

Registered Tools:
  - browser_navigate_and_inspect: Opens Chromium, navigates to target URL, returns accessible elements & DOM hierarchy.
  - browser_validate_locator: Validates whether a given Playwright locator exists and resolves uniquely.
  - browser_get_page_elements: Extracts all buttons, inputs, links and roles from the active page.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 stdout/stdin
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[MCP-Server] %(message)s")
logger = logging.getLogger("travelguard.mcp_server")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"


# Script executed inside Node.js to perform the Playwright browser inspection
_INSPECTION_RUNNER = """
const { chromium } = require('@playwright/test');

(async () => {
  const url = process.argv[2] || 'http://localhost:5173';
  const targetLocator = process.argv[3] || '';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(1000);

    let locatorValid = null;
    let locatorCount = 0;
    if (targetLocator) {
      try {
        const loc = eval(`page.${targetLocator}`);
        locatorCount = await loc.count();
        locatorValid = locatorCount > 0;
      } catch (e) {
        locatorValid = false;
      }
    }

    const elements = await page.evaluate(() => {
      const results = [];
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_ELEMENT,
        null
      );
      let node;
      while ((node = walker.nextNode())) {
        const tag = node.tagName.toLowerCase();
        if (!['button', 'a', 'input', 'select', 'textarea', 'label', 'h1', 'h2', 'h3'].includes(tag)) continue;
        const role = node.getAttribute('role') || tag;
        const text = (node.textContent || '').trim().substring(0, 100);
        const name = node.getAttribute('aria-label') || node.getAttribute('name') || text;
        const testId = node.getAttribute('data-testid') || '';
        const placeholder = node.getAttribute('placeholder') || '';
        const type = node.getAttribute('type') || '';
        if (text || name || testId) {
          results.push({ tag, role, name, text, testId, placeholder, type });
        }
      }
      return results;
    });

    const title = await page.title();
    console.log(JSON.stringify({
      success: true,
      title,
      url: page.url(),
      elements,
      locatorValid,
      locatorCount
    }));
  } catch (err) {
    console.log(JSON.stringify({
      success: false,
      error: err.message,
      elements: [],
      locatorValid: false
    }));
  } finally {
    await browser.close();
  }
})();
"""


def _run_browser_action(url: str, locator: str = "") -> dict:
    """Run headless Playwright browser inspection and return parsed JSON."""
    try:
        cmd = ["node", "-e", _INSPECTION_RUNNER, url, locator]
        proc = subprocess.run(
            cmd,
            cwd=str(_TESTS_DIR),
            capture_output=True,
            text=True,
            timeout=25,
            env=dict(os.environ),
        )
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        return {"success": False, "error": proc.stderr or "No JSON output from Playwright runner"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


class PlaywrightMCPServer:
    """Standard Model Context Protocol (MCP) server for Playwright browser inspection."""

    SERVER_INFO = {
        "name": "travelguard-playwright-mcp",
        "version": "1.0.0",
    }

    TOOLS = [
        {
            "name": "browser_navigate_and_inspect",
            "description": "Navigate to an application URL and inspect the live DOM and accessible elements.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL to inspect (e.g. http://localhost:5173)",
                    }
                },
                "required": ["url"],
            },
        },
        {
            "name": "browser_validate_locator",
            "description": "Validate whether a candidate Playwright locator exists and is resolvable on the page.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target page URL"},
                    "locator": {
                        "type": "string",
                        "description": "Playwright locator expression (e.g., getByRole('button', { name: 'Reserve Flight' }))",
                    },
                },
                "required": ["url", "locator"],
            },
        },
        {
            "name": "browser_get_page_elements",
            "description": "Extract all interactive elements (buttons, inputs, links) from the current page.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Page URL to query"},
                },
                "required": ["url"],
            },
        },
    ]

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming MCP JSON-RPC 2.0 request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": self.SERVER_INFO,
                },
            }

        elif method == "notifications/initialized":
            logger.info("Client acknowledged initialized")
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.TOOLS},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return self._execute_tool(req_id, tool_name, arguments)

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def _execute_tool(self, req_id: Any, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        url = args.get("url", "http://localhost:5173")
        locator = args.get("locator", "")

        if name == "browser_navigate_and_inspect":
            data = _run_browser_action(url=url)
            text_result = json.dumps(data)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text_result}],
                    "isError": not data.get("success", False),
                },
            }

        elif name == "browser_validate_locator":
            data = _run_browser_action(url=url, locator=locator)
            text_result = json.dumps({
                "valid": data.get("locatorValid", False),
                "count": data.get("locatorCount", 0),
                "locator": locator,
            })
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text_result}],
                    "isError": False,
                },
            }

        elif name == "browser_get_page_elements":
            data = _run_browser_action(url=url)
            elements = data.get("elements", [])
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"elements": elements})}],
                    "isError": not data.get("success", False),
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": f"Unknown tool: {name}"},
        }

    def run_stdio_server(self) -> None:
        """Run standard stdio JSON-RPC loop."""
        logger.info("Starting Playwright MCP stdio server...")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                logger.error(f"Error handling request: {exc}")


if __name__ == "__main__":
    server = PlaywrightMCPServer()
    server.run_stdio_server()
