# TravelGuard AI — Increment 2 Design Document
## Change Detection & Business Impact Analysis

---

### 1. Overview & Objective
Increment 2 introduces the first real intelligence layer of **TravelGuard AI**:
- Translating low-level code/file modifications into **high-level business intent**.
- Reasoning about impact on customer user journeys in SkyBook.
- Assessing risk via deterministic rules and multi-provider LLM analysis (Groq primary with OpenRouter and Gemini fallbacks).
- Recommending targeted tests to run.
- Providing deterministic hackathon demo scenarios and a rich interactive CLI.

---

### 2. Core Architectural Principles
1. **Business Intent over Raw Files**:
   TravelGuard does not simply report that `PassengerForm.tsx` or `booking.py` changed. It determines that the **Flight Booking & Confirmation** journey has been impacted, identifies the customer capability (e.g. traveler details capture and ticket issuance), and calculates business risk accordingly.
2. **Deterministic First, LLM Augmented**:
   Before querying the LLM, known paths and components are matched against the machine-readable **Business Journey Registry** (`travelguard/journeys.yaml`). This avoids wasting LLM calls on basic file routing while providing rich context to the LLM prompt.
3. **Multi-Tier Resilient LLM Layer**:
   Reuses the provider router:
   - Primary: **Groq** (`openai/gpt-oss-120b` or `openai/gpt-oss-20b`)
   - Fallback 1: **OpenRouter** (`openrouter/free`)
   - Fallback 2: **Gemini** (`gemini-3-flash-preview`)
   - If a provider is unavailable or encounters a network/rate limit error, failover down the hierarchy happens seamlessly with observable logging.
4. **Transparent Risk Scoring**:
   Combines journey criticality, modification type (API vs UI vs config), behavioral significance, and diff volume into a clean 0–100 score and categorical level (LOW, MEDIUM, HIGH, CRITICAL).
5. **Zero Mutation / Safe Boundary**:
   Increment 2 does **not** execute tests automatically, modify source code, update locators, or perform self-healing. It strictly observes, reasons, assesses risk, and recommends tests.

---

### 3. Pipeline Architecture

```
Git Working Tree / Commits / PRs / Fixtures
                     │
                     ▼
             [ChangeDetector]
        (Extracts unified diffs & file statuses)
                     │
                     ▼
               [ChangeSet]
       (Normalized internal change model)
                     │
                     ▼
             [JourneyMapper]
   (Matches paths & components against journeys.yaml)
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
Deterministic Journey       Candidate Tests
       │                           │
       └─────────────┬─────────────┘
                     ▼
           [ChangeImpactAnalyzer]
                     │
                     ▼
          [LLMService Router]
       Primary: Groq ──(failover)──► OpenRouter ──(failover)──► Gemini
                     │
                     ▼
          Validated Structured JSON
                     │
                     ▼
              [RiskEngine]
   (Transparent scoring: Criticality + Type + Behavioral)
                     │
                     ▼
           [TestRecommender]
   (Prioritizes E2E and API tests for affected workflows)
                     │
                     ▼
       [ImpactAnalysisResult & CLI Report]
```

---

### 4. Component Directory Structure

```
travelguard/
├── __init__.py                # Package metadata (v0.2.0)
├── __main__.py                # Module execution entrypoint (python -m travelguard)
├── analyzer.py                # ChangeImpactAnalyzer with LLM routing and JSON validation
├── change_detector.py         # Working tree, commit diff, and fixture change detectors
├── cli.py                     # CLI report formatter, commands, and argument parser
├── demo.py                    # Deterministic hackathon demo scenario runner
├── journey_mapper.py          # Deterministic path and component matcher
├── journeys.yaml              # Machine-readable Business Journey Registry
├── models.py                  # Pydantic data schemas (ChangeSet, FileChange, ImpactAnalysisResult)
├── recommender.py             # Test recommendation engine
├── registry.py                # YAML loader and query interface
├── risk_engine.py             # Transparent risk scoring engine (0-100)
├── fixtures/                  # Preset diff fixtures for deterministic demos
│   ├── scenario_a_cosmetic_ui.diff
│   ├── scenario_b_booking_ui.diff
│   └── scenario_c_booking_api.diff
└── tests/                     # 36 automated unit & integration tests
    ├── test_analyzer.py
    ├── test_change_detector.py
    ├── test_demo_scenarios.py
    ├── test_journey_mapping.py
    └── test_risk_engine.py
```

---

### 5. Registered SkyBook Business Journeys

Defined in `travelguard/journeys.yaml`:

| Stage | Journey ID | Name | Criticality | Components / Routes | Candidate Tests |
|---|---|---|---|---|---|
| 0 | `system_health` | System & LLM Diagnostics | MEDIUM | `/api/health`, `/api/llm/health`, `backend/app/llm` | `api-health.spec.ts`, `test_api.py::test_health_check`, `test_llm.py` |
| 1 | `flight_search` | Flight Search | MEDIUM | `SearchForm.tsx`, `Header.tsx`, `/api/flights` | `search.spec.ts`, `test_api.py::test_flights_search_filter` |
| 2 | `flight_selection` | Flight Selection | MEDIUM | `FlightResults.tsx`, `/api/flights` | `select-flight.spec.ts`, `test_api.py::test_flights_catalogue` |
| 3 | `passenger_details` | Passenger Details & Validation | HIGH | `PassengerForm.tsx`, `ErrorBanner.tsx`, `/api/book` | `validation.spec.ts`, `test_api.py::test_booking_validation_failure` |
| 4 | `flight_booking` | Flight Booking & Confirmation | CRITICAL | `Confirmation.tsx`, `PassengerForm.tsx`, `App.tsx`, `api.ts`, `/api/book` | `booking.spec.ts`, `test_api.py::test_booking_success` |

---

### 6. Risk Scoring Model

The risk engine computes a 0–100 score and assigns a category:
- **0–30: LOW**
- **31–70: MEDIUM**
- **71–90: HIGH**
- **91–100: CRITICAL**

#### Scoring Factors:
1. **Journey Criticality Base**:
   - `CRITICAL`: +50
   - `HIGH`: +35
   - `MEDIUM`: +20
   - `LOW`: +10
2. **Change Type Weight**:
   - `API`: +30
   - `Business Logic`: +25
   - `Runtime Config`: +25
   - `UI (Behavioral)`: +20
   - `UI (Cosmetic)`: +5
   - `Test`: +5
   - `Docs`: +0
3. **Behavioral Impact Modifier**:
   - Behavioral (`is_behavioral=True`): +15
   - Non-behavioral / cosmetic: -10 (capped at score 25–30)
4. **Diff Volume Modifier**:
   - > 50 lines: +5
   - > 200 lines: +10

---

### 7. Hackathon Demo Scenarios

Three isolated, deterministic demo scenarios are bundled in `travelguard/fixtures/`:

1. **Scenario A — Cosmetic UI Change (`scenario_a`)**:
   - **Diff**: Modifies button styling classes and text in `SearchForm.tsx`.
   - **Classification**: Cosmetic UI (`is_behavioral=False`).
   - **Risk**: **LOW** (Score: ~15/100).
   - **Affected Journey**: Flight Search.
   - **Recommended Tests**: Flight Search E2E (`tests/e2e/search.spec.ts`).

2. **Scenario B — Booking UI Change (`scenario_b`)**:
   - **Diff**: Alters form submission pipeline and payload structure in `PassengerForm.tsx`.
   - **Classification**: Behavioral UI (`is_behavioral=True`).
   - **Risk**: **HIGH** (Score: ~85/100).
   - **Affected Journey**: Flight Booking & Confirmation.
   - **Recommended Tests**: Flight Booking E2E, Booking Creation API, Form Validation E2E.

3. **Scenario C — Booking API Change (`scenario_c`)**:
   - **Diff**: Alters passenger name validation rules and confirmation code format in `/api/book`.
   - **Classification**: Behavioral Backend API (`is_behavioral=True`).
   - **Risk**: **CRITICAL** (Score: ~92–95/100).
   - **Affected Journey**: Flight Booking & Confirmation.
   - **Recommended Tests**: Booking Creation API, Booking Validation API, Flight Booking E2E.

---

### 8. CLI Usage Reference

```bash
# Analyze live git working tree
python -m travelguard analyze

# Analyze against a specific git commit or branch ref
python -m travelguard analyze --ref HEAD~1

# Run deterministic hackathon demo scenarios
python -m travelguard analyze --demo scenario_a
python -m travelguard analyze --demo scenario_b
python -m travelguard analyze --demo scenario_c

# Emit structured JSON
python -m travelguard analyze --demo scenario_b --json

# List all registered business user journeys
python -m travelguard journeys

# List available demo scenarios
python -m travelguard demo
```
