# agent_artifact.py
# This defines what an Artifact looks like — a saved recipe of steps

import json
import uuid
from datetime import datetime

def create_artifact(capability_name, description, goal, steps, extracted_data):
    """
    Takes the steps the AI performed and saves them as a reusable JSON file.
    
    steps = list of actions the AI took
    extracted_data = the final result (e.g. savings balance)
    """
    
    artifact = {
        "id": str(uuid.uuid4())[:8],
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "capability_name": capability_name,
        "description": description,
        "goal": goal,
        "target_url": "http://127.0.0.1:5000",
        "input_params": {
            "member_id": "string"
        },
        "output_schema": {
            "savings_balance": "string"
        },
        "steps": steps,
        "extracted_data": extracted_data,
        "success_condition": "Page shows member savings balance"
    }
    
    # Save to artifacts folder
    filename = f"artifacts/{capability_name}_{artifact['id']}.json"
    with open(filename, "w") as f:
        json.dump(artifact, f, indent=2)
    
    print(f"\n💾 Artifact saved: {filename}")
    print(f"   Steps recorded: {len(steps)}")
    print(f"   Extracted data: {extracted_data}")
    
    return filename, artifact


# Test it — create a sample artifact from our known steps
if __name__ == "__main__":
    
    sample_steps = [
        {
            "step_id": 0,
            "action": "type",
            "element": "Username input field",
            "value": "admin",
            "checkpoint": "Password field visible"
        },
        {
            "step_id": 1,
            "action": "type",
            "element": "Password input field",
            "value": "password123",
            "checkpoint": "Login button visible"
        },
        {
            "step_id": 2,
            "action": "click",
            "element": "Login button",
            "value": None,
            "checkpoint": "Member Search page visible"
        },
        {
            "step_id": 3,
            "action": "type",
            "element": "Member ID input field",
            "value": "{{member_id}}",
            "checkpoint": "Search Member button visible"
        },
        {
            "step_id": 4,
            "action": "click",
            "element": "Search Member button",
            "value": None,
            "checkpoint": "Savings Balance visible"
        },
        {
            "step_id": 5,
            "action": "read",
            "element": "Savings Balance value",
            "value": None,
            "checkpoint": None
        }
    ]
    
    extracted = {"savings_balance": "$5,432.10"}
    
    create_artifact(
        capability_name="lookup_member_balance",
        description="Log in and look up a member savings balance",
        goal="Log in and find member savings balance",
        steps=sample_steps,
        extracted_data=extracted
    )


#after adding this   - to test_agent 
# Gemini: The savings balance for member 12345 is displayed as $5,432.10. The goal is full
#   Action: done → None

# ✅ GOAL COMPLETE!

# 💾 Artifact saved: artifacts/lookup_member_balance_cb794397.json
#    Steps recorded: 5
#    Extracted data: {'savings_balance': 'extracted from page'}