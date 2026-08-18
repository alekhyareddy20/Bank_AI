# test_all_models.py
# Tests every model and shows which ones work for our bank task

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

PAGE_TEXT = """BankCore Legacy System v2.3
OPERATOR LOGIN
Username: Password: Login"""

GOAL = "Log in with username admin and password password123"

PROMPT = f"""
You are an AI agent operating a web application.
GOAL: {GOAL}
PAGE TEXT: {PAGE_TEXT}

Reply ONLY with this JSON:
{{
  "reasoning": "what you see and why",
  "action": "click OR type OR read OR done",
  "element": "describe the element",
  "value": "text to type if action is type, else null",
  "is_done": false
}}
"""

results = []

def test_model(provider, model_name, fn):
    print(f"\nTesting {provider} — {model_name}...")
    start = time.time()
    try:
        response = fn()
        elapsed = round(time.time() - start, 2)
        print(f"  ✅ Works! ({elapsed}s)")
        print(f"  Response: {str(response)[:120]}")
        results.append({
            "provider": provider,
            "model": model_name,
            "status": "✅ works",
            "speed": f"{elapsed}s",
            "response": str(response)[:100]
        })
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        print(f"  ❌ Failed: {str(e)[:100]}")
        results.append({
            "provider": provider,
            "model": model_name,
            "status": "❌ failed",
            "speed": f"{elapsed}s",
            "response": str(e)[:100]
        })


# ── GROQ MODELS ───────────────────────────────────────────────
GROQ_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def test_groq(model):
    def fn():
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": PROMPT}],
                  "temperature": 0.1, "max_tokens": 300},
            timeout=30
        )
        if r.status_code != 200:
            raise Exception(f"Status {r.status_code}: {r.text[:100]}")
        return r.json()["choices"][0]["message"]["content"][:100]
    return fn

if GROQ_KEY:
    test_model("Groq", "qwen/qwen3.6-27b",   test_groq("qwen/qwen3.6-27b"))
    test_model("Groq", "groq/compound-mini",  test_groq("groq/compound-mini"))
    test_model("Groq", "openai/gpt-oss-20b",  test_groq("openai/gpt-oss-20b"))
else:
    print("\n⚠️  No GROQ_API_KEY in .env — skipping Groq models")


# ── HUGGINGFACE MODELS ────────────────────────────────────────
HF_KEY = os.getenv("HUGGINGFACE_API_KEY")
HF_BASE = "https://api-inference.huggingface.co/models"

def test_hf(model):
    def fn():
        r = requests.post(
            f"{HF_BASE}/{model}",
            headers={"Authorization": f"Bearer {HF_KEY}"},
            json={"inputs": PROMPT, "parameters": {"max_new_tokens": 200, "return_full_text": False}},
            timeout=60
        )
        if r.status_code == 503:
            raise Exception("Model loading (503) — try again in 30s")
        if r.status_code != 200:
            raise Exception(f"Status {r.status_code}: {r.text[:100]}")
        result = r.json()
        if isinstance(result, list):
            return result[0].get("generated_text", "")[:100]
        return str(result)[:100]
    return fn

if HF_KEY:
    test_model("HuggingFace", "mistralai/Mistral-7B-Instruct-v0.3", test_hf("mistralai/Mistral-7B-Instruct-v0.3"))
    test_model("HuggingFace", "HuggingFaceH4/zephyr-7b-beta",       test_hf("HuggingFaceH4/zephyr-7b-beta"))
else:
    print("\n⚠️  No HUGGINGFACE_API_KEY in .env — skipping HuggingFace models")


# ── GEMINI MODELS ─────────────────────────────────────────────
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def test_gemini(model):
    def fn():
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        r = client.models.generate_content(model=model, contents=PROMPT)
        return r.text[:100]
    return fn

if GEMINI_KEY:
    test_model("Gemini", "gemini-3.6-flash", test_gemini("gemini-3.6-flash"))
    test_model("Gemini", "gemini-3.7-flash", test_gemini("gemini-3.7-flash"))
else:
    print("\n⚠️  No GEMINI_API_KEY in .env — skipping Gemini models")


# ── SUMMARY TABLE ─────────────────────────────────────────────
print("\n\n" + "="*60)
print("MODEL COMPARISON RESULTS")
print("="*60)
print(f"{'Provider':<15} {'Model':<35} {'Status':<12} {'Speed'}")
print("-"*60)
for r in results:
    print(f"{r['provider']:<15} {r['model']:<35} {r['status']:<12} {r['speed']}")
print("="*60)