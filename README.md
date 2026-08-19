# Computer Use Automation System
### AI Agent that operates a legacy bank web application — records steps, replays without AI

The agent logs into a fake legacy bank, looks up a member's savings balance, saves the steps as a reusable JSON artifact, and replays them deterministically — no AI needed on replay.

---

## What This Does

```
┌─────────────────────────────────────────────────────┐
│  DISCOVERY MODE (AI-powered)                         │
│                                                      │
│  Browser opens → AI watches screen → AI decides     │
│  what to click/type → executes action → repeats     │
│  until goal is complete → saves Artifact JSON        │
└──────────────────────┬──────────────────────────────┘
                       │ saves
                       ▼
            artifacts/lookup_member_balance.json
                       │
                       │ replay with any member ID
                       ▼
┌─────────────────────────────────────────────────────┐
│  REPLAY MODE (no AI — deterministic)                 │
│                                                      │
│  Reads artifact steps → executes in browser →       │
│  returns balance → handles errors (member not found, │
│  frozen account, network failures)                   │
└─────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Bank_AI/
├── main.py                    # Single entry point (discover / replay / bank / operator)
├── test_agent.py              # Standalone agent loop for testing different LLMs
├── .env                       # Your API keys and model selection (not committed)
├── .env.example               # Template — copy this to .env
│
├── agent/
│   ├── llm_provider.py        # Multi-LLM abstraction (Groq, Gemini, HuggingFace)
│   ├── discovery.py           # Full AI discovery agent loop
│   ├── replay.py              # Deterministic replay engine with guardrails
│   ├── artifact.py            # Artifact JSON schema and save/load
│   ├── guardrails.py          # URL allowlist, risky page detection, redaction
│   └── escalation.py         # Human handoff — pause/resume for operator review
│
├── target_app/
│   └── app.py                 # Fake legacy bank (Flask) — intentionally ugly, no test IDs
│
├── artifacts/
│   └── lookup_member_balance_*.json   # Saved recording — replay runs from here
│
├── evidence/
│   └── step_001.png, step_002.png…    # Screenshots taken at each agent step
│
└── tests.py                   # 18 tests — discovery, replay, guardrails, escalation
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Set up your API keys
cp .env.example .env
# Edit .env — add your GROQ_API_KEY (free at https://console.groq.com)

# 3. Start the fake bank (Terminal 1)
python main.py bank

# 4. Run the AI agent (Terminal 2)
python test_agent.py

# 5. Replay the saved artifact
python main.py replay artifacts/lookup_member_balance_*.json member_id=12345
python main.py replay artifacts/lookup_member_balance_*.json member_id=67890
python main.py replay artifacts/lookup_member_balance_*.json member_id=99999  # not found

# 6. Run all tests
python tests.py
```

---

## The LLM Journey — What I Tried and Why I Changed

### Stage 1 — Gemini (started here, hit problems fast)

The project started with **Google Gemini** (`gemini-1.5-flash`). Gemini is a vision model — it can actually *see* screenshots, not just read text. That makes it ideal for legacy apps with no clean HTML structure.

**Problem:** Gemini's free tier kept returning:
```
503 UNAVAILABLE — This model is currently experiencing high demand.
```
And when it did work, each step took **8–12 seconds**. A 7-step task took nearly 2 minutes. Not practical.

**Config that caused problems:**
```
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash
```

---

### Stage 2 — Single Groq model (fast, reliable, text-only)

Switched to **Groq** with `openai/gpt-oss-20b`. Groq's inference is dramatically faster — the same 7-step task completed in under 10 seconds total.

The trade-off: this model is text-only (no screenshots). Instead of looking at the page visually, it reads all the visible text on the page. For a structured legacy bank app, the page text contains everything needed — form labels, button names, member data.

**Result: 7 steps, ~0.75s per step, 100% reliable.**

```
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
```

Step-by-step output:
```
Step 1 — type → Username field       0.75s  ✓
Step 2 — type → Password field       0.68s  ✓
Step 3 — click → Login button        0.71s  ✓
Step 4 — type → Member ID field      0.79s  ✓
Step 5 — click → Search button       0.73s  ✓
Step 6 — read → Savings Balance      0.69s  ✓
Step 7 — done                        0.75s  ✓  $5,432.10
```

---

### Stage 3 — Two-model setup (best understanding)

The insight: what if one model *describes* the page and a second model *decides* the action? The first model focuses entirely on understanding the current state. The second focuses entirely on what to do next — with a clean structured summary instead of raw page text.

**First attempt — qwen/qwen3.6-27b as analyzer:**

```
VISION_MODEL=qwen/qwen3.6-27b       ← analyzer (smarter)
DECISION_MODEL=openai/gpt-oss-20b   ← decider (fastest)
```

Problem: qwen outputs `<think>...</think>` reasoning blocks before its JSON — broke the parser. Also hit Groq's rate limit after 2–3 calls. Fixed the think-tag stripping but the rate limit made it unreliable.

**Final config — gpt-oss-120b as analyzer (recommended):**

```
LLM_PROVIDER=two_model
VISION_PROVIDER=groq
VISION_MODEL=openai/gpt-oss-120b     ← 6× bigger, richer page analysis
DECISION_PROVIDER=groq
DECISION_MODEL=openai/gpt-oss-20b    ← fastest decider stays the same
```

This worked cleanly. The 120b analyzer gave structured, detailed page analysis:
```
[analyzer 0.79s] Page: login | Operator login page | Fields: Username, Password | Buttons: Login
[analyzer 0.86s] Page: member_search | Member search page | Fields: Member ID | Buttons: Search Member
[analyzer 0.71s] Page: member_details | Alice Johnson's account | Data: Savings: $5,432.10
```

The analyzer understood it was looking at Alice Johnson's account and knew her balance before the decider even chose an action. That richer context leads to better, more confident decisions.

---

## Model Comparison

| Setup | Model(s) | Speed/step | Vision | Reliability | Verdict |
|---|---|---|---|---|---|
| Gemini single | gemini-1.5-flash | ~10s | ✅ sees screenshots | ❌ 503 errors | Too slow & unreliable |
| Groq single | gpt-oss-20b | ~0.75s | ❌ text-only | ✅ Solid | Fast, good for simple pages |
| Groq two-model (qwen) | qwen + gpt-oss-20b | ~2.8s | ❌ text-only | ⚠️ Rate limits | Hit quota too fast |
| **Groq two-model** ✅ | **gpt-oss-120b + gpt-oss-20b** | **~1.3s** | **❌ text-only** | **✅ Solid** | **Best understanding** |

**Winner: Two-model with gpt-oss-120b analyzer + gpt-oss-20b decider.**

Even though it is slightly slower than the single model (~1.3s vs ~0.75s per step), the structured page analysis gives the decider much richer context. On complex pages with multiple sections, error states, or dynamic content, that understanding difference is critical. The decider always knows exactly what page it is on, what fields are visible, and what data is present — before making any decision.

---

## How the Two-Model Architecture Works

```
                     PAGE TEXT
                        │
          ┌─────────────▼──────────────┐
          │     ANALYZER MODEL         │
          │   (gpt-oss-120b — smarter) │
          │                            │
          │  "Page: member_details     │
          │   Fields: Savings Balance  │
          │   Data: Alice, $5,432.10"  │
          └─────────────┬──────────────┘
                        │ structured description
          ┌─────────────▼──────────────┐
          │     DECIDER MODEL          │
          │   (gpt-oss-20b — fastest)  │
          │                            │
          │  {"action": "done",        │
          │   "is_done": true,         │
          │   "extracted_data": {...}} │
          └────────────────────────────┘
```

---

## How the Artifact System Works

After the agent completes a run, it saves a JSON artifact:

```json
{
  "capability_name": "lookup_member_balance",
  "goal": "Log in and look up a member savings balance",
  "steps": [
    { "action": "navigate", "url": "http://127.0.0.1:5000" },
    { "action": "type", "locator": { "strategy": "placeholder", "value": "Username" }, "value": "admin" },
    { "action": "type", "locator": { "strategy": "placeholder", "value": "Password" }, "value": "password123" },
    { "action": "click", "locator": { "strategy": "text", "value": "Login" } },
    { "action": "type", "locator": { "strategy": "placeholder", "value": "Enter Member ID" }, "value": "{{member_id}}" },
    { "action": "click", "locator": { "strategy": "text", "value": "Search Member" } },
    { "action": "read", "locator": { "strategy": "text", "value": "Savings Balance" }, "extract_as": "savings_balance" }
  ]
}
```

`{{member_id}}` is a placeholder — replay fills it with any real member ID at runtime. One recorded run works for all members.

---

## Error Handling

| Outcome | Example | What happens |
|---|---|---|
| `success` | Member 12345 found | Returns `{"savings_balance": "$5,432.10"}` |
| `business_outcome` | Member 99999 not found | Returns outcome message, no crash |
| `hard_failure` | Network error, page changed | Saves screenshot, triggers escalation |

---

## Guardrails

- **URL allowlist** — only `127.0.0.1:5000` is allowed; any other URL is blocked
- **Risky page detection** — transfer/confirm pages require human approval before proceeding
- **Password redaction** — credentials are never written to logs or artifacts
- **Step logging** — every action logged safely, sensitive values replaced with `[REDACTED]`

---

## Tests

```bash
python tests.py
# Ran 18 tests in 3.4s — OK
```

Covers artifact creation, replay with all member types, guardrail enforcement, escalation flow, and error handling.

---

## Tech Stack

| Component | Technology |
|---|---|
| Browser automation | Playwright (Python) |
| AI providers | Groq API (primary), Google Gemini (fallback) |
| Target app | Flask (fake legacy bank) |
| Operator console | FastAPI + HTML |
| Tests | Python unittest |

---

## Free API Keys (all used in this project)

| Provider | Free limit | Get key |
|---|---|---|
| Groq | Thousands of requests/day | https://console.groq.com |
| Google Gemini | 1,500 requests/day | https://aistudio.google.com |
| HuggingFace | Limited | https://huggingface.co → Settings → Access Tokens |

---

*Built by Alekhya Kodumuru*
