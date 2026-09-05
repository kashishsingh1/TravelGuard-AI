# TravelGuard AI — Increment 3 Architecture & Design Document
## Intelligent Test Selection & AI Test Generation

---

### 1. Overview & Objective
Increment 3 elevates **TravelGuard AI** from change impact observation into **actionable quality intelligence**:
- **From**: *"Something changed. Here are some tests you could run."*
- **To**: *"Something changed. I understand the business impact. I have selected the most important tests (P0/P1/P2) with data-driven rationale, accounted for skipped tests, detected coverage gaps, generated candidate Playwright tests for unhandled capabilities, and statically verified the generated code."*

---

### 2. Multi-Tier LLM Architecture (Strict 3-Tier Hierarchy)
All references to legacy providers have been completely removed. The system employs an observable 3-tier fallback chain:

```
                  ┌───────────────────────────────┐
                  │       Incoming Request        │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   Tier 1: Primary     │
                     │         Groq          │
                     │  openai/gpt-oss-120b  │
                     └───────────┬───────────┘
                                 │ Failover
                                 ▼
                     ┌───────────────────────┐
                     │  Tier 2: Fallback 1   │
                     │      OpenRouter       │
                     │    openrouter/free    │
                     └───────────┬───────────┘
                                 │ Failover
                                 ▼
                     ┌───────────────────────┐
                     │  Tier 3: Fallback 2   │
                     │        Gemini         │
                     │ gemini-3-flash-preview│
                     └───────────┬───────────┘
                                 │ All Failed
                                 ▼
                     ┌───────────────────────┐
                     │ALL_LLM_PROVIDERS_FAILED│
                     └───────────────────────┘
```

#### Provider Defaults & Configuration
| Tier | Provider | Environment Variable | Default Model | Base URL / Protocol |
|---|---|---|---|---|
| **Primary** | Groq | `GROQ_API_KEY`, `GROQ_MODEL` | `openai/gpt-oss-120b` (or `openai/gpt-oss-20b`) | `https://api.groq.com/openai/v1` |
| **Fallback 1** | OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `openrouter/free` | `https://openrouter.ai/api/v1` |
| **Fallback 2** | Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | `gemini-3-flash-preview` | `https://generativelanguage.googleapis.com/v1beta` |

Observable logging traces each stage in real time:
```text
[LLM] Request started across configured providers: groq, openrouter, gemini
[LLM] Provider 1: groq (model: openai/gpt-oss-120b)
[LLM] Status: SUCCESS | Latency: 420.5ms | Fallback: False
```

---

### 3. Machine-Readable Test Inventory
Located at `travelguard/test_inventory.yaml`, this registry mirrors the actual Playwright tests and API tests in the repository:

| Test ID | File | Journeys Covered | Criticality | Default Tier |
|---|---|---|---|---|
| `flight-booking` | `tests/e2e/booking.spec.ts` | `flight_booking`, `passenger_details` | `critical` | **P0** |
| `booking-api` | `backend/tests/test_api.py::test_booking_success` | `flight_booking` | `critical` | **P0** |
| `passenger-validation` | `tests/e2e/validation.spec.ts` | `passenger_details` | `high` | **P1** |
| `flight-selection` | `tests/e2e/select-flight.spec.ts` | `flight_selection` | `high` | **P1** |
| `flight-search` | `tests/e2e/search.spec.ts` | `flight_search` | `medium` | **P1** |

Can be inspected via the CLI:
```bash
python -m travelguard test-inventory
```

---

### 4. Intelligent Test Selection Engine
Test selection evaluates change impact and assigns tests to 3 priority tiers:
- **P0 (Critical)**: Direct changes affecting revenue-critical journeys (`flight_booking`) or API contracts.
- **P1 (Important)**: Functional changes to supporting journeys (`flight_search`, `passenger_details`) or regression suites.
- **P2 (Lower-Risk / Informational)**: Non-critical styling or cosmetic alterations.

#### Transparent Accounting
Every existing test in the inventory is categorized as either **Selected** or **Skipped**:
- **Selected Tests**: Includes priority tier, execution path, and data-driven rationale.
- **Skipped Tests**: Explicit explanation why the test was omitted (e.g., *"Test targets flight_search, but change only impacts flight_booking"*), avoiding blind execution or unexplained omissions.

---

### 5. Coverage Gap Detection & AI Test Generation
When code modifications introduce capabilities not covered by the inventory (such as promo codes, seat selection, or travel insurance), TravelGuard:
1. Identifies `CoverageStatus.INSUFFICIENT` with specific missing scenarios.
2. Prompts the primary LLM (or robust template engine) grounded in existing SkyBook Playwright conventions.
3. Generates a new test candidate into `tests/generated/` (e.g. `tests/generated/promo-code.spec.ts`).

#### Grounding Rules for AI Tests:
- Imports from `@playwright/test`.
- Mandatory header disclaimer:
  ```typescript
  /**
   * AI-GENERATED TEST - TRAVELGUARD AI
   * Generated: 2026-09-05
   * Target Journey: Flight Booking & Confirmation
   * SUT: SkyBook Flight Booking Application
   * DO NOT EDIT DIRECTLY - Candidate test awaiting human QA review.
   */
  ```
- Realistic data grounded in SkyBook UI (`#origin`, `#destination`, `#search-flights-btn`, `.flight-card`, `#fullName`, `#email`, `#phone`, `#promoCode`, `#book-flight-btn`).
- Prohibited from using `page.waitForTimeout()` (must use explicit locators/assertions).

---

### 6. Static Test Validation
Every generated candidate undergoes strict multi-point static verification before being reported:
1. **File Existence**: File was successfully written to `tests/generated/`.
2. **Playwright Imports**: Must import `test` and `expect` from `@playwright/test`.
3. **Executable Test Block**: Must define at least one `test(...)` suite.
4. **Assertions**: Must contain at least one `expect(...)` statement.
5. **Syntax Balance**: Braces `{}`, brackets `[]`, and parentheses `()` must match.
6. **No Arbitrary Sleep**: Prohibits `page.waitForTimeout()`.
7. **AI Disclaimer Header**: Validates the presence of the audit banner.

Status is reported as `PASSED` or `FAILED` with specific diagnostics.

---

### 7. Hackathon Demo Scenarios
TravelGuard provides 4 deterministic demo scenarios demonstrating the entire pipeline:

| Scenario | Name | Target File | Risk | Coverage | Generated Test |
|---|---|---|---|---|---|
| **`scenario_a`** | Cosmetic UI Change | `SearchForm.tsx` | LOW (15/100) | SUFFICIENT | None (P2 selected) |
| **`scenario_b`** | Booking UI Change | `PassengerForm.tsx` | HIGH (85/100) | SUFFICIENT | None (P0 selected) |
| **`scenario_c`** | Booking API Change | `booking.py` | CRITICAL (95/100) | SUFFICIENT | None (P0 selected) |
| **`scenario_d`** | New Feature (Promo Code) | `PassengerForm.tsx` | HIGH (85/100) | **INSUFFICIENT** | `promo-code.spec.ts` (**PASSED**) |

#### Run Commands:
```bash
# Scenario A (Cosmetic)
python -m travelguard analyze --demo scenario_a

# Scenario B (Booking UI)
python -m travelguard analyze --demo scenario_b

# Scenario C (Booking API)
python -m travelguard analyze --demo scenario_c

# Scenario D (New Feature: Promo Code with AI Generation)
python -m travelguard analyze --demo scenario_d

# Offline/Mock verification
python -m travelguard analyze --demo scenario_d --mock-llm
```

---

### 8. Explicit Boundary (Definition of Done for Increment 3)
- **NO Automated Test Execution**: Tests are generated and statically verified, but NOT executed automatically against the browser.
- **NO Self-Healing**: Dynamic locator healing and flake recovery are strictly reserved for Increment 4.
- **Candidate Isolation**: All generated tests are stored in `tests/generated/` and never overwrite baseline tests in `tests/e2e/`.
