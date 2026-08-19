# escalation.py
# When the agent is stuck or hits a risky action,
# it writes a file and WAITS for a human to resolve it.

import json
import os
import time
from datetime import datetime

INTERVENTIONS_DIR = "evidence/interventions"


def request_intervention(reason, goal, step_num, screenshot_path, context={}):
    """
    Agent is stuck. Write an intervention file and pause.
    A human will read this file and click Resume.
    """
    os.makedirs(INTERVENTIONS_DIR, exist_ok=True)

    intervention = {
        "id": f"intervention_{int(time.time())}",
        "status": "pending",
        "reason": reason,
        "goal": goal,
        "step_num": step_num,
        "screenshot_path": screenshot_path,
        "context": context,
        "created_at": datetime.utcnow().isoformat(),
        "resolved_at": None,
        "human_notes": ""
    }

    filepath = os.path.join(INTERVENTIONS_DIR, f"{intervention['id']}.json")
    with open(filepath, "w") as f:
        json.dump(intervention, f, indent=2)

    print(f"\n🆘 INTERVENTION REQUESTED")
    print(f"   Reason: {reason}")
    print(f"   Step: {step_num}")
    print(f"   File: {filepath}")
    print(f"   Waiting for human to resolve...")

    return filepath


def wait_for_resume(intervention_path, timeout_seconds=300):
    """
    Poll the intervention file every 2 seconds.
    Return True when human marks it as resolved.
    """
    start = time.time()

    while time.time() - start < timeout_seconds:
        with open(intervention_path) as f:
            data = json.load(f)

        if data["status"] == "resolved":
            print(f"\n✅ Human resolved the intervention!")
            print(f"   Notes: {data.get('human_notes', 'none')}")
            return True

        time.sleep(2)
        print(f"   Still waiting... ({int(time.time() - start)}s)")

    print(f"\n⏰ Timeout — no human response after {timeout_seconds}s")
    return False


def resolve_intervention(intervention_path, notes=""):
    """Human calls this to mark intervention as resolved"""
    with open(intervention_path) as f:
        data = json.load(f)

    data["status"] = "resolved"
    data["resolved_at"] = datetime.utcnow().isoformat()
    data["human_notes"] = notes

    with open(intervention_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Intervention resolved: {intervention_path}")


def list_pending():
    """List all pending interventions"""
    if not os.path.exists(INTERVENTIONS_DIR):
        return []

    pending = []
    for filename in os.listdir(INTERVENTIONS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(INTERVENTIONS_DIR, filename)) as f:
                data = json.load(f)
            if data["status"] == "pending":
                pending.append(data)

    return pending


# ── TEST IT ───────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("evidence/interventions", exist_ok=True)

    print("Testing escalation system...\n")

    # Simulate agent getting stuck
    filepath = request_intervention(
        reason="Cannot find element after 3 attempts",
        goal="Look up member savings balance",
        step_num=4,
        screenshot_path="evidence/failure_step_4.png",
        context={"element": "Search button", "action": "click"}
    )

    print(f"\nIntervention file created at: {filepath}")
    print("In a real system, the human would now:")
    print("  1. See this in the operator console")
    print("  2. Fix the issue manually in the browser")
    print("  3. Click Resume")
    print("\nSimulating human resolving it now...")

    time.sleep(1)
    resolve_intervention(filepath, notes="Fixed — button label had changed")

    print(f"\nPending interventions: {list_pending()}")
    print("\n✅ Escalation system working!")