# tests.py
# Tests for the entire system — run all at once

import os
import json

os.makedirs("evidence", exist_ok=True)
os.makedirs("evidence/interventions", exist_ok=True)

passed = 0
failed = 0

def test(name, condition, expected=True):
    global passed, failed
    result = condition == expected
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} — {name}")
    if result:
        passed += 1
    else:
        failed += 1


print("\n" + "="*50)
print("RUNNING ALL TESTS")
print("="*50 + "\n")


# ── TEST 1: GUARDRAILS ────────────────────────────────────────
print("--- Guardrails ---")
from guardrails import check_url, check_action, check_risky_page, redact_sensitive

# Allowed URL passes
try:
    check_url("http://127.0.0.1:5000/search")
    test("Allowed URL passes", True)
except:
    test("Allowed URL passes", False)

# Blocked URL raises exception
try:
    check_url("http://google.com")
    test("Blocked URL raises exception", False)
except:
    test("Blocked URL raises exception", True)

# Risky page detected
risky, keyword = check_risky_page("This action cannot be undone")
test("Risky page detected", risky, True)

# Safe page not flagged
risky, _ = check_risky_page("Welcome to BankCore")
test("Safe page not flagged", risky, False)

# Password redacted
redacted = redact_sensitive("password", "password123")
test("Password is redacted", redacted != "password123")
test("Password shows last 4 chars", redacted.endswith("d123"))

# Normal field not redacted
normal = redact_sensitive("member_id", "12345")
test("Normal field not redacted", normal == "12345")


# ── TEST 2: ARTIFACT ─────────────────────────────────────────
print("\n--- Artifact ---")
from agent_artifact import create_artifact

# Create a test artifact
filepath, artifact = create_artifact(
    capability_name="test_capability",
    description="Test artifact",
    goal="Test goal",
    steps=[{"step_id": 0, "action": "click", "element": "button", "value": None}],
    extracted_data={"result": "ok"}
)

test("Artifact file created", os.path.exists(filepath))
test("Artifact has capability name", artifact["capability_name"] == "test_capability")
test("Artifact has steps", len(artifact["steps"]) == 1)
test("Artifact has version", artifact["version"] == "1.0")


# ── TEST 3: REPLAY ────────────────────────────────────────────
print("\n--- Replay (no browser) ---")

# Check artifact files exist
files = [f for f in os.listdir("artifacts") if f.endswith(".json")]
test("At least one artifact exists", len(files) > 0)

# Check artifact structure
# Use the bank artifact specifically, not the test one
bank_files = [f for f in files if "lookup_member" in f]
latest = sorted(bank_files)[-1] if bank_files else sorted(files)[-1]
with open(f"artifacts/{latest}") as f:
    data = json.load(f)

test("Artifact has steps", len(data.get("steps", [])) > 0)
test("Artifact has target_url", "target_url" in data)
test("Artifact has member_id placeholder", 
     any("{{member_id}}" in str(s.get("value","")) for s in data["steps"]))


# ── TEST 4: ESCALATION ────────────────────────────────────────
print("\n--- Escalation ---")
from escalation import request_intervention, resolve_intervention, list_pending

filepath = request_intervention(
    reason="Test intervention",
    goal="Test goal",
    step_num=1,
    screenshot_path="evidence/test.png",
    context={}
)

test("Intervention file created", os.path.exists(filepath))
pending = list_pending()
test("Intervention shows as pending", len(pending) > 0)

resolve_intervention(filepath, notes="Test resolved")
pending = list_pending()
test("No pending after resolve", len(pending) == 0)


# ── SUMMARY ───────────────────────────────────────────────────
print("\n" + "="*50)
print(f"RESULTS: {passed} passed, {failed} failed")
print("="*50)
if failed == 0:
    print("🎉 ALL TESTS PASSED!")
else:
    print("⚠️  Some tests failed — check above")