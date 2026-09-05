# TravelGuard AI — Increment 4 Architecture & Design Document
## Autonomous Test Execution, Failure Diagnosis & Self-Healing

---

### 1. Overview & Vision
Increment 4 marks a fundamental milestone in **TravelGuard AI**:
- **From**: *"I selected which tests to run and generated candidates."*
- **To**: *"I run the selected tests, detect failures, inspect runtime DOM state using browser tools, accurately distinguish between **Test Drift**, **Product Defect**, and **Environment Failure**, self-heal brittle locators with confidence-gated patches, re-validate fixes, and produce an executive Quality Report."*

TravelGuard acts as an **Autonomous Quality Engineer** that closes the loop from code change to verified fix without human bottleneck.

```
┌─────────────────┐
│ Code Git Change │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Test Selection  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Autonomous Test Runner  │
└────────┬────────────────┘
         │
    [Test Passes?] ──► YES ──► [Healthy Quality Report]
         │ NO
         ▼
┌─────────────────────────┐
│   Failure Normalizer    │ (Extracts trace, stack, DOM, screenshot)
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ MCP Browser Inspector   │ (Queries runtime DOM & element accessibility)
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Failure Diagnosis Engine│ (Categorizes: DRIFT vs DEFECT vs ENV)
└────────┬────────────────┘
         │
    ┌────┴───────────────────────────┐
    │                                │
    ▼                                ▼
[TEST_DRIFT]                  [PRODUCT_DEFECT / ENV_FAILURE]
    │                                │
    ▼                                ▼
[Confidence >= 0.70?]         [Never Modify Test]
    │                                │
    ▼ YES                            ▼
[Self-Healing Engine]         [Flag Bug / Blocked State]
    │ (Backup & Patch locator)       │
    ▼                                ▼
[Re-validation Run]           [Executive Quality Report]
    │                                │
    ▼                                ▼
[Quality Report (HEALED)]     [Actionable Incident Report]
```

---

### 2. Failure Taxonomy & Classification Rules

A critical requirement of an autonomous QA system is **never "healing" a real product bug** (which masks production regressions) and **never blaming the application for infrastructure outages**.

| Classification | Meaning | Self-Healing Action | Production Impact |
|---|---|---|---|
| **`TEST_DRIFT`** | The application code changed intentionally (e.g. data-testid updated, CSS class renamed, layout shifted), but the test still uses stale locators or expectations. | **YES** (with backup, patch, and re-validation if confidence >= 0.70). | Test suite maintenance automated; zero false alerts. |
| **`PRODUCT_DEFECT`** | The application code has broken functional logic, returns HTTP 500/422, violates API schemas, or fails legitimate business invariants. | **STRICTLY FORBIDDEN**. Must preserve test failure and file bug report. | Regression caught before production deployment. |
| **`ENVIRONMENT_FAILURE`** | Downstream dependency offline, port refused (`ECONNREFUSED`), timeout before app start, DNS failure, 502/503 Bad Gateway. | **NO**. Deterministic classification without wasting LLM tokens. | Infrastructure alerts raised; pipeline safely marked `BLOCKED`. |

---

### 3. Architecture & Core Components

#### 3.1 Data Models (`travelguard/models.py`)
- `FailureClassification`: `TEST_DRIFT`, `PRODUCT_DEFECT`, `ENVIRONMENT_FAILURE`.
- `HealingStatus`: `HEALED`, `PROPOSED`, `UNABLE_TO_HEAL`, `NOT_APPLICABLE`, `HUMAN_REVIEW_REQUIRED`.
- `QualityStatus`: `HEALTHY`, `NEEDS_ATTENTION`, `DEGRADED`, `BLOCKED`.
- `HealingMode`: `APPLY`, `PROPOSE_ONLY`, `DRY_RUN`.
- `TestFailureInfo`: Structured container with error message, stack trace, locator attempted, expected vs actual values, page URL, DOM snippet, and screenshot path.
- `DiagnosisResult`: Root cause analysis, classification, evidence list, confidence score (0.0–1.0), and proposed remedy.
- `RepairProposal`: Original code snippet, replacement code snippet, target file path, and explanation.
- `HealingResult`: Status, patch applied flag, backup file path, validation result, and error details.
- `AutonomousRunResult`: Complete run record including selected tests, execution results, diagnoses, healing results, and final quality report.

#### 3.2 Execution Engine (`travelguard/execution_engine.py`)
- Dual-mode execution:
  1. **Live Subprocess Runner**: Spawns Playwright test runner (`npx playwright test ...`) or Pytest (`pytest backend/...`), capturing stdout, stderr, exit code, execution duration, and trace artifacts.
  2. **Deterministic Demo Runner**: Provides robust, reproducible demo fixtures for hackathon demonstrations without requiring active browsers or external services.

#### 3.3 Failure Normalizer (`travelguard/failure_normalizer.py`)
- Parses raw Playwright / Pytest outputs, stack traces, and failure messages into structured `TestFailureInfo`.
- Automatically extracts:
  - Missing locators (e.g., `locator('#book-flight-btn')` or `data-testid="submit"`).
  - Timeout errors (`waiting for locator... to be visible`).
  - Assertion mismatches (`Expected: 200, Received: 500`).
  - Associated source file and failing line number.

#### 3.4 MCP Browser Inspector (`travelguard/mcp_inspector.py`)
- Implements Model Context Protocol (MCP) browser inspection primitives:
  - `inspect_page(url)`: Retrieves active DOM hierarchy, metadata, and accessibility tree.
  - `get_element_state(selector)`: Checks element visibility, enabled state, bounding box, and text content.
  - `capture_snapshot()`: Captures current DOM snapshot to locate candidate replacement locators.
- Enables the diagnosis engine to correlate what the test expected versus what the DOM actually renders.

#### 3.5 Failure Diagnosis Engine (`travelguard/diagnosis_engine.py`)
- **Fast Deterministic Path**:
  - Immediately flags connection errors (`ECONNREFUSED`, `ERR_CONNECTION_REFUSED`, `502 Bad Gateway`) as `ENVIRONMENT_FAILURE` with 1.0 confidence, bypassing LLM calls.
- **LLM Multi-Tier Reasoning**:
  - Leverages Groq (`openai/gpt-oss-120b`) with failover to OpenRouter and Gemini.
  - Passes the Git diff, failure stack trace, failing test source, and MCP DOM snapshot.
  - Enforces strict JSON output containing classification, root cause, evidence points, and confidence score.
- **Heuristic Fallback**:
  - If all LLM providers are unavailable, evaluates regex rules over DOM and diff to maintain pipeline resilience.

#### 3.6 Self-Healing Engine (`travelguard/healing_engine.py`)
- Safety-first repair engine:
  - **Safety Gate**: Verifies `classification == TEST_DRIFT` and `confidence >= 0.70`. Rejects healing for defects and environment errors.
  - **Backup Guarantee**: Creates a `.bak` copy of the target test file before modifying code.
  - **Modes**:
    - `APPLY`: Modifies the test file, replaces the brittle locator with the healed locator, and triggers a re-validation test.
    - `PROPOSE_ONLY`: Emits code diff for human QA review without altering files on disk.
  - **Re-Validation**: Re-runs the test through `ExecutionEngine`. If the test passes, status becomes `HEALED`; otherwise reverts from backup and sets `HUMAN_REVIEW_REQUIRED`.

#### 3.7 Autonomous Pipeline Orchestrator (`travelguard/autonomous_pipeline.py`)
- Coordinates the complete autonomous lifecycle:
  1. Detects Git changes & performs Impact Analysis.
  2. Selects high-priority test suites.
  3. Executes tests via `ExecutionEngine`.
  4. Collects and normalizes any failures.
  5. Inspects application state via `MCPInspector`.
  6. Diagnoses failures via `FailureDiagnosisEngine`.
  7. Attempts self-healing via `SelfHealingEngine`.
  8. Computes aggregate `QualityStatus` (`HEALTHY`, `NEEDS_ATTENTION`, `DEGRADED`, `BLOCKED`).
  9. Persists JSON and Markdown reports to `artifacts/`.

---

### 4. Deterministic Demo Scenarios

Increment 4 includes 3 turnkey demo scenarios executable via CLI:

#### Scenario 1: UI Locator Drift (Self-Healing in Action)
- **Problem**: UI button changed from `#book-flight-btn` to `#complete-booking-btn`.
- **Test Fails**: Playwright times out waiting for `#book-flight-btn`.
- **Diagnosis**: `TEST_DRIFT` (Confidence: 0.94).
- **Self-Healing**: Locates new button in DOM, creates backup, patches test to `#complete-booking-btn`, re-runs test → **HEALED**.
- **Exit Code**: `0` (Success).

```bash
python -m travelguard autonomous-demo --demo booking-ui-drift --mock-llm
```

#### Scenario 2: Product Defect (Safety Gate Prevents Bad Patches)
- **Problem**: Backend API returns `500 Internal Server Error` due to a regression in `booking.py`.
- **Test Fails**: Status code assertion failed (`Expected 200, received 500`).
- **Diagnosis**: `PRODUCT_DEFECT` (Confidence: 0.96).
- **Self-Healing**: **ABORTED**. Self-healing engine refuses to modify test.
- **Quality Status**: `DEGRADED`.
- **Exit Code**: `2` (Defect detected).

```bash
python -m travelguard autonomous-demo --demo booking-api-defect --mock-llm
```

#### Scenario 3: Environment Failure (Zero-Token Deterministic Filter)
- **Problem**: FastAPI backend service is down (`ECONNREFUSED 127.0.0.1:8000`).
- **Diagnosis**: `ENVIRONMENT_FAILURE` (Confidence: 1.00, 0 tokens used).
- **Self-Healing**: Skipped.
- **Quality Status**: `BLOCKED`.
- **Exit Code**: `3` (Environment failure).

```bash
python -m travelguard autonomous-demo --demo environment-failure --mock-llm
```

---

### 5. CLI Reference

```bash
# Run autonomous pipeline on current git workspace
python -m travelguard autonomous-run

# Run autonomous pipeline in propose-only mode (safe preview)
python -m travelguard autonomous-run --healing-mode PROPOSE_ONLY

# Run hackathon demo scenarios
python -m travelguard autonomous-demo --demo booking-ui-drift
python -m travelguard autonomous-demo --demo booking-api-defect
python -m travelguard autonomous-demo --demo environment-failure

# Inspect test inventory
python -m travelguard test-inventory
```

---

### 6. Test Suite & Validation

The test suite covers all units and integrations with zero external network dependencies:

```bash
python -m pytest travelguard/tests/ -v
```

**Results**:
- `test_execution_engine.py`: 10 passed
- `test_failure_normalizer.py`: 11 passed
- `test_diagnosis_engine.py`: 12 passed
- `test_healing_engine.py`: 11 passed
- `test_autonomous_pipeline.py`: 12 passed
- Legacy increments (git analysis, selector, generator, llm): 38 passed
- **Total: 94 passed, 0 failed.**
