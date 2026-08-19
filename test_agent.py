#!/usr/bin/env python3
# test_agent.py — Observe → Decide → Act loop

import os
import sys
import base64
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# ── CRITICAL: tell Python where to find llm_provider.py ──────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)                          # adds Bank_AI/
sys.path.insert(0, os.path.join(_here, "agent"))   # adds Bank_AI/agent/

load_dotenv()

from llm_provider import create_llm_provider

# ── Import artifact classes via the agent package ─────────────────────────────
import agent.artifact as _art_mod
Artifact   = _art_mod.Artifact
ActionStep = _art_mod.ActionStep
Locator    = _art_mod.Locator

# ─────────────────────────────────────────────────────────────────────────────
BANK_URL  = "http://127.0.0.1:5000"
GOAL      = "Log in with username admin and password password123, then search for member 12345 and find their savings balance"
MAX_STEPS = 12

SYSTEM_PROMPT = """
You are an AI agent operating a legacy web banking application.
Reply with ONLY valid JSON — no markdown, no explanation outside the JSON:

{
  "reasoning": "what you see and why you are taking this action",
  "action": "click | type | read | done",
  "element": "describe the element to interact with",
  "value": "text to type (only when action is type, else null)",
  "is_done": false,
  "extracted_data": null
}

Set is_done = true and fill extracted_data when the GOAL is fully complete.
Example: "extracted_data": {"savings_balance": "$5,432.10"}
"""

# ─────────────────────────────────────────────────────────────────────────────
def observe(page, step_num):
    os.makedirs("evidence", exist_ok=True)
    screenshot_path = f"evidence/step_{step_num:03d}.png"
    page.screenshot(path=screenshot_path, full_page=True)
    with open(screenshot_path, "rb") as f:
        screenshot_b64 = base64.b64encode(f.read()).decode()
    page_text = page.inner_text("body")
    return screenshot_b64, page_text


def execute_action(page, action):
    act     = action.get("action", "")
    element = action.get("element", "")
    value   = action.get("value")

    if act == "type":
        filled = False
        for placeholder in ["Username", "Password", "Enter Member ID", "Member ID"]:
            if placeholder.lower() in element.lower() or element.lower() in placeholder.lower():
                try:
                    page.get_by_placeholder(placeholder).fill(value)
                    filled = True
                    break
                except Exception:
                    pass
        if not filled:
            try:
                page.locator("input:visible").first.fill(value)
            except Exception as e:
                return f"TYPE FAILED: {e}"
        return f"Typed '{value}' into '{element}'"

    elif act == "click":
        clicked = False

        # Strategy 1: find a button whose text contains any word from element description
        element_words = [w.lower() for w in element.split() if len(w) > 2]
        all_buttons = page.get_by_role("button").all()
        for btn in all_buttons:
            try:
                btn_text = btn.inner_text().strip().lower()
                if any(word in btn_text for word in element_words):
                    btn.click()
                    page.wait_for_timeout(1200)
                    clicked = True
                    break
            except Exception:
                pass

        # Strategy 2: click any visible element containing that text
        if not clicked:
            try:
                page.locator(f"button, input[type=submit], a").filter(has_text=element.split()[0]).first.click()
                page.wait_for_timeout(1200)
                clicked = True
            except Exception:
                pass

        # Strategy 3: click by full text match
        if not clicked:
            try:
                page.get_by_text(element, exact=False).first.click()
                page.wait_for_timeout(1200)
                clicked = True
            except Exception as e:
                return f"CLICK FAILED: {e}"

        return f"Clicked '{element}'"

    elif act == "read":
        return f"Read page ({len(page.inner_text('body'))} chars)"

    elif act == "done":
        return "Done"

    return f"Unknown action '{act}'"


# ─────────────────────────────────────────────────────────────────────────────
def run_agent():
    print("\n" + "═"*55)
    print("  COMPUTER USE AGENT")
    print("═"*55)
    print(f"  Goal: {GOAL}\n")

    llm = create_llm_provider()
    print()

    steps_done   = []
    final_result = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page    = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BANK_URL)
        page.wait_for_load_state("networkidle")
        print(f"  Browser opened → {BANK_URL}\n")

        for step_num in range(1, MAX_STEPS + 1):
            print(f"{'─'*55}")
            print(f"  Step {step_num}/{MAX_STEPS}")

            screenshot_b64, page_text = observe(page, step_num)
            print(f"  Page: {page_text[:80].strip()}...")

            history = "\n".join(
                f"  Step {i+1}: {s['action']} → {s['element']}"
                for i, s in enumerate(steps_done)
            ) or "  (none yet)"

            user_prompt = f"""
GOAL: {GOAL}

STEPS ALREADY DONE:
{history}

What is the next single action? Reply ONLY with valid JSON.
"""

            print(f"  Asking LLM...", end=" ", flush=True)

            action = llm.ask(
                screenshot_b64=screenshot_b64,
                page_text=page_text,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            print("done")
            print(f"  Reasoning: {str(action.get('reasoning','?'))[:75]}")
            print(f"  Action:    {action.get('action')} → {action.get('element','')}")

            if action.get("is_done"):
                final_result = action.get("extracted_data") or {}

                # If LLM forgot to fill extracted_data, scan page text for the balance
                if not final_result:
                    import re
                    balance_match = re.search(r'\$[\d,]+\.\d{2}', page_text)
                    if balance_match:
                        final_result = {"savings_balance": balance_match.group(0)}

                print(f"\n  ✅ GOAL COMPLETE!")
                print(f"  Extracted: {final_result}")
                break

            result = execute_action(page, action)
            print(f"  Result:    {result}")

            step_record = {
                "action":  action.get("action"),
                "element": action.get("element", ""),
                "value":   action.get("value"),
                "result":  result,
            }
            if step_record.get("value") == "12345":
                step_record["value"] = "{{member_id}}"
            steps_done.append(step_record)

        else:
            print(f"\n  ⚠️  Max steps ({MAX_STEPS}) reached")

        page.wait_for_timeout(3000)
        browser.close()

    # ── SAVE ARTIFACT ────────────────────────────────────────────────────────
    if final_result:
        # Build the steps list — starts with navigate, then all recorded steps
        artifact_steps = [
            ActionStep(
                step_id=0,
                description="Navigate to the bank login page",
                action_type="navigate",
                url=BANK_URL,
                locator=None,
            )
        ]

        action_type_map = {"type": "type", "click": "click", "read": "read"}

        for i, s in enumerate(steps_done):
            act = s.get("action", "")
            if act not in action_type_map:
                continue   # skip "done" and unknowns

            artifact_steps.append(ActionStep(
                step_id=i + 1,
                description=s.get("result", f"{act} {s.get('element','')}"),
                action_type=action_type_map[act],
                locator=Locator(
                    strategy="text",
                    value=s.get("element", ""),
                    description=s.get("element", ""),
                ),
                value=s.get("value"),                          # {{member_id}} already substituted above
                extract_as="savings_balance" if act == "read" else None,
                risk_level="safe",
            ))

        artifact = Artifact(
            capability_name="lookup_member_balance",
            description="Log in to the bank and look up a member's savings balance",
            target_url=BANK_URL,
            input_params={"member_id": "string"},
            output_schema={"savings_balance": "string"},
            steps=artifact_steps,
            success_condition="Savings Balance",
            allowed_domains=["127.0.0.1"],
        )

        artifact_path = artifact.save("artifacts")
        print(f"\n  💾 Artifact saved → {artifact_path}")

    # ── FINAL SUMMARY ────────────────────────────────────────────────────────
    print("\n" + "═"*55)
    print(f"  Steps taken: {len(steps_done)}")
    if final_result:
        for k, v in final_result.items():
            print(f"  {k}: {v}")
    else:
        print("  Goal not completed — check evidence/ folder for screenshots")
    print("═"*55 + "\n")
    return final_result


if __name__ == "__main__":
    run_agent()