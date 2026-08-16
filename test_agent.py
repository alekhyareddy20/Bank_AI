# test_agent.py
# Full loop: Observe → Decide → Act → Repeat

import os
import json
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask_gemini(screenshot_path, goal, page_text, steps_so_far):
    with open(screenshot_path, "rb") as f:
        image_data = f.read()

    history = "\n".join([
        f"Step {i+1}: {s['action']} on {s['element']}"
        for i, s in enumerate(steps_so_far)
    ])

    prompt = f"""
You are an AI agent operating a web application.

GOAL: {goal}

STEPS TAKEN SO FAR:
{history if history else "None yet"}

PAGE TEXT:
{page_text}

What is the next single action to take?
Reply with ONLY this JSON:

{{
  "reasoning": "what you see and why",
  "action": "click OR type OR read OR done",
  "element": "describe the element",
  "value": "text to type if action is type, else null",
  "is_done": false
}}

Set is_done to true when the GOAL is fully complete.
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Content(parts=[
                types.Part(text=prompt),
                types.Part(inline_data=types.Blob(
                    mime_type="image/png",
                    data=image_data
                ))
            ])
        ]
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return json.loads(text)


def execute_action(page, action):
    act = action.get("action")
    element = action.get("element", "")
    value = action.get("value")

    if act == "type":
        if "username" in element.lower():
            page.get_by_placeholder("Username").fill(value)
        elif "password" in element.lower():
            page.get_by_placeholder("Password").fill(value)
        elif "member" in element.lower():
            page.get_by_placeholder("Enter Member ID").fill(value)
        print(f"  ✓ Typed '{value}' into {element}")

    elif act == "click":
        if "login" in element.lower():
            page.get_by_role("button", name="Login").click()
        elif "search" in element.lower():
            page.get_by_role("button", name="Search Member").click()
        page.wait_for_timeout(1000)
        print(f"  ✓ Clicked {element}")

    elif act == "read":
        text = page.inner_text("body")
        print(f"  ✓ Read page: {text[:200]}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://127.0.0.1:5000")

    goal = "Log in with username admin and password password123, then search for member 12345 and find their savings balance"
    steps_done = []

    print(f"GOAL: {goal}\n")

    for step_num in range(10):
        print(f"\n--- Step {step_num + 1} ---")

        page.screenshot(path="current_state.png")
        page_text = page.inner_text("body")

        action = ask_gemini("current_state.png", goal, page_text, steps_done)

        print(f"  Gemini: {action['reasoning'][:80]}")
        print(f"  Action: {action['action']} → {action['element']}")

        if action.get("is_done"):
            print("\n✅ GOAL COMPLETE!")
            break

        execute_action(page, action)
        steps_done.append(action)

    page.wait_for_timeout(3000)
    browser.close()