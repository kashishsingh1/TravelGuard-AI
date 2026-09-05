"""PlaywrightMCPService — genuine Model Context Protocol (MCP) client and browser inspector.

Architecture:
  TravelGuard Agent / Healing Engine
            ↓
  PlaywrightMCPService
            ↓
  PlaywrightMCPClient (JSON-RPC 2.0 stdio transport)
            ↓
  Playwright MCP Server (travelguard/mcp_server.py)
            ↓
  Headless Chromium Browser
            ↓
  Target Application (SkyBook)

Provides live DOM and accessibility evidence to FailureDiagnosisEngine and SelfHealingEngine,
and allows deterministic validation of candidate locators before test patching.
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("travelguard.mcp")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"


class ElementInfo:
    """Represents a discovered UI element from browser inspection."""

    def __init__(
        self,
        tag: str,
        role: str,
        name: str,
        text: str,
        test_id: str = "",
        placeholder: str = "",
        input_type: str = "",
    ):
        self.tag = tag
        self.role = role
        self.name = name
        self.text = text
        self.test_id = test_id
        self.placeholder = placeholder
        self.input_type = input_type

    def to_playwright_locator(self) -> str:
        """Generate the most stable Playwright locator for this element."""
        # Priority: getByRole > data-testid > getByText
        if self.role in ("button", "link", "textbox", "checkbox") and self.name:
            return f"getByRole('{self.role}', {{ name: '{self.name}' }})"
        if self.test_id:
            return f"locator('[data-testid=\"{self.test_id}\"]')"
        if self.placeholder:
            return f"getByPlaceholder('{self.placeholder}')"
        if self.text:
            return f"getByText('{self.text}')"
        return f"locator('{self.tag}')"

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "role": self.role,
            "name": self.name,
            "text": self.text,
            "test_id": self.test_id,
            "placeholder": self.placeholder,
            "locator": self.to_playwright_locator(),
        }

    def __repr__(self) -> str:
        return f"ElementInfo(role={self.role!r}, name={self.name!r}, text={self.text!r})"


class BrowserInspectionResult:
    """Result of inspecting a live application page via Playwright MCP."""

    def __init__(
        self,
        available: bool,
        url: str = "",
        title: str = "",
        elements: Optional[List[ElementInfo]] = None,
        error: str = "",
        method: str = "playwright_mcp",
    ):
        self.available = available
        self.url = url
        self.title = title
        self.elements = elements or []
        self.error = error
        self.method = method

    def find_buttons(self) -> List[ElementInfo]:
        """Return all discovered button elements."""
        return [e for e in self.elements if e.tag == "button" or e.role == "button"]

    def find_by_approximate_name(self, approximate_name: str) -> List[ElementInfo]:
        """Find elements whose name or text contains approximate_name (case-insensitive)."""
        q = approximate_name.lower()
        return [
            e
            for e in self.elements
            if q in (e.name or "").lower() or q in (e.text or "").lower()
        ]

    def find_similar_to(self, old_name: str) -> List[ElementInfo]:
        """Find elements that may be semantic replacements for old_name."""
        buttons = self.find_buttons()
        direct = self.find_by_approximate_name(old_name)
        if direct:
            return direct
        return buttons

    def to_context_string(self, max_elements: int = 30) -> str:
        """Produce a compact text representation for LLM prompts."""
        if not self.available:
            return f"Browser inspection unavailable: {self.error}"
        lines = [
            f"URL: {self.url}",
            f"Page title: {self.title}",
            f"Discovered {len(self.elements)} interactive elements (showing up to {max_elements}):",
        ]
        for e in self.elements[:max_elements]:
            lines.append(
                f"  [{e.tag}] role={e.role!r} name={e.name!r} text={e.text!r}"
                + (f" data-testid={e.test_id!r}" if e.test_id else "")
            )
        return "\n".join(lines)


class PlaywrightMCPClient:
    """
    Model Context Protocol (MCP) Client for stdio JSON-RPC 2.0 communication.
    Connects to travelguard.mcp_server and executes MCP tools.
    """

    def __init__(self, server_module: str = "travelguard.mcp_server", timeout: int = 25):
        self.server_module = server_module
        self.timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._request_id = 0

    def start(self) -> None:
        """Launch the MCP server process with piped stdio."""
        if self._proc is not None and self._proc.poll() is None:
            return

        cmd = [sys.executable, "-m", self.server_module]
        env = dict(os.environ)
        # Ensure PYTHONPATH includes repo root and backend
        pypath = [str(_REPO_ROOT), str(_REPO_ROOT / "backend")]
        if "PYTHONPATH" in env:
            pypath.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pypath)

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(_REPO_ROOT),
            env=env,
        )

        # Send MCP initialize
        init_res = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "travelguard-agent", "version": "0.5.0"},
            },
        )
        logger.info(f"[MCP-Client] Connected to MCP server: {init_res.get('serverInfo', {})}")

        # Send notifications/initialized
        self._send_notification("notifications/initialized", {})

    def stop(self) -> None:
        """Terminate the MCP server process."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Query registered tools from the MCP server."""
        res = self._send_request("tools/list", {})
        return res.get("tools", [])

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke an MCP tool via tools/call."""
        res = self._send_request("tools/call", {"name": tool_name, "arguments": arguments})
        return res

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._proc or self._proc.poll() is not None:
            self.start()

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        raw_msg = json.dumps(payload) + "\n"
        assert self._proc and self._proc.stdin and self._proc.stdout
        self._proc.stdin.write(raw_msg)
        self._proc.stdin.flush()

        # Read JSON response line
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed connection without response")

        resp = json.loads(line.strip())
        if "error" in resp:
            raise RuntimeError(f"MCP Server error: {resp['error']}")
        return resp.get("result", {})

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        if not self._proc or self._proc.poll() is not None:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        raw_msg = json.dumps(payload) + "\n"
        assert self._proc.stdin
        self._proc.stdin.write(raw_msg)
        self._proc.stdin.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class PlaywrightMCPService:
    """
    High-level browser automation service for TravelGuard AI backed by genuine Playwright MCP.
    """

    def __init__(
        self,
        tests_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
        timeout_seconds: int = 30,
    ):
        self.tests_dir = tests_dir or _TESTS_DIR
        self.repo_root = repo_root or _REPO_ROOT
        self.timeout_seconds = timeout_seconds
        self._client: Optional[PlaywrightMCPClient] = None

    def _get_client(self) -> PlaywrightMCPClient:
        if self._client is None:
            self._client = PlaywrightMCPClient(timeout=self.timeout_seconds)
            self._client.start()
        return self._client

    def inspect_url(self, url: str) -> BrowserInspectionResult:
        """
        Inspect live application URL using the Playwright MCP server tool 'browser_navigate_and_inspect'.
        """
        logger.info(f"[MCP] Inspecting URL via MCP server: {url}")
        try:
            client = self._get_client()
            res = client.call_tool("browser_navigate_and_inspect", {"url": url})
            content_blocks = res.get("content", [])
            if not content_blocks:
                return BrowserInspectionResult(
                    available=False,
                    url=url,
                    error="No content returned from MCP tool",
                    method="playwright_mcp",
                )

            data_str = content_blocks[0].get("text", "{}")
            data = json.loads(data_str)

            if not data.get("success", False):
                return BrowserInspectionResult(
                    available=False,
                    url=url,
                    error=data.get("error", "Unknown browser error"),
                    method="playwright_mcp",
                )

            elements = []
            for raw in data.get("elements", []):
                elements.append(
                    ElementInfo(
                        tag=raw.get("tag", ""),
                        role=raw.get("role", ""),
                        name=raw.get("name", ""),
                        text=raw.get("text", ""),
                        test_id=raw.get("testId", ""),
                        placeholder=raw.get("placeholder", ""),
                        input_type=raw.get("type", ""),
                    )
                )

            return BrowserInspectionResult(
                available=True,
                url=data.get("url", url),
                title=data.get("title", ""),
                elements=elements,
                method="playwright_mcp",
            )
        except Exception as exc:
            logger.warning(f"[MCP] Inspection via MCP failed ({exc}).")
            return BrowserInspectionResult(
                available=False,
                url=url,
                error=str(exc),
                method="playwright_mcp_failed",
            )

    def validate_locator(self, url: str, locator: str) -> bool:
        """
        Validate whether a Playwright locator exists on the page using MCP tool 'browser_validate_locator'.
        """
        logger.info(f"[MCP] Validating locator via MCP tool: {locator}")
        try:
            client = self._get_client()
            res = client.call_tool("browser_validate_locator", {"url": url, "locator": locator})
            content_blocks = res.get("content", [])
            if not content_blocks:
                return False
            data = json.loads(content_blocks[0].get("text", "{}"))
            return bool(data.get("valid", False))
        except Exception as exc:
            logger.warning(f"[MCP] Locator validation error: {exc}")
            return False

    def close(self) -> None:
        """Stop the underlying MCP client and server process."""
        if self._client:
            self._client.stop()
            self._client = None
