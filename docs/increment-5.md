# TravelGuard AI — Increment 5 Architecture & Design Document
## Production CI/CD, Genuine Playwright MCP & Release Confidence

---

### 1. Overview & Vision
Increment 5 elevates **TravelGuard AI** from an autonomous test execution and healing engine into an enterprise-grade, production-ready continuous delivery quality platform:
- **From**: *"I executed tests, classified failures, and healed locators."*
- **To**: *"I act as an enterprise release gate in CI/CD. I inspect live UI state using a genuine Model Context Protocol (MCP) server, redact sensitive credentials from LLM prompts, mathematically quantify release confidence, enforce deterministic quality gate policies with CI/CD exit codes, and expose Prometheus metrics and OpenTelemetry traces."*

```
┌─────────────────────────────────────────────────────────────┐
│                 Continuous Integration / CD                 │
│              (.github/workflows/qa.yml)                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 TravelGuard Autonomous QA                   │
│             (AutonomousQAEngine: run_id)                    │
└──────┬───────────────────────┬───────────────────────┬──────┘
       │                       │                       │
       ▼                       ▼                       ▼
┌──────────────┐      ┌─────────────────┐     ┌──────────────────┐
│  Change Set  │      │ Genuine MCP     │     │ Secret Scrubber  │
│  & Selection │      │ Browser Server  │     │ (Credential &    │
└──────┬───────┘      │ (JSON-RPC 2.0)  │     │ Token Redaction) │
       │              └────────┬────────┘     └────────┬─────────┘
       ▼                       ▼                       │
┌───────────────────────────────────────┐              │
│       Diagnosis & Self-Healing        │◄─────────────┘
└──────────────────┬────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│               Release Confidence Engine                     │
│   Score = BasePassScore - (HealedCount * 0.05) - Caps       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Quality Gate Policy & Evaluator                │
│    Exit 0: PASS / RELEASE ALLOWED                           │
│    Exit 2: BLOCKED by Real Product Defect                   │
│    Exit 3: BLOCKED by Environment / Infra Failure           │
│    Exit 4: BLOCKED by Unclassified Failures                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           Observability & Artifact Reporting                │
│   • Prometheus /api/metrics   • Grafana Dashboard           │
│   • OpenTelemetry Traces      • artifacts/runs/*.json       │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Genuine Playwright MCP Server Architecture

Rather than invoking ad-hoc subprocess scripts, Increment 5 implements a native **Model Context Protocol (MCP)** server conforming to the JSON-RPC 2.0 stdio protocol.

#### 2.1 MCP Protocol & Tools (`travelguard/mcp_server.py`)
The MCP server operates as a standard stdio server exposing typed tools:
1. `travelguard_launch_browser`: Boots headless Chromium with configurable viewport and timeout.
2. `travelguard_navigate`: Loads an application URL and awaits network idle state.
3. `travelguard_inspect_dom`: Queries and summarizes interactable elements (`button`, `input`, `select`, `a`), extracting:
   - Tag name, `data-testid`, `id`, `name`, `aria-label`, visible text, and bounding box.
4. `travelguard_click`: Clicks a locator safely.
5. `travelguard_fill`: Types input values into targeted form controls.
6. `travelguard_take_screenshot`: Captures base64 PNG snapshots for multimodal LLM inspection.

#### 2.2 MCP Client Inspector (`travelguard/mcp_inspector.py`)
- Manages the lifecycle of MCP server connections.
- Bridges the diagnosis engine with real-time DOM states, providing rich, structured element accessibility data to determine if a broken locator is due to UI drift or an application regression.

---

### 3. Transparent Mathematical Release Confidence Engine

Release confidence is calculated by a deterministic mathematical engine (`travelguard/release_confidence.py`) rather than an arbitrary LLM guess:

$$\text{Confidence} = \max\left(0.0, \, \frac{\text{Passed}}{\text{Selected}} - (\text{Healed} \times 0.05) - \text{RiskPenalty}\right)$$

#### Strict Boundary & Policy Rules:
1. **Zero Tolerance for Product Defects**:
   - If any `PRODUCT_DEFECT` exists: $\text{Confidence} = 0.0$ (Strict release blocker).
2. **Environment Failure Ceiling**:
   - If any `ENVIRONMENT_FAILURE` exists: $\text{Confidence} \le 0.30$.
3. **Unknown Failure Discount**:
   - Each unclassified failure docks $0.25$ from the score.
4. **Self-Healing Discount**:
   - Self-healed tests verify functionality but carry risk of behavioral drift; each healed test incurs a transparent 5% ($0.05$) confidence discount.
5. **Human-Readable Formula Explanation**:
   - Every report includes a transparent breakdown explaining the exact score calculation for auditability and compliance.

---

### 4. Deterministic CI/CD Quality Gate & Standard Exit Codes

The Quality Gate (`travelguard/quality_gate.py`) enforces binary release gating with industry-standard exit codes:

| Gate Decision | Exit Code | Condition | Meaning |
|---|---|---|---|
| **`ALLOW_RELEASE`** | `0` | Status `PASS` or `PASS_WITH_HEALING`, 0 product defects, 0 env failures, confidence $\ge 0.85$. | Release candidate is healthy; pipeline succeeds. |
| **`BLOCK_RELEASE` (Defect)** | `2` | $\ge 1$ `PRODUCT_DEFECT` diagnosed. | Critical regression identified; blocks deployment. |
| **`BLOCK_RELEASE` (Env)** | `3` | $\ge 1$ `ENVIRONMENT_FAILURE` diagnosed. | Infrastructure offline; release blocked for retry. |
| **`BLOCK_RELEASE` (Unknown)** | `4` | $\ge 1$ `UNKNOWN` failure or confidence below threshold. | Unresolved test failure; requires human review. |

---

### 5. Security & Secret Scrubbing Layer

To ensure strict zero-leakage compliance when sending traces and DOM snippets to external AI model providers:
- **`travelguard/security.py`** scans all unified diffs, failure stack traces, and browser inspection dumps before LLM transmission.
- Patterns redacted automatically:
  - API Keys: Groq (`gsk_...`), OpenRouter (`sk-or-...`), Gemini (`AIza...`), OpenAI (`sk-...`), AWS (`AKIA...`), Stripe (`sk_live_...`).
  - Authorization headers (`Bearer ...`, `Basic ...`).
  - Password fields and tokens in URLs and payload bodies.
- Matches are sanitized to `[REDACTED_API_KEY]`, `[REDACTED_TOKEN]`, or `[REDACTED_SECRET]`.

---

### 6. Production Observability: Metrics & Tracing

#### 6.1 Prometheus Metrics (`travelguard/observability.py` & `backend/app/api/metrics.py`)
Metrics exported at `/api/metrics`:
- `travelguard_runs_total`: Counter partitioned by status (`PASS`, `PASS_WITH_HEALING`, `REAL_DEFECT`, `BLOCKED`).
- `travelguard_quality_gate_decision_total`: Counter of gate actions (`ALLOW_RELEASE`, `BLOCK_RELEASE`).
- `travelguard_release_confidence`: Gauge tracking confidence distribution across runs.
- `travelguard_tests_healed_total`: Counter tracking self-healed tests.
- `travelguard_defects_detected_total`: Counter tracking caught product defects.

#### 6.2 Grafana Quality Dashboard (`observability/grafana/dashboard.json`)
Pre-configured dashboard tracking:
- Release Decision Distribution (pie chart).
- Release Confidence Trends over time.
- Automated Self-Healing Rate vs. Real Defect Frequency.
- Test Failure Classification Breakdown.

#### 6.3 OpenTelemetry Distributed Tracing
Spans created for each pipeline phase:
- `travelguard.change_detection`
- `travelguard.test_selection`
- `travelguard.test_execution`
- `travelguard.failure_diagnosis`
- `travelguard.self_healing`
- `travelguard.quality_gate_evaluation`

---

### 7. Continuous Integration Workflow (`.github/workflows/qa.yml`)

The production GitHub Actions workflow:
1. Checks out repository with full git history.
2. Sets up Python 3.12 and Node.js 20.
3. Installs backend dependencies and Playwright browser binaries.
4. Executes unit & intelligence test suites (140 tests).
5. Boots SkyBook SUT (FastAPI backend + Vite frontend) in the background.
6. Runs `travelguard autonomous-run --quality-gate`.
7. Fails the build if the Quality Gate returns non-zero exit code.
8. Uploads quality gate reports and healing audit logs as workflow artifacts.

---

### 8. Verification & Test Metrics
- **Automated Tests**: 140 passing tests across `travelguard/tests` and `backend/tests`.
- **Demo Scenarios Validated**:
  - `booking-ui-drift`: Exit code 0, status `PASS_WITH_HEALING`, confidence 95%.
  - `booking-api-defect`: Exit code 2, status `REAL_DEFECT`, confidence 0%.
  - `environment-failure`: Exit code 3, status `BLOCKED`, confidence 0%.
