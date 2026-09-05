# TravelGuard AI — Autonomous QA Platform
## Increment 1: SkyBook SUT & Foundation

---

### 1. What SkyBook Is
**SkyBook** is a lightweight, fully functional travel booking web application that serves as the controlled **System Under Test (SUT)** for **TravelGuard AI**. It represents a realistic travel business workflow:

$$\text{Flight Search} \longrightarrow \text{Flight Results} \longrightarrow \text{Select Flight} \longrightarrow \text{Passenger Details} \longrightarrow \text{Book Flight} \longrightarrow \text{Booking Confirmation}$$

---

### 2. What TravelGuard AI Will Eventually Become
**TravelGuard AI** is conceived as an **Autonomous QA Engineer for AI-driven travel applications**. Across subsequent increments, TravelGuard AI will:
1. **Detect application changes** (Git diffs, DOM updates, API changes).
2. **Understand affected business workflows** via multi-modal intent reasoning.
3. **Generate and prioritize tests** based on risk and critical user journeys.
4. **Execute UI, API, security, accessibility, and performance tests**.
5. **Self-heal broken test automation** when locators or UI flows change.
6. **Distinguish test drift from real product defects**.
7. **Produce explainable quality insights**.
8. **Make informed release decisions**.

---

### 3. Why SkyBook Exists
Automated QA systems and self-healing algorithms cannot be reliably trained, verified, or benchmarked without a stable, reproducible, and intentionally modifiable baseline. SkyBook provides this exact testbed:
- Consistent mock inventory and deterministic booking responses.
- Explicit `data-testid` hooks alongside semantic, accessible HTML.
- Known error pathways (input validation, network failure states).
- A clean platform against which future mutations and self-healing tests will be applied.

---

### 4. Current Increment 1 Scope
In Increment 1, we focus solely on building the **foundation**:
- [x] Working SkyBook frontend (React + TypeScript + Vite).
- [x] Simple FastAPI backend with deterministic endpoints (`/api/flights`, `/api/book`, `/api/health`).
- [x] Baseline Playwright E2E test suite (Search, Select, Book, Validation, API Health).
- [x] Multi-provider LLM abstraction (Primary: DeepSeek, Fallback: Groq).
- [x] Observable fallback logging and LLM diagnostic endpoint (`/api/llm/health`).
- [x] Zero advanced autonomous features yet (no AI drift, no auto-repair, no premature complexity).

---

### 5. System Architecture

```
amadeus_hack/
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
│   │   ├── llm/                  # Provider abstraction (DeepSeek, Groq, Router)
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
├── .env.example                  # Environment configuration template
├── .gitignore                    # Secrets and build ignore rules
└── README.md
```

---

### 6. How to Install Dependencies

#### Prerequisites
- Node.js `>= 18` (v20+ recommended)
- Python `>= 3.10` (Python 3.13 tested)
- npm `>= 9`

#### 1. Setup Backend
```bash
# In project root:
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

#### 2. Setup Frontend
```bash
cd frontend
npm install
cd ..
```

#### 3. Setup Playwright Tests
```bash
cd tests
npm install
npx playwright install chromium
cd ..
```

---

### 7. How to Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure your LLM provider credentials in `.env`:
```ini
# Primary LLM: DeepSeek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Fallback LLM: Groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1

# Ports
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

> [!NOTE]
> `.env` is gitignored. Do not commit actual API keys to source control.

---

### 8. How to Start the Backend
From the project root:
```bash
./backend/.venv/bin/python backend/run.py
```
Or with uvicorn directly:
```bash
./backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```
The backend will be available at `http://localhost:8000`.
API documentation is automatically available at `http://localhost:8000/docs`.

---

### 9. How to Start the Frontend
In a separate terminal tab:
```bash
cd frontend
npm run dev
```
The SkyBook frontend will open at `http://localhost:5173`.

---

### 10. How to Run Playwright Tests
Ensure the backend (`http://localhost:8000`) and frontend (`http://localhost:5173`) are running.

Then, execute the baseline suite:
```bash
cd tests
npm test
```

To run individual tests:
```bash
npx playwright test e2e/booking.spec.ts
```

To run with visual browser UI:
```bash
npx playwright test --headed
```

---

### 11. How to Test the LLM Provider
A dedicated diagnostic endpoint is provided at `GET /api/llm/health`.

Using `curl`:
```bash
curl -s http://localhost:8000/api/llm/health
```

#### Expected Responses

**When DeepSeek is active and configured:**
```json
{
  "success": true,
  "provider": "deepseek",
  "model": "deepseek-v4-flash"
}
```

**When DeepSeek fails (or has invalid credentials) and Groq succeeds:**
```json
{
  "success": true,
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "fallback_used": true
}
```

**When neither provider has configured API keys:**
```json
{
  "success": false,
  "error": "Primary (deepseek) failed: DEEPSEEK_API_KEY is not set or empty. Fallback (groq) failed: GROQ_API_KEY is not set or empty"
}
```

---

### 12. How DeepSeek → Groq Fallback Works

The LLM abstraction uses a two-tier strategy orchestrated by `LLMService` (`backend/app/llm/router.py`):

1. **Attempt Primary (`DeepSeekProvider`)**:
   - Sends the prompt to `https://api.deepseek.com/chat/completions` using `DEEPSEEK_MODEL`.
   - Logs:
     ```
     [LLM] Primary provider: DeepSeek
     [LLM] Model: deepseek-v4-flash
     ```
2. **Handle Failure & Failover**:
   - If DeepSeek encounters an authentication error, rate limit, timeout, or network failure:
     ```
     [LLM] Request failed: <error details>
     [LLM] Falling back to Groq
     [LLM] Model: llama-3.3-70b-versatile
     ```
3. **Execute Secondary (`GroqProvider`)**:
   - Sends the request to Groq's high-speed API (`https://api.groq.com/openai/v1/chat/completions`).
   - Marks `fallback_used: true` on the normalized `LLMResponse`.
   - Logs:
     ```
     [LLM] Success (fallback: groq)
     ```
4. **Resilience & Security**:
   - All errors are formatted cleanly without exposing raw authorization headers or keys.
   - Provider models are completely configurable via environment variables without code modification.
