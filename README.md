# TravelGuard AI — Autonomous QA Platform
## Increment 2: Change Detection & Business Impact Analysis

---

### 1. What TravelGuard AI Is
**TravelGuard AI** is an **Autonomous QA Engineer for AI-driven travel applications**. It bridges the gap between code-level commits and high-level travel business intent:
- Detects what changed across the repository (working tree, git commit ranges, or CI PR diffs).
- Translates file changes into affected **Business User Journeys** (Flight Search, Flight Selection, Passenger Details, Flight Booking & Confirmation).
- Employs resilient multi-provider LLM reasoning (**DeepSeek** primary with automatic failover to **Grok**).
- Computes a transparent, explainable **Risk Score (0–100)** and risk tier (**LOW, MEDIUM, HIGH, CRITICAL**).
- Recommends targeted automated tests to execute.
- Provides reproducible, zero-mutation **Hackathon Demo Scenarios**.

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
            ┌─────────────┴─────────────┐
            ▼                           ▼
     Known Journeys              Candidate Tests
            │                           │
            └─────────────┬─────────────┘
                          ▼
                [ChangeImpactAnalyzer]
                          │
                          ▼
                 [LLMService Router]
         Primary: DeepSeek ──(fallback)──► Grok
                          │
                          ▼
               Validated Structured JSON
                          │
                          ▼
                   [RiskEngine]
        (Transparent 0–100 score calculation)
                          │
                          ▼
                [TestRecommender]
        (Prioritizes E2E and API test suites)
                          │
                          ▼
            [CLI Report & Impact Result]
```

---

### 4. Repository Structure

```
TravelGuard-AI/
├── travelguard/                  # TravelGuard Intelligence Core (INCREMENT 2)
│   ├── __init__.py               # Package version (v0.2.0)
│   ├── __main__.py               # CLI runner entrypoint
│   ├── analyzer.py               # AI change analyzer with JSON validation & LLM routing
│   ├── change_detector.py        # Git working tree, commit diff & fixture change detection
│   ├── cli.py                    # Terminal report formatter & argument parsing
│   ├── demo.py                   # Deterministic hackathon demo scenario runner
│   ├── journey_mapper.py         # Deterministic journey & capability mapping
│   ├── journeys.yaml             # Machine-readable Business Journey Registry
│   ├── models.py                 # Pydantic schemas (ChangeSet, FileChange, ImpactResult)
│   ├── recommender.py            # Targeted test recommendation engine
│   ├── registry.py               # Journey registry loader & query interface
│   ├── risk_engine.py            # Transparent risk scoring engine (0-100)
│   ├── fixtures/                 # Predefined diff fixtures for deterministic demos
│   │   ├── scenario_a_cosmetic_ui.diff
│   │   ├── scenario_b_booking_ui.diff
│   │   └── scenario_c_booking_api.diff
│   └── tests/                    # 36 automated unit & integration tests
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
│   │   ├── llm/                  # Provider abstraction (DeepSeek, Grok, Router)
│   │   ├── models/               # Pydantic data schemas
│   │   ├── config.py             # Pydantic Settings reading .env
│   │   └── main.py               # App configuration & CORS middleware
│   ├── requirements.txt
│   └── run.py                    # Server launch script
├── tests/                        # Playwright Test Suite (TypeScript)
│   ├── e2e/
│   │   ├── search.spec.ts        # TEST 1: Flight search
│   │   ├── select-flight.spec.ts # TEST 2: Flight selection
│   │   ├── booking.spec.ts       # TEST 3: End-to-end booking flow
│   │   ├── validation.spec.ts    # TEST 4: Form validation rejection
│   │   └── api-health.spec.ts    # TEST 5: API & LLM health validation
│   ├── playwright.config.ts
│   └── package.json
├── docs/
│   └── increment-2.md            # In-depth architectural design document
├── .env.example                  # Environment configuration template
├── .gitignore                    # Secrets and build ignore rules
└── README.md
```

---

### 5. Machine-Readable Business Journey Registry

Defined in `travelguard/journeys.yaml`:

| Stage | Journey ID | Name | Criticality | Components / Routes | Candidate Tests |
|---|---|---|---|---|---|
| 0 | `system_health` | System & LLM Diagnostics | MEDIUM | `/api/health`, `/api/llm/health`, `backend/app/llm` | `api-health.spec.ts`, `test_health_check`, `test_llm.py` |
| 1 | `flight_search` | Flight Search | MEDIUM | `SearchForm.tsx`, `Header.tsx`, `/api/flights` | `search.spec.ts`, `test_flights_search_filter` |
| 2 | `flight_selection` | Flight Selection | MEDIUM | `FlightResults.tsx`, `/api/flights` | `select-flight.spec.ts`, `test_flights_catalogue` |
| 3 | `passenger_details` | Passenger Details & Validation | HIGH | `PassengerForm.tsx`, `ErrorBanner.tsx`, `/api/book` | `validation.spec.ts`, `test_booking_validation_failure` |
| 4 | `flight_booking` | Flight Booking & Confirmation | CRITICAL | `Confirmation.tsx`, `PassengerForm.tsx`, `App.tsx`, `api.ts`, `/api/book` | `booking.spec.ts`, `test_booking_success` |

---

### 6. Transparent Risk Scoring Model

Risk is computed by `RiskEngine` combining deterministic business rules with AI classification:
- **0–30: LOW**
- **31–70: MEDIUM**
- **71–90: HIGH**
- **91–100: CRITICAL**

#### Scoring Components:
1. **Journey Criticality Base**:
   - `CRITICAL`: +50 points
   - `HIGH`: +35 points
   - `MEDIUM`: +20 points
   - `LOW`: +10 points
2. **Change Type Points**:
   - `API`: +30 points
   - `Business Logic`: +25 points
   - `Configuration`: +25 points
   - `UI (Behavioral)`: +20 points
   - `UI (Cosmetic)`: +5 points
   - `Test / Docs`: +0 to +5 points
3. **Behavioral Modifier**:
   - Behavioral changes (`is_behavioral=True`): +15 points
   - Cosmetic changes (`is_behavioral=False`): -10 points (capped at 25–30 max)
4. **Diff Volume Modifier**:
   - Small (<50 lines): 0 points
   - Medium (50–200 lines): +5 points
   - Large (>200 lines): +10 points

---

### 7. How to Run TravelGuard CLI

From the repository root:

#### A. Analyze Current Git Changes
```bash
# Analyze unstaged, staged, and untracked changes in the working tree
python -m travelguard analyze

# Diff against a specific commit or branch reference
python -m travelguard analyze --ref HEAD~1
```

#### B. Run Deterministic Hackathon Demo Scenarios (Zero Code Mutation)
```bash
# Scenario A: Cosmetic UI Change (Search button styling) -> Risk: LOW
python -m travelguard analyze --demo scenario_a

# Scenario B: Booking UI Change (PassengerForm submit handler) -> Risk: HIGH
python -m travelguard analyze --demo scenario_b

# Scenario C: Booking API Change (/api/book payload & validation) -> Risk: CRITICAL
python -m travelguard analyze --demo scenario_c

# Emit machine-readable JSON
python -m travelguard analyze --demo scenario_c --json

# Offline verification mode (uses mock LLM, no API keys required)
python -m travelguard analyze --demo scenario_a --mock-llm
```

#### C. Inspect Registered Journeys and Demo Options
```bash
# List all registered business user journeys
python -m travelguard journeys

# List available demo scenarios
python -m travelguard demo
```

---

### 8. Example Analysis Output

```
==================================================
TRAVELGUARD AI
CHANGE IMPACT ANALYSIS
==================================================

Changed Files:

  M backend/app/api/booking.py

--------------------------------------------------
CHANGE SUMMARY
--------------------------------------------------

Updated booking ID generation and added passenger name length validation in the booking API.

Change Type:
BUSINESS_LOGIC (Behavioral)

--------------------------------------------------
BUSINESS IMPACT
--------------------------------------------------

Affected Journey:
Passenger Details & Validation
Capability:
Passenger name validation
Impact Level:
HIGH

Affected Journey:
Flight Booking & Confirmation
Capability:
Booking confirmation ID generation
Impact Level:
CRITICAL

Business Impact:
If the new validation rejects valid passenger names or the altered booking ID format is incompatible with other systems, customers may be unable to complete bookings, leading to lost revenue and a negative user experience.

--------------------------------------------------
RISK
--------------------------------------------------

Risk Level:
CRITICAL

Risk Score:
92/100

Reason:
The change modifies the booking ID format and introduces stricter name validation, which can break downstream services that rely on the old ID pattern and cause legitimate bookings to fail due to name length checks.

--------------------------------------------------
RECOMMENDED TESTS
--------------------------------------------------

✓ Booking Creation API (backend/tests/test_api.py::test_booking_success)
✓ Booking Validation API (backend/tests/test_api.py::test_booking_validation_failure)
✓ Flight Booking E2E (tests/e2e/booking.spec.ts)
✓ Form Validation E2E (tests/e2e/validation.spec.ts)

--------------------------------------------------
AI CONFIDENCE & ORCHESTRATION
--------------------------------------------------

Confidence: 90%
Provider:   Groq (Fallback Engaged)

==================================================
```

---

### 9. How to Run Automated Tests

Execute all 36 unit and integration tests (both Increment 1 backend tests and Increment 2 TravelGuard tests):

```bash
# Run complete test suite with pytest
python -m pytest backend/tests travelguard/tests
```

Expected output:
```
backend/tests/test_api.py .....                                          [ 13%]
backend/tests/test_llm.py ....                                           [ 25%]
travelguard/tests/test_analyzer.py ......                                [ 41%]
travelguard/tests/test_change_detector.py .....                          [ 55%]
travelguard/tests/test_demo_scenarios.py ....                            [ 66%]
travelguard/tests/test_journey_mapping.py .......                        [ 86%]
travelguard/tests/test_risk_engine.py .....                              [100%]

============================= 36 passed in 1.32s ==============================
```

---

### 10. How to Start the SkyBook Application

#### Start Backend
```bash
python backend/run.py
```
Backend runs at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

#### Start Frontend
```bash
cd frontend
npm run dev
```
SkyBook frontend opens at `http://localhost:5173`.

---

### 11. What is Intentionally NOT Implemented Yet

To preserve strict incremental engineering:
- ❌ No automated test execution (tests are recommended only).
- ❌ No self-healing or automatic locator rewriting.
- ❌ No automatic source code modification or auto-commit.
- ❌ No automatic test generation.
- ❌ No CI/CD pull-request commenting bot.

These capabilities are reserved for subsequent increments:
```
Git / Application
        ↓
Change Detection       ← COMPLETED (Increment 2)
        ↓
Business Impact        ← COMPLETED (Increment 2)
        ↓
Risk Analysis          ← COMPLETED (Increment 2)
        ↓
Test Selection         ← (Future Increment)
        ↓
Test Generation        ← (Future Increment)
        ↓
Self-Healing           ← (Future Increment)
        ↓
Defect Detection       ← (Future Increment)
        ↓
Release Decision       ← (Future Increment)
```
