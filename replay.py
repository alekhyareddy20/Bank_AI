# replay.py
# Loads a saved artifact and replays the steps — NO AI needed

import json
from playwright.sync_api import sync_playwright

def replay(artifact_path, input_params={}):
    """
    Loads an artifact JSON and replays every step.
    input_params lets you swap {{member_id}} with a real value.
    """

    print(f"\n📂 Loading artifact: {artifact_path}")
    with open(artifact_path) as f:
        artifact = json.load(f)

    print(f"   Capability: {artifact['capability_name']}")
    print(f"   Steps to replay: {len(artifact['steps'])}")
    print(f"   Input params: {input_params}")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(artifact["target_url"])

        for i, step in enumerate(artifact["steps"]):
            step_id = step.get("step_id", i)
            action = step.get("action", step.get("action_type", ""))
            element = step.get("element", step.get("locator", {}).get("value", "unknown") if isinstance(step.get("locator"), dict) else "unknown")

            # Replace {{member_id}} with the real value
            value = step.get("value")
            if value and "{{" in str(value):
                for param_key, param_val in input_params.items():
                    value = value.replace(f"{{{{{param_key}}}}}", param_val)

            print(f"\n   Step {step_id + 1}: {action} → {element}")
            if value:
                print(f"            value: {value}")

            try:
                if action == "type":
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

                elif action == "read":
                    # Read savings balance from the page
                    all_cells = page.locator("td").all()
                    for i, cell in enumerate(all_cells):
                        text = cell.inner_text().strip()
                        if "Savings Balance" in text:
                            balance = all_cells[i + 1].inner_text().strip()
                            results["savings_balance"] = balance
                            print(f"            extracted: {balance}")

                print(f"   ✓ Done")

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                break

        page.wait_for_timeout(2000)
        browser.close()

    print(f"\n✅ REPLAY COMPLETE")
    print(f"   Results: {results}")
    return results


# Run it — change the artifact filename to match yours
if __name__ == "__main__":
    import sys
    import os

    # Find the latest artifact
    files = [f for f in os.listdir("artifacts") if f.endswith(".json")]
    if not files:
        print("No artifacts found! Run test_agent.py first.")
        exit()

    latest = sorted(files)[-1]
    artifact_path = f"artifacts/{latest}"

    # Replay with a DIFFERENT member ID
    results = replay(
        artifact_path=artifact_path,
        input_params={"member_id": "67890"}
    )



# # 
# 📂 Loading artifact: artifacts/lookup_member_balance_cb794397.json
#    Capability: lookup_member_balance
#    Steps to replay: 6
#    Input params: {'member_id': '67890'}

#    Step 1: type → Username input field
#             value: admin
#    ✓ Done

#    Step 2: type → Password input field
#             value: password123
#    ✓ Done

#    Step 3: click → Login button
#    ✓ Done

#    Step 4: type → Member ID input field
#             value: 67890
#    ✓ Done

#    Step 5: click → Search Member button
#    ✓ Done

#    Step 6: read → Savings Balance value
#             extracted: MEMBER DETAILS — ID: 67890
#             extracted: $12,750.50
#    ✓ Done

# ✅ REPLAY COMPLETE
#    Results: {'savings_balance': '$12,750.50'}