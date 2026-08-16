# test_agent.py
import os
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask_gemini(screenshot_path, goal, page_text):
    with open(screenshot_path, "rb") as f:
        image_data = f.read()

    prompt = f"""
You are an AI agent operating a web application.

GOAL: {goal}

PAGE TEXT (what is visible on screen):
{page_text}

Look at the screenshot and tell me what single action to take next.
Reply with ONLY this JSON format, nothing else:

{{
  "reasoning": "what you see and why you are doing this",
  "action": "click OR type OR read",
  "element": "describe the button or field to interact with",
  "value": "text to type (only if action is type, else null)"
}}
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

    print(f"\nGemini says:\n{response.text}")
    return response.text


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    print("Going to bank login page...")
    page.goto("http://127.0.0.1:5000")
    page.screenshot(path="current_state.png")

    page_text = page.inner_text("body")
    print(f"Page text: {page_text[:100]}")

    print("\nAsking Gemini what to do next...")
    ask_gemini(
        screenshot_path="current_state.png",
        goal="Log in using username admin and password password123",
        page_text=page_text
    )

    page.wait_for_timeout(3000)
    browser.close()


# model="gemini-3.6-flash",
#     n test_agent.py
# Going to bank login page...
# Page text: BankCore Legacy System v2.3

# Authorized Personnel Only



# OPERATOR LOGIN
# Username:
# Password:


# Asking Gemini what to do next...
# Direct use of automatic function calling (AFC) in Models.generate_content is not recommended. Instead, we recommend to use AFC in Chat.send_message. Similarly, direct use of AFC in Models.generate_content_stream is not recommended. Instead, we recommend to use AFC in Chat.send_message_stream.

# Gemini says:
# ```json
# {
#   "reasoning": "To achieve the goal of logging in, the first action required is entering the username into the designated input field.",
#   "action": "type",
#   "element": "Username input field",
#   "value": "admin"
# }