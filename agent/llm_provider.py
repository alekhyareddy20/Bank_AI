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
    DEFAULT_MODEL = "llama-3.2-11b-vision-preview"
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
    DESCRIBE_PROMPT = """You are a screen reader for an AI agent.
Describe: 1) what page is shown, 2) visible form fields and buttons, 3) important text.
Be brief. Example: "Login page. Username field, Password field, Login button."
"""
    def __init__(self):
        super().__init__(model="two-model")
        _map = {"groq": GroqProvider, "gemini": GeminiProvider, "huggingface": HuggingFaceProvider, "hf": HuggingFaceProvider}
        vision_provider   = os.getenv("VISION_PROVIDER", "groq").lower()
        vision_model      = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        decision_provider = os.getenv("DECISION_PROVIDER", "groq").lower()
        decision_model    = os.getenv("DECISION_MODEL", "openai/gpt-oss-20b")
        print(f"  ✓ Two-model: vision={vision_provider}/{vision_model}, decision={decision_provider}/{decision_model}")
        self.vision   = _map[vision_provider](model=vision_model)
        self.decision = _map[decision_provider](model=decision_model)

    def ask(self, screenshot_b64, page_text, system_prompt, user_prompt):
        try:
            desc = self.vision.ask(screenshot_b64, page_text, self.DESCRIBE_PROMPT, "Describe this screen.")
            description = desc.get("description", str(desc)) if isinstance(desc, dict) else str(desc)
        except Exception as e:
            description = f"(vision failed: {e})\n{page_text[:400]}"
        enriched = f"{user_prompt}\n\nSCREEN: {description}\n\nPAGE TEXT: {page_text[:600]}"
        return self.decision.ask("", page_text, system_prompt, enriched)


def create_llm_provider():
    """Read LLM_PROVIDER from .env and return the right provider."""
    name  = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL", None)
    if name in ("two_model", "two-model"):
        return TwoModelProvider()
    providers = {"groq": GroqProvider, "gemini": GeminiProvider, "huggingface": HuggingFaceProvider, "hf": HuggingFaceProvider}
    if name not in providers:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Choose: {list(providers.keys()) + ['two_model']}")
    return providers[name](model=model)