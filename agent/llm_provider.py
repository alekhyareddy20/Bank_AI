# agent/llm_provider.py

import os
import json
import requests
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    def __init__(self, model=None):
        self.model = model

    @abstractmethod
    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        pass

    def _clean_json(self, raw_text):
        text = raw_text.strip()

        # Strip <think>...</think> blocks (qwen and some models reason out loud)
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except Exception:
                    pass
            raise ValueError(f"Could not parse JSON.\nRaw: {text[:400]}")


class GroqProvider(BaseLLMProvider):
    DEFAULT_MODEL = "openai/gpt-oss-20b"
    API_URL       = "https://api.groq.com/openai/v1/chat/completions"
    VISION_MODELS = {
        "llama-3.2-11b-vision-preview",
        "llama-3.2-90b-vision-preview",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
    }

    def __init__(self, model=None):
        super().__init__(model or self.DEFAULT_MODEL)
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in .env!\nGet key: https://console.groq.com")
        self.has_vision = self.model in self.VISION_MODELS
        print(f"  ✓ Groq ({self.model}) — {'vision ✅' if self.has_vision else 'text-only'}")

    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        if self.has_vision and screenshot_b64:
            user_content = [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                {"type": "text", "text": f"{user_prompt}\n\nReply ONLY with valid JSON."}
            ]
        else:
            user_content = f"Page text:\n{page_text}\n\n{user_prompt}\n\nReply ONLY with valid JSON."

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens":  1000,
        }
        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Groq error {resp.status_code}: {resp.text[:300]}")
        return self._clean_json(resp.json()["choices"][0]["message"]["content"])


class GeminiProvider(BaseLLMProvider):
    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(self, model=None):
        super().__init__(model or self.DEFAULT_MODEL)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env!\nGet key: https://aistudio.google.com")
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.model)
        print(f"  ✓ Gemini ({self.model}) — vision ✅")

    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        image_part = {"mime_type": "image/png", "data": screenshot_b64}
        response = self._model.generate_content(
            [f"{system_prompt}\n\n{user_prompt}", image_part],
            generation_config={"temperature": 0.1}
        )
        return self._clean_json(response.text)


class HuggingFaceProvider(BaseLLMProvider):
    DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
    API_BASE      = "https://api-inference.huggingface.co/models"

    def __init__(self, model=None):
        super().__init__(model or self.DEFAULT_MODEL)
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY not found in .env!")
        print(f"  ✓ HuggingFace ({self.model}) — text-only")

    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        prompt = f"{system_prompt}\n\nPage text:\n{page_text}\n\n{user_prompt}\n\nRespond ONLY with valid JSON."
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 800, "temperature": 0.1, "return_full_text": False}}
        resp = requests.post(f"{self.API_BASE}/{self.model}", headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"HuggingFace error {resp.status_code}: {resp.text[:300]}")
        result = resp.json()
        raw_text = result[0].get("generated_text", "") if isinstance(result, list) else str(result)
        return self._clean_json(raw_text)


class TwoModelProvider(BaseLLMProvider):
    """
    Two-model setup — both on Groq (no vision needed):
      Analyzer: qwen/qwen3.6-27b      — smarter, reads page and describes state
      Decider:  openai/gpt-oss-20b    — fastest, reads description and picks action

    .env:
        LLM_PROVIDER=two_model
        VISION_PROVIDER=groq
        VISION_MODEL=qwen/qwen3.6-27b
        DECISION_PROVIDER=groq
        DECISION_MODEL=openai/gpt-oss-20b
    """

    ANALYZE_PROMPT = """You are a web page analyzer for an AI agent.
Read the page text and describe the current state.

Reply with ONLY this JSON (no markdown):
{
  "current_page": "login | member_search | member_details | transfer | other",
  "description": "one sentence — what page is shown",
  "visible_fields": "input fields visible e.g. Username, Password, Member ID",
  "visible_buttons": "buttons visible e.g. Login, Search Member",
  "key_data": "important data e.g. Member: Alice Johnson, Savings: $5432.10 — or empty string"
}"""

    def __init__(self):
        super().__init__(model="two-model")
        _map = {
            "groq":        GroqProvider,
            "gemini":      GeminiProvider,
            "huggingface": HuggingFaceProvider,
            "hf":          HuggingFaceProvider,
        }
        analyzer_provider = os.getenv("VISION_PROVIDER",   "groq").lower()
        analyzer_model    = os.getenv("VISION_MODEL",       "qwen/qwen3.6-27b")
        decider_provider  = os.getenv("DECISION_PROVIDER",  "groq").lower()
        decider_model     = os.getenv("DECISION_MODEL",     "openai/gpt-oss-20b")

        print(f"  ✓ Two-model setup:")
        print(f"    Analyzer: {analyzer_provider} / {analyzer_model}")
        self.analyzer = _map[analyzer_provider](model=analyzer_model)
        print(f"    Decider:  {decider_provider} / {decider_model}")
        self.decider  = _map[decider_provider](model=decider_model)

    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        import time

        # ── Step 1: Analyzer reads page and describes state ───────────────────
        t1 = time.time()
        try:
            analysis = self.analyzer.ask(
                screenshot_b64=screenshot_b64,
                page_text=page_text,
                system_prompt=self.ANALYZE_PROMPT,
                user_prompt=f"Analyze this page:\n{page_text[:1000]}",
            )
            if isinstance(analysis, dict):
                description = (
                    f"Page: {analysis.get('current_page','?')} | "
                    f"{analysis.get('description','')} | "
                    f"Fields: {analysis.get('visible_fields','')} | "
                    f"Buttons: {analysis.get('visible_buttons','')} | "
                    f"Data: {analysis.get('key_data','')}"
                )
            else:
                description = str(analysis)
        except Exception as e:
            description = f"(analysis failed: {e}) | raw: {page_text[:300]}"

        t2 = time.time()
        print(f"    [analyzer {t2-t1:.2f}s] {description[:90]}")

        # ── Step 2: Decider reads analysis and picks next action ──────────────
        enriched_prompt = f"""{user_prompt}

PAGE ANALYSIS (from analyzer):
{description}

RAW PAGE TEXT:
{page_text[:600]}
"""
        t3 = time.time()
        result = self.decider.ask(
            screenshot_b64="",
            page_text=page_text,
            system_prompt=system_prompt,
            user_prompt=enriched_prompt,
        )
        t4 = time.time()
        print(f"    [decider  {t4-t3:.2f}s]")
        return result


def create_llm_provider():
    """Read LLM_PROVIDER from .env and return the right provider."""
    name  = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL", None)

    if name in ("two_model", "two-model"):
        return TwoModelProvider()

    providers = {
        "groq":        GroqProvider,
        "gemini":      GeminiProvider,
        "huggingface": HuggingFaceProvider,
        "hf":          HuggingFaceProvider,
    }
    if name not in providers:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Choose: {list(providers.keys()) + ['two_model']}")
    return providers[name](model=model)

# OPERATOR LOGIN
# Usernam...
#   Asking LLM...     [analyzer 2.20s] (analysis failed: Could not parse JSON.
# Raw: <think>
# Thinking Process:
# 1.  **Analyze User 
#     [decider  0.57s]
# done
#   Reasoning: After entering the username and password, the next step is to submit the lo
#   Action:    click → Login button
#   Result:    Clicked 'Login button'
# ───────────────────────────────────────────────────────
#   Step 4/12
#   Page: BankCore Legacy System v2.3
#         Logout

# MEMBER SEARCH
# Member ID:...
#   Asking LLM...     [analyzer 2.13s] (analysis failed: Could not parse JSON.
# Raw: <think>
# Thinking Process:
# 1.  **Analyze User 
#     [decider  0.47s]
# done
#   Reasoning: After logging in, the user is on the Member Search page. The next step is t
#   Action:    type → Member ID field
#   Result:    Typed '12345' into 'Member ID field'
# ───────────────────────────────────────────────────────
#   Step 5/12
#   Page: BankCore Legacy System v2.3
#         Logout

# MEMBER SEARCH
# Member ID:...
#   Asking LLM...     [analyzer 0.16s] (analysis failed: Groq error 429: {"error":{"message":"Rate limit reached for model `qwen/
#     [decider  0.49s]
# done
#   Reasoning: After entering the member ID, the next step is to submit the search query b
#   Action:    click → Search button next to Member ID field
#   Result:    Clicked 'Search button next to MemberID field'
# ───────────────────────────────────────────────────────
#   Step 6/12
#   Page: BankCore Legacy System v2.3
#         Back to Search | Logout

# MEMBER DETAILS — ID: 12345...
#   Asking LLM...     [analyzer 0.17s] (analysis failed: Groq error 429: {"error":{"message":"Rate limit reached for model `qwen/
#     [decider  0.41s]
# done
#   Reasoning: After searching for member 12345, themember details page is displayed. The
#   Action:    read → Savings Balance field
#   Result:    Read page (232 chars)
# ───────────────────────────────────────────────────────
#   Step 7/12
#   Page: BankCore Legacy System v2.3
#         Back to Search | Logout

# MEMBER DETAILS — ID: 12345...
#   Asking LLM...     [analyzer 0.13s] (analysis failed: Groq error 429: {"error":{"message":"Rate limit reached for model `qwen/
#     [decider  0.61s]
# done
#   Reasoning: All steps to log in, search for member 12345, and read the savings balance 
#   Action:    done → None

#   ✅ GOAL COMPLETE!
#   Extracted: {'savings_balance': '$5,432.10'}

# ═══════════════════════════════════════════════════════
#   Steps taken: 6
#   savings_balance: $5,432.10
# ═══════════════════════════════════════════════════════