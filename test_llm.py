# test_llm.py
# Tests that Gemini API is working

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")

print(f"API key loaded: {api_key[:10]}...")

# Create Gemini client
client = genai.Client(api_key=api_key)

# Send test request
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello and tell me you are working!"
)

print(f"\nGemini says: {response.text}")
print("\n✅ Gemini is connected and working!")