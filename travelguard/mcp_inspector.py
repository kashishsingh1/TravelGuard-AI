"""PlaywrightMCPService — real browser inspection for locator discovery and UI state.

Uses Playwright's Node.js subprocess to navigate to the target application URL and
inspect the live DOM/accessibility tree. Provides evidence for the diagnosis engine
to reason about locator drift vs. real application defects.

Architecture:
  TravelGuard Agent
        ↓
  PlaywrightMCPService
        ↓
  Running SkyBook (browser via npx playwright)
        ↓
  Observed UI (accessible elements, roles, names)
        ↓
  AI reasoning (diagnosis engine)
"""

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("travelguard.mcp")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"

# Playwright inspection script template — run inside npx playwright
_INSPECTION_SCRIPT = """
const {{ chromium }} = require('@playwright/test');

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage();
  try {{
    await page.goto('{url}', {{ waitUntil: 'domcontentloaded', timeout: 15000 }});
    await page.waitForTimeout(1500);

    const elements = await page.evaluate(() => {{
      const results = [];
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_ELEMENT,
        null
      );
      let node;
      while ((node = walker.nextNode())) {{
        const tag = node.tagName.toLowerCase();
        if (!['button', 'a', 'input', 'select', 'textarea', 'label', 'h1', 'h2', 'h3'].includes(tag)) continue;
        const role = node.getAttribute('role') || tag;
        const text = (node.textContent || '').trim().substring(0, 100);
        const name = node.getAttribute('aria-label') || node.getAttribute('name') || text;
        const testId = node.getAttribute('data-testid') || '';
        const placeholder = node.getAttribute('placeholder') || '';
        const type = node.getAttribute('type') || '';
        if (text || name || testId) {{
          results.push({{ tag, role, name, text, testId, placeholder, type }});
        }}
      }}
      return results;
    }});

    const title = await page.title();
    const url = page.url();
    console.log(JSON.stringify({{ success: true, title, url, elements }}));
  }} catch (err) {{
    console.log(JSON.stringify({{ success: false, error: err.message, elements: [] }}));
  }} finally {{
    await browser.close();
  }}
}})();
"""


class ElementInfo:
    """Represents a discovered UI element from browser inspection."""

    def __init__(self, tag: str, role: str, name: str, text: str,
                 test_id: str = "", placeholder: str = "", input_type: str = ""):
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
        method: str = "playwright_subprocess",
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
            e for e in self.elements
            if q in (e.name or "").lower() or q in (e.text or "").lower()
        ]

    def find_similar_to(self, old_name: str) -> List[ElementInfo]:
        """
        Find elements that may be semantic replacements for old_name.
        Looks for elements with similar roles (button, link) where the name changed.
        """
        buttons = self.find_buttons()
        # Direct substring match
        direct = self.find_by_approximate_name(old_name)
        if direct:
            return direct
        # Return all buttons as candidates (the LLM will reason about semantics)
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


class PlaywrightMCPService:
    """
    Browser inspection service using Playwright as an MCP-compatible agent tool.

    Navigates to the target application URL and inspects the live DOM/accessibility
    tree to provide real UI state as evidence for failure diagnosis.

    This is NOT a fake wrapper. It runs a real Playwright browser instance
    and returns actual DOM element information.
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

    def _is_playwright_available(self) -> bool:
        """Check whether npx playwright is callable in the tests directory."""
        try:
            result = subprocess.run(
                ["npx", "playwright", "--version"],
                cwd=str(self.tests_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def inspect_url(self, url: str) -> BrowserInspectionResult:
        """
        Navigate to a URL and return all discovered interactive elements.
        Provides genuine browser state as evidence for the diagnosis engine.
        """
        logger.info(f"[MCP] Inspecting URL: {url}")

        if not self._is_playwright_available():
            logger.warning("[MCP] Playwright not available — browser inspection skipped")
            return BrowserInspectionResult(
                available=False,
                url=url,
                error="Playwright not available in this environment",
                method="unavailable",
            )

        # Write the inspection script to a temp file
        script_content = _INSPECTION_SCRIPT.format(url=url)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(script_content)
            script_path = tmp.name

        try:
            env = dict(os.environ)
            result = subprocess.run(
                ["node", script_path],
                cwd=str(self.tests_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
            raw_output = result.stdout.strip()

            if not raw_output:
                logger.warning(f"[MCP] Empty output from browser script. stderr: {result.stderr[:500]}")
                return BrowserInspectionResult(
                    available=False,
                    url=url,
                    error=result.stderr[:500] or "Empty browser output",
                )

            # Find the last line that looks like JSON
            json_line = None
            for line in reversed(raw_output.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    json_line = line
                    break

            if not json_line:
                logger.warning("[MCP] No JSON output found from browser script")
                return BrowserInspectionResult(
                    available=False,
                    url=url,
                    error="No JSON output from browser inspection",
                )

            data = json.loads(json_line)

            if not data.get("success"):
                logger.warning(f"[MCP] Browser inspection failed: {data.get('error')}")
                return BrowserInspectionResult(
                    available=False,
                    url=url,
                    error=data.get("error", "Browser reported failure"),
                )

            elements = []
            for e in data.get("elements", []):
                elements.append(ElementInfo(
                    tag=e.get("tag", ""),
                    role=e.get("role", ""),
                    name=e.get("name", ""),
                    text=e.get("text", ""),
                    test_id=e.get("testId", ""),
                    placeholder=e.get("placeholder", ""),
                    input_type=e.get("type", ""),
                ))

            logger.info(f"[MCP] Found {len(elements)} elements on {url}")
            return BrowserInspectionResult(
                available=True,
                url=data.get("url", url),
                title=data.get("title", ""),
                elements=elements,
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"[MCP] Browser inspection timed out after {self.timeout_seconds}s")
            return BrowserInspectionResult(
                available=False,
                url=url,
                error=f"Browser inspection timed out after {self.timeout_seconds}s",
            )
        except json.JSONDecodeError as jde:
            logger.warning(f"[MCP] JSON parse error from browser script: {jde}")
            return BrowserInspectionResult(
                available=False,
                url=url,
                error=f"JSON parse error: {jde}",
            )
        except Exception as exc:
            logger.warning(f"[MCP] Unexpected error during browser inspection: {exc}")
            return BrowserInspectionResult(
                available=False,
                url=url,
                error=str(exc),
            )
        finally:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass

    def find_replacement_for_locator(
        self,
        url: str,
        broken_locator: str,
        old_name: str,
    ) -> Optional[ElementInfo]:
        """
        Inspect the running application to find the current element that
        corresponds to a broken locator.

        Example:
          broken_locator = "getByRole('button', { name: 'Book Flight' })"
          old_name = "Book Flight"
          → discovers button "Reserve Flight" → returns ElementInfo
        """
        inspection = self.inspect_url(url)
        if not inspection.available:
            return None

        candidates = inspection.find_similar_to(old_name)
        if candidates:
            # Prefer button/link candidates
            button_candidates = [c for c in candidates if c.tag in ("button", "a")]
            if button_candidates:
                return button_candidates[0]
            return candidates[0]

        # Fallback: return first button found
        buttons = inspection.find_buttons()
        if buttons:
            return buttons[0]

        return None
