# replay.py
# Replay engine with error classification AND safety guardrails
# Three outcomes: success, business_outcome, hard_failure

import json
import os
from playwright.sync_api import sync_playwright
from agent.guardrails import check_url, check_action, check_risky_page, safe_log_step

BUSINESS_OUTCOMES = [
    "No record found",
    "Member not found",
    "Invalid member",
    "Account frozen",
    "Invalid username or password",
    "Session expired",
    "Access denied",
]

HARD_FAILURE_PATTERNS = [
    "500",
    "Internal Server Error",
    "Connection refused",
]


def check_page_for_errors(page_text):
    for pattern in BUSINESS_OUTCOMES:
        if pattern.lower() in page_text.lower():
            return "business_outcome", pattern
    for pattern in HARD_FAILURE_PATTERNS:
        if pattern.lower() in page_text.lower():
            return "hard_failure", pattern
    return "success", None


def replay(artifact_path, input_params={}):
    print(f"\n📂 Loading artifact: {artifact_path}")
    with open(artifact_path) as f:
        artifact = json.load(f)

    print(f"   Capability: {artifact['capability_name']}")
    print(f"   Steps to replay: {len(artifact['steps'])}")
    print(f"   Input params: {input_params}")

    results = {}
    final_status = "success"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(artifact["target_url"])

        for i, step in enumerate(artifact["steps"]):
            step_id = step.get("step_id", i)

            # Support both old format (action/element) and new Pydantic format (action_type/locator)
            action  = step.get("action_type") or step.get("action", "")
            locator = step.get("locator") or {}
            element = locator.get("description") or locator.get("value") or step.get("element", "")

            # Replace {{member_id}} with real value
            value = step.get("value")
            if value and "{{" in str(value):
                for param_key, param_val in input_params.items():
                    value = value.replace(f"{{{{{param_key}}}}}", param_val)

            print(f"\n   Step {step_id + 1}: {action} → {element}")

            # ── SAFETY CHECKS ──────────────────────────────────
            try:
                check_action(action)
                if step.get("url"):
                    check_url(step["url"])
            except Exception as e:
                print(f"   🚫 SAFETY BLOCK: {e}")
                final_status = "hard_failure"
                break

            # ── RISKY PAGE CHECK ───────────────────────────────
            page_text = page.inner_text("body")
            is_risky, keyword = check_risky_page(page_text)
            if is_risky:
                print(f"   ⚠️  RISKY PAGE DETECTED: '{keyword}'")
                print(f"   🛑 Stopping — human approval needed")
                final_status = "hard_failure"
                break

            # ── LOG STEP ───────────────────────────────────────
            safe_log_step(element, value)

            try:
                if action == "navigate":
                    page.goto(step.get("url", artifact["target_url"]))
                    page.wait_for_timeout(800)

                elif action == "type":
                    if "username" in element.lower():
                        page.get_by_placeholder("Username").fill(value)
                    elif "password" in element.lower():
                        page.get_by_placeholder("Password").fill(value)
                    elif "member" in element.lower():
                        page.get_by_placeholder("Enter Member ID").fill(value)
                    page.wait_for_timeout(500)

                elif action == "click":
                    if "login" in element.lower():
                        page.get_by_role("button", name="Login").click()
                    elif "search" in element.lower():
                        page.get_by_role("button", name="Search Member").click()
                    page.wait_for_timeout(1000)

                    page_text = page.inner_text("body")
                    status, message = check_page_for_errors(page_text)

                    if status == "business_outcome":
                        print(f"\n⚠️  BUSINESS OUTCOME: {message}")
                        final_status = "business_outcome"
                        results["outcome"] = message
                        browser.close()
                        return {"status": final_status, "results": results}

                    if status == "hard_failure":
                        print(f"\n❌ HARD FAILURE: {message}")
                        os.makedirs("evidence", exist_ok=True)
                        page.screenshot(path="evidence/failure.png")
                        final_status = "hard_failure"
                        browser.close()
                        return {"status": final_status, "results": results}

                elif action == "read":
                    all_cells = page.locator("td").all()
                    for j, cell in enumerate(all_cells):
                        text = cell.inner_text().strip()
                        if "Savings Balance" in text:
                            balance = all_cells[j + 1].inner_text().strip()
                            results["savings_balance"] = balance
                            print(f"            extracted: {balance}")

                print(f"   ✓ Done")

            except Exception as e:
                print(f"   ❌ Step failed: {e}")
                os.makedirs("evidence", exist_ok=True)
                page.screenshot(path=f"evidence/failure_step_{i}.png")
                final_status = "hard_failure"
                break

        page.wait_for_timeout(2000)
        browser.close()

    print(f"\n{'✅' if final_status == 'success' else '⚠️'} REPLAY COMPLETE")
    print(f"   Status: {final_status}")
    print(f"   Results: {results}")
    return {"status": final_status, "results": results}


if __name__ == "__main__":
    os.makedirs("evidence", exist_ok=True)
    files = [f for f in os.listdir("artifacts") if f.endswith(".json")]
    latest = sorted(files)[-1]

    print("TEST 1: Valid member 67890")
    replay(f"artifacts/{latest}", input_params={"member_id": "67890"})

    print("\n" + "=" * 50)
    print("TEST 2: Missing member 99999")
    replay(f"artifacts/{latest}", input_params={"member_id": "99999"})