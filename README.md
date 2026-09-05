# TravelGuard AI — Autonomous QA Platform
## Increment 4: Autonomous Test Execution, Failure Diagnosis & Self-Healing

---

### 1. What TravelGuard AI Is
**TravelGuard AI** is an **Autonomous Quality Engineer for the AI Development Era**. It bridges the gap between code-level commits, runtime browser execution, failure diagnosis, and verified self-healing:
- Detects what changed across the repository (working tree, git commit ranges, or CI PR diffs).
- Translates file changes into affected **Business User Journeys** (Flight Search, Flight Selection, Passenger Details, Flight Booking & Confirmation).
- Employs a resilient 3-tier LLM hierarchy (**Groq** primary $\to$ **OpenRouter** fallback 1 $\to$ **Gemini** fallback 2).
- Computes a transparent, explainable **Risk Score (0–100)** and risk tier (**LOW, MEDIUM, HIGH, CRITICAL**).
- Maintains a machine-readable **Test Inventory** (`travelguard/test_inventory.yaml`).
- **Intelligently selects** tests into prioritized tiers (**P0, P1, P2**) with transparent accounting of skipped tests.
- Detects **Coverage Gaps** and **generates candidate Playwright tests** (`tests/generated/`) with static QA validation.
- **Autonomously executes tests** using Playwright / Pytest subprocess runners.
- Inspects runtime DOM and element accessibility via **MCP Browser Inspector**.
- Accurately diagnoses failures into **`TEST_DRIFT`**, **`PRODUCT_DEFECT`**, or **`ENVIRONMENT_FAILURE`**.
- **Self-heals** stale locators safely (backup created, confidence gated >= 0.70, re-validated) while strictly refusing to heal real product bugs.
- Generates executive **Quality Reports** (JSON & Markdown) with overall quality status.

---

### 2. The Controlled System Under Test: SkyBook
**SkyBook** is a lightweight, fully functional travel booking web application that serves as the controlled **System Under Test (SUT)**. It implements a sequential 5-stage travel workflow:

$$\text{Flight Search} \longrightarrow \text{Flight Results} \longrightarrow \text{Select Flight} \longrightarrow \text{Passenger Details} \longrightarrow \text{Book Flight} \longrightarrow \text{Booking Confirmation}$$

---

### 3. Architecture & Intelligence Pipeline

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

### 4. Resilient 3-Tier Multi-Provider LLM Hierarchy

All LLM calls flow through an observable fallback router. If any provider fails, the router immediately attempts the next tier:

| Tier | Provider | Model | Environment Variable | Role |
|---|---|---|---|---|
| **Tier 1 (Primary)** | Groq | `openai/gpt-oss-120b` (or `openai/gpt-oss-20b`) | `GROQ_API_KEY`, `GROQ_MODEL` | Ultra-fast primary reasoning |
| **Tier 2 (Fallback 1)** | OpenRouter | `openrouter/free` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Secondary fallback provider |
| **Tier 3 (Fallback 2)** | Gemini | `gemini-3-flash-preview` | `GEMINI_API_KEY`, `GEMINI_MODEL` | High-capacity tertiary fallback |

If all three providers fail, the router returns `ALL_LLM_PROVIDERS_FAILED`.

Health check endpoint: `GET /api/llm/health` reports status across all 3 tiers without leaking credentials.

---

### 5. Machine-Readable Test Inventory

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

### 6. Repository Structure

```
TravelGuard-AI/
├── travelguard/                  # TravelGuard Intelligence Core (INCREMENT 3)
│   ├── __init__.py               # Package version (v0.3.0)
│   ├── __main__.py               # CLI runner entrypoint
│   ├── analyzer.py               # AI change analyzer with JSON validation & LLM routing
│   ├── change_detector.py        # Git working tree, commit diff & fixture change detection
│   ├── cli.py                    # Rich terminal report formatter & CLI parser
│   ├── coverage_analyzer.py      # Coverage gap detection engine
│   ├── demo.py                   # Deterministic hackathon demo runner (Scenarios A-D)
│   ├── journey_mapper.py         # Deterministic journey & capability mapping
│   ├── journeys.yaml             # Machine-readable Business Journey Registry
│   ├── models.py                 # Pydantic schemas (ChangeSet, TestIntelligenceResult, etc.)
│   ├── pipeline.py               # Test Intelligence Pipeline orchestrator
│   ├── recommender.py            # Targeted test recommendation engine
│   ├── registry.py               # Journey registry loader
│   ├── risk_engine.py            # Transparent risk scoring engine (0-100)
│   ├── test_generator.py         # Grounded Playwright test generator
│   ├── test_inventory.py         # Test inventory registry loader
│   ├── test_inventory.yaml       # Machine-readable test catalog
│   ├── test_selector.py          # Deterministic & LLM-based P0/P1/P2 test selector
│   ├── test_validator.py         # Multi-point static Playwright test validator
│   ├── fixtures/                 # Predefined diff fixtures for deterministic demos
│   │   ├── scenario_a_cosmetic_ui.diff
│   │   ├── scenario_b_booking_ui.diff
│   │   ├── scenario_c_booking_api.diff
│   │   └── scenario_d_promo_code.diff
│   └── tests/                    # 36 automated unit tests
├── frontend/                     # SkyBook React + TypeScript + Vite SUT
│   ├── src/
│   │   ├── components/           # Header, SearchForm, FlightResults, PassengerForm, Confirmation
│   │   ├── services/api.ts       # Typed client for FastAPI endpoints
│   │   ├── types/index.ts        # Shared TypeScript data models
│   │   ├── index.css             # Modern design system & styling
│   │   ├── App.tsx               # 5-step booking state management
│   │   └── main.tsx              # Application entrypoint
│   └── package.json
├── backend/                      # Python FastAPI Backend
│   ├── app/
│   │   ├── api/                  # /api/health, /api/flights, /api/book, /api/llm
│   │   ├── llm/                  # 3-Tier Provider abstraction (Groq, OpenRouter, Gemini, Router)
│   │   ├── models/               # Pydantic data schemas
│   │   ├── config.py             # Pydantic Settings reading .env
│   │   └── main.py               # App configuration & CORS middleware
│   ├── tests/                    # 13 backend unit & router fallback tests
│   ├── requirements.txt
│   └── run.py                    # Server launch script
├── tests/                        # Playwright Test Suite (TypeScript)
│   ├── e2e/                      # 11 baseline E2E & API health tests
│   │   ├── search.spec.ts
│   │   ├── select-flight.spec.ts
│   │   ├── booking.spec.ts
│   │   ├── validation.spec.ts
│   │   └── api-health.spec.ts
│   ├── generated/                # Isolated directory for AI-generated candidate tests
│   ├── playwright.config.ts
│   └── package.json
├── docs/
│   ├── increment-1.md            # SUT & baseline test specification
│   ├── increment-2.md            # Change detection & business impact design
│   └── increment-3.md            # Test selection & AI generation design
├── .env.example                  # Template with Groq, OpenRouter, Gemini configs
├── .gitignore                    # Secrets and build ignore rules
└── README.md
```

---

### 7. How to Run TravelGuard CLI

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

### 8. Example Analysis Output (Scenario D: New Feature)

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

### 9. How to Run Automated Tests

Execute automated tests across all tiers (94 unit & integration tests):

```bash
# Run all TravelGuard unit & integration tests (94 tests)
python -m pytest travelguard/tests/ -v

# Run backend API tests
pytest backend/tests

# Run Playwright E2E suite
cd tests && npx playwright test
```

---

### 10. Autonomous QA Demo Commands (Increment 4)

Run deterministic, observable demo scenarios:

```bash
# Scenario 1: UI Locator Drift -> Diagnosed as TEST_DRIFT -> Automatically Healed
python -m travelguard autonomous-demo --demo booking-ui-drift --mock-llm

# Scenario 2: Backend API Defect -> Diagnosed as PRODUCT_DEFECT -> Self-healing REJECTED -> Bug Reported
python -m travelguard autonomous-demo --demo booking-api-defect --mock-llm

# Scenario 3: Backend Offline -> Diagnosed deterministically as ENVIRONMENT_FAILURE -> Pipeline BLOCKED
python -m travelguard autonomous-demo --demo environment-failure --mock-llm
```

---

### 11. How to Start the SkyBook Application

#### Start Backend
```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
Backend runs at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

#### Start Frontend
```bash
cd frontend
npm run dev
```
SkyBook frontend opens at `http://localhost:5173`.

---

### 12. Incremental Roadmap

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
Defect Analysis        ← (Increment 5)
        ↓
Release Decision       ← (Increment 5)
```

