# TravelGuard AI — Autonomous QA Platform

---

### 1. What TravelGuard AI Is
**TravelGuard AI** is an **Autonomous Quality Engineer for the AI Development Era**. It bridges the gap between code-level commits, runtime browser execution, failure diagnosis, verified self-healing, and enterprise release gating:
- Detects what changed across the repository (working tree, git commit ranges, or CI PR diffs).
- Translates file changes into affected **Business User Journeys** (Flight Search, Flight Selection, Passenger Details, Flight Booking & Confirmation).
- Employs a resilient 3-tier LLM hierarchy (**Groq** primary $\to$ **OpenRouter** fallback 1 $\to$ **Gemini** fallback 2) with zero secret leakage via the **Secret Scrubber**.
- Computes a transparent, explainable **Risk Score (0–100)** and risk tier (**LOW, MEDIUM, HIGH, CRITICAL**).
- Maintains a machine-readable **Test Inventory** (`travelguard/test_inventory.yaml`).
- **Intelligently selects** tests into prioritized tiers (**P0, P1, P2**) with transparent accounting of skipped tests.
- Detects **Coverage Gaps** and **generates candidate Playwright tests** (`tests/generated/`) with static QA validation.
- **Autonomously executes tests** using Playwright / Pytest runners with real-time browser inspection via a genuine **Model Context Protocol (MCP)** server.
- Accurately diagnoses failures into **`TEST_DRIFT`**, **`PRODUCT_DEFECT`**, or **`ENVIRONMENT_FAILURE`**.
- **Self-heals** brittle locators safely (backup created, confidence gated >= 0.70, re-validated) while strictly refusing to heal real product bugs.
- Mathematically quantifies **Release Confidence (0–100%)** with an explicit audit formula and discount accounting.
- Enforces deterministic **CI/CD Quality Gates** with standardized exit codes (`0` = Pass, `2` = Defect, `3` = Env Failure, `4` = Unknown).
- Emits **Prometheus Metrics** (`/api/metrics`) and **OpenTelemetry Traces** with a ready-to-use Grafana dashboard.

---

### 2. The Controlled System Under Test: SkyBook
**SkyBook** is a lightweight, fully functional travel booking web application that serves as the controlled **System Under Test (SUT)**. It implements a sequential 5-stage travel workflow:

$$\text{Flight Search} \longrightarrow \text{Flight Results} \longrightarrow \text{Select Flight} \longrightarrow \text{Passenger Details} \longrightarrow \text{Book Flight} \longrightarrow \text{Booking Confirmation}$$

---

### 3. Interactive Developer Console (Web Dashboard)

While developers work on any travel application locally, they can launch and interact with the **TravelGuard AI Developer Console** in their browser at `http://localhost:5173`:

- **Seamless Dual-Mode**: Switch between the customer-facing **SkyBook Booking App** and the **TravelGuard Dev Console** via the top header toggle or the floating quick launcher.
- **One-Click Autonomous Demo Triggers**:
  - **Scenario A**: Booking UI Drift & Self-Healing (`TEST_DRIFT` &rarr; `RELEASE ALLOWED`)
  - **Scenario B**: Booking API Defect (`PRODUCT_DEFECT` &rarr; `RELEASE BLOCKED`)
  - **Scenario C**: Environment Failure (`ENVIRONMENT_FAILURE` &rarr; `RELEASE BLOCKED`)
  - **Scenario D**: Promo Code Feature & Test Gen (`COVERAGE GAP` &rarr; `Playwright Gen`)
  - **Live Local Git Changes**: Real-time analysis of uncommitted local working tree diffs.
- **7-Stage Visual Pipeline Stepper**: Live animated stage pills (Change Detect &rarr; Journey Mapping &rarr; Test Selection &rarr; Execution &rarr; AI Diagnosis &rarr; Self-Healing &rarr; Release Gate).
- **Executive Release Verdict Banner**: Glowing emerald banner for `RELEASE ALLOWED` and vibrant rose for `RELEASE BLOCKED` with exact exit code and confidence percentage.
- **Visual Self-Healing Inspector**: Interactive diff viewer displaying `- Old Locator` &rarr; `+ Repaired Locator`, patch status, and automated re-validation results.
- **AI Test Generator Playground**: Displays generated Playwright TypeScript tests with line numbers and a 1-click **Copy Code** button.

---

### 4. Architecture & Intelligence Pipeline

```
Git Working Tree / Commits / PRs / Preset Fixtures
                          │
                          ▼
                  [ChangeDetector]
        (Extracts unified diffs & file statuses)
                          │
                          ▼
                    [ChangeSet]
            (Normalized change data model)
                          │
                          ▼
                  [JourneyMapper]
        (Matches paths against journeys.yaml)
                          │
                          ▼
                [ChangeImpactAnalyzer]
                          │
                          ▼
                 [LLMService Router]
        Primary: Groq ──(fallback)──► OpenRouter ──(fallback)──► Gemini
                          │
                          ▼
               Validated Structured JSON
                          │
                          ▼
                   [RiskEngine]
        (Transparent 0–100 score calculation)
                          │
                          ▼
            [TestIntelligencePipeline]
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
  [TestSelectorEngine]         [CoverageAnalyzer]
 (P0/P1/P2 Selection &        (Gap Detection against
  Skipped Test Accounting)       Test Inventory)
                                        │ (If INSUFFICIENT)
                                        ▼
                               [AITestGenerator]
                             (Playwright TypeScript)
                                        │
                                        ▼
                                 [TestValidator]
                            (Multi-point Static QA)
                                        │
                                        ▼
                       Candidate in tests/generated/
```

---

### 5. Resilient 3-Tier Multi-Provider LLM Hierarchy

All LLM calls flow through an observable fallback router. If any provider fails, the router immediately attempts the next tier:

| Tier | Provider | Model | Environment Variable | Role |
|---|---|---|---|---|
| **Tier 1 (Primary)** | Groq | `openai/gpt-oss-120b` (or `openai/gpt-oss-20b`) | `GROQ_API_KEY`, `GROQ_MODEL` | Ultra-fast primary reasoning |
| **Tier 2 (Fallback 1)** | OpenRouter | `openrouter/free` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Secondary fallback provider |
| **Tier 3 (Fallback 2)** | Gemini | `gemini-3-flash-preview` | `GEMINI_API_KEY`, `GEMINI_MODEL` | High-capacity tertiary fallback |

If all three providers fail, the router returns `ALL_LLM_PROVIDERS_FAILED`.

Health check endpoint: `GET /api/llm/health` reports status across all 3 tiers without leaking credentials.

---

### 6. Machine-Readable Test Inventory

Registered in `travelguard/test_inventory.yaml`, representing actual tests in the repository:

| Test ID | File | Journeys Covered | Criticality | Default Priority |
|---|---|---|---|---|
| `flight-booking` | `tests/e2e/booking.spec.ts` | `flight_booking`, `passenger_details` | `critical` | **P0** |
| `booking-api` | `backend/tests/test_api.py::test_booking_success` | `flight_booking` | `critical` | **P0** |
| `passenger-validation` | `tests/e2e/validation.spec.ts` | `passenger_details` | `high` | **P1** |
| `flight-selection` | `tests/e2e/select-flight.spec.ts` | `flight_selection` | `high` | **P1** |
| `flight-search` | `tests/e2e/search.spec.ts` | `flight_search` | `medium` | **P1** |

CLI command to inspect the inventory:
```bash
python -m travelguard test-inventory
```

---

### 7. Repository Structure

```
TravelGuard-AI/
├── .github/
│   └── workflows/
│       └── qa.yml                # CI/CD workflow with autonomous QA quality gate
├── travelguard/                  # TravelGuard Intelligence Core (INCREMENT 5)
│   ├── __init__.py               # Package version (v0.5.0)
│   ├── __main__.py               # CLI runner entrypoint
│   ├── analyzer.py               # AI change analyzer with JSON validation & LLM routing
│   ├── autonomous_pipeline.py    # End-to-end autonomous QA engine & orchestrator
│   ├── change_detector.py        # Git working tree, commit diff & fixture change detection
│   ├── cli.py                    # Rich terminal report formatter & CLI parser
│   ├── coverage_analyzer.py      # Coverage gap detection engine
│   ├── demo.py                   # Deterministic hackathon demo runner & SUT synchronization
│   ├── diagnosis_engine.py       # Failure diagnosis: TEST_DRIFT vs PRODUCT_DEFECT vs ENV
│   ├── execution_engine.py       # Dual-mode Playwright/Pytest test runner
│   ├── healing_engine.py         # Confidence-gated self-healing engine (safe backups & patch)
│   ├── journey_mapper.py         # Deterministic journey & capability mapping
│   ├── journeys.yaml             # Machine-readable Business Journey Registry
│   ├── mcp_inspector.py          # MCP client interface for real-time DOM queries
│   ├── mcp_server.py             # Genuine Playwright MCP server (JSON-RPC 2.0 stdio)
│   ├── models.py                 # Pydantic data schemas
│   ├── observability.py          # OpenTelemetry tracing & Prometheus metrics definitions
│   ├── pipeline.py               # Test Intelligence Pipeline orchestrator
│   ├── quality_gate.py           # Deterministic CI/CD release gate & standard exit codes
│   ├── recommender.py            # Targeted test recommendation engine
│   ├── registry.py               # Journey registry loader
│   ├── release_confidence.py     # Mathematical release confidence scoring engine
│   ├── risk_engine.py            # Transparent risk scoring engine (0-100)
│   ├── security.py               # Secret scrubber redacting credentials before LLM dispatch
│   ├── test_generator.py         # Grounded Playwright test generator
│   ├── test_inventory.py         # Test inventory registry loader
│   ├── test_inventory.yaml       # Machine-readable test catalog
│   ├── test_selector.py          # Deterministic & LLM-based P0/P1/P2 test selector
│   ├── test_validator.py         # Multi-point static Playwright test validator
│   ├── fixtures/                 # Predefined diff fixtures for deterministic demos
│   └── tests/                    # Comprehensive automated unit & integration tests
├── observability/
│   └── grafana/
│       └── dashboard.json        # Pre-configured Grafana QA dashboard
├── frontend/                     # SkyBook React + TypeScript + Vite SUT
│   ├── src/
│   │   ├── travelguard/          # TravelGuard AI Developer Console (Web Dashboard)
│   │   │   ├── TravelGuardConsole.tsx
│   │   │   ├── travelguard.css
│   │   │   └── types.ts
│   │   ├── components/           # SkyBook Booking UI components
│   │   └── App.tsx               # Dual SUT & TravelGuard Console state
├── backend/                      # Python FastAPI Backend
│   ├── app/
│   │   ├── api/                  # /api/health, /api/flights, /api/book, /api/llm, /api/metrics, /api/travelguard
│   │   ├── llm/                  # 3-Tier Provider abstraction (Groq, OpenRouter, Gemini)
│   │   └── main.py               # App configuration & Prometheus instrumentations
│   └── tests/                    # Backend unit, router fallback & TravelGuard API tests
├── tests/                        # Playwright Test Suite (TypeScript)
├── docs/
│   ├── increment-2.md
│   ├── increment-3.md
│   ├── increment-4.md
│   └── increment-5.md            # Production CI/CD, Genuine MCP & Release Confidence
├── pytest.ini                    # Standard pytest test discovery & pythonpath configuration
├── .env.example                  # Template with Groq, OpenRouter, Gemini configs
└── README.md
```

---

### 8. How to Run TravelGuard CLI

From the repository root:

#### A. Analyze Current Working Tree or Git Commits
```bash
# Analyze unstaged, staged, and untracked changes in the working tree
python -m travelguard analyze

# Diff against a specific commit or branch reference
python -m travelguard analyze --ref HEAD~1
```

#### B. Run the 4 Deterministic Hackathon Demo Scenarios
```bash
# Scenario A: Cosmetic UI Change (Search button styling) -> Risk: LOW, P2 Selected
python -m travelguard analyze --demo scenario_a

# Scenario B: Booking UI Change (PassengerForm submit handler) -> Risk: HIGH, P0 Selected
python -m travelguard analyze --demo scenario_b

# Scenario C: Booking API Change (/api/book payload & validation) -> Risk: CRITICAL, P0 Selected
python -m travelguard analyze --demo scenario_c

# Scenario D: New Feature (Promo Code) -> Gap Detected -> Generates & Statically Validates Test!
python -m travelguard analyze --demo scenario_d

# Emit machine-readable JSON for CI integration
python -m travelguard analyze --demo scenario_d --json

# Offline verification mode (deterministic mock LLM)
python -m travelguard analyze --demo scenario_d --mock-llm
```

#### C. Inspect Test Inventory and Business Journeys
```bash
# View all registered tests with priorities and journey tags
python -m travelguard test-inventory

# View all registered business user journeys
python -m travelguard journeys

# List available demo scenarios
python -m travelguard demo
```

---

### 9. Example Analysis Output (Scenario D: New Feature)

```
==================================================
TRAVELGUARD AI
INTELLIGENT TEST SELECTION & AI GENERATION
==================================================

Changed Files:
  M frontend/src/components/PassengerForm.tsx

--------------------------------------------------
CHANGE SUMMARY
--------------------------------------------------
Added promotional discount coupon input and discount calculation to passenger details checkout.
Change Type: UI (Behavioral)

--------------------------------------------------
BUSINESS IMPACT
--------------------------------------------------
Affected Journey: Flight Booking & Confirmation
Capability:       Promotional coupon application and checkout fare calculation
Impact Level:     HIGH

Business Impact:
Pricing discrepancy or checkout disruption if promotional calculation fails.

--------------------------------------------------
RISK ASSESSMENT
--------------------------------------------------
Risk Level: HIGH
Risk Score: 85/100
Reason:     Introduces new promotional code state, coupon validation, and dynamic fare modification.

--------------------------------------------------
INTELLIGENT TEST SELECTION (P0 / P1 / P2)
--------------------------------------------------
Selected Tests (2):
  [P0] tests/e2e/booking.spec.ts
       Reason: Critical revenue-impacting booking flow directly modified by form changes
  [P0] backend/tests/test_api.py::test_booking_success
       Reason: Booking transaction API contract must be validated against passenger payload changes

Skipped Tests (3):
  [-] tests/e2e/search.spec.ts
      Reason: Test targets flight_search, but change only impacts flight_booking
  [-] tests/e2e/select-flight.spec.ts
      Reason: Test targets flight_selection, but change only impacts flight_booking
  [-] tests/e2e/validation.spec.ts
      Reason: Existing validation does not cover new promo code capabilities

--------------------------------------------------
COVERAGE GAP EVALUATION
--------------------------------------------------
Status: INSUFFICIENT
Reason: Code change introduces promotional code logic but no test in the inventory covers promo code application.
Missing Scenarios:
  - Promo code input validation and discount application

--------------------------------------------------
AI-GENERATED PLAYWRIGHT TEST
--------------------------------------------------
File:              tests/generated/promo-code.spec.ts
Target Journey:    Flight Booking & Confirmation
Validation Status: PASSED

Static Checks Passed:
  ✓ File written to tests/generated/
  ✓ Playwright imports verified (@playwright/test)
  ✓ Executable test() suite defined
  ✓ Assertions present (expect)
  ✓ Syntax structure balanced
  ✓ No arbitrary sleep (page.waitForTimeout avoided)
  ✓ AI disclaimer header present

--------------------------------------------------
AI ORCHESTRATION
--------------------------------------------------
Provider Used: Groq (openai/gpt-oss-120b)
Confidence:    96%
Fallback Used: No
==================================================
```

---

### 10. How to Run Automated Tests

Execute the complete automated test suite across all subsystems (**140 unit, intelligence & integration tests passing**):

```bash
# Run all TravelGuard and backend tests (140 tests passing)
python -m pytest

# Run specific intelligence test files with verbose output
python -m pytest travelguard/tests/test_autonomous_pipeline.py -v
python -m pytest travelguard/tests/test_quality_gate.py -v
python -m pytest travelguard/tests/test_release_confidence.py -v
python -m pytest travelguard/tests/test_mcp_genuine.py -v

# Run Playwright E2E suite
cd tests && npx playwright test
```

---

### 11. Autonomous QA Demo Commands (Deterministic)

Run fully deterministic, reproducible demo scenarios demonstrating autonomous failure classification, self-healing, and release quality gating:

```bash
# Scenario A: UI Locator Drift -> Diagnosed as TEST_DRIFT -> Self-Heals -> Release ALLOWED
python -m travelguard autonomous-demo --demo booking-ui-drift --mock-llm
# Expected: Exit Code 0 | Verdict: RELEASE ALLOWED (PASS WITH HEALING)

# Scenario B: Backend 500 Defect -> Diagnosed as PRODUCT_DEFECT -> Healing REJECTED -> Release BLOCKED
python -m travelguard autonomous-demo --demo booking-api-defect --mock-llm
# Expected: Exit Code 2 | Verdict: RELEASE BLOCKED

# Scenario C: Environment Offline -> Diagnosed as ENVIRONMENT_FAILURE -> Release BLOCKED
python -m travelguard autonomous-demo --demo environment-failure --mock-llm
# Expected: Exit Code 3 | Verdict: RELEASE BLOCKED (ENVIRONMENT FAILURE)
```

---

### 12. CI/CD Quality Gate & Production Observability

#### A. Standardized Quality Gate Exit Codes
The Quality Gate (`travelguard/quality_gate.py`) returns standard exit codes for seamless CI/CD integration:
- **`0`**: `RELEASE ALLOWED` (Suite passed or healed with confidence $\ge 0.85$)
- **`2`**: `RELEASE BLOCKED` (Real product defect detected; bug report generated)
- **`3`**: `RELEASE BLOCKED` (Environment / infrastructure failure detected)
- **`4`**: `RELEASE BLOCKED` (Unclassified or low-confidence failure)

Run on any branch or pull request:
```bash
python -m travelguard autonomous-run --quality-gate
```

#### B. Prometheus Metrics & Grafana Dashboard
- Prometheus metrics are exposed at `GET /api/metrics` via FastAPI.
- Tracked metrics:
  - `travelguard_runs_total` (counter partitioned by status)
  - `travelguard_quality_gate_decision_total` (ALLOW_RELEASE vs BLOCK_RELEASE)
  - `travelguard_release_confidence` (gauge)
  - `travelguard_tests_healed_total` (counter)
  - `travelguard_defects_detected_total` (counter)
- Pre-configured Grafana dashboard JSON available at `observability/grafana/dashboard.json`.

#### C. GitHub Actions CI/CD Pipeline
- Automated quality gate workflow configured in `.github/workflows/qa.yml`.
- Runs full test suite, launches SUT, executes `travelguard autonomous-run --quality-gate`, and archives quality reports.

---

### 13. How to Start the SkyBook Application

#### Start Backend
```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
Backend runs at `http://localhost:8000` (API docs at `http://localhost:8000/docs`, metrics at `http://localhost:8000/api/metrics`).

#### Start Frontend
```bash
cd frontend
npm run dev
```
SkyBook frontend opens at `http://localhost:5173`.

---

### 14. Incremental Roadmap

```
Git / Application Changes
        ↓
Change Detection       ← COMPLETED (Increment 2)
        ↓
Business Impact        ← COMPLETED (Increment 2)
        ↓
Risk Analysis          ← COMPLETED (Increment 2)
        ↓
Test Selection         ← COMPLETED (Increment 3)
        ↓
Test Generation        ← COMPLETED (Increment 3)
        ↓
Static QA Validation   ← COMPLETED (Increment 3)
        ↓
Test Execution         ← COMPLETED (Increment 4)
        ↓
Failure Diagnosis      ← COMPLETED (Increment 4)
        ↓
Self-Healing           ← COMPLETED (Increment 4)
        ↓
Defect Analysis        ← COMPLETED (Increment 5)
        ↓
Genuine Playwright MCP ← COMPLETED (Increment 5)
        ↓
Release Confidence     ← COMPLETED (Increment 5)
        ↓
CI/CD Quality Gate     ← COMPLETED (Increment 5)
```


