#!/usr/bin/env python3
# main.py — single entry point
#
#   python main.py bank
#   python main.py replay artifacts/lookup_member_balance_XXXX.json member_id=12345
#   python main.py replay artifacts/lookup_member_balance_XXXX.json member_id=99999

import sys
import os
import glob
import json
from dotenv import load_dotenv

load_dotenv()


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║        ComputerUse Automation System                 ║
║        interface.ai Take-Home Project                ║
╚══════════════════════════════════════════════════════╝
""")


def cmd_bank(args):
    from target_app.app import app
    print_banner()
    print("▶ Starting Fake Bank App")
    print("  Open: http://localhost:5000")
    print("  Login: admin / password123\n")
    app.run(debug=False, port=5000)


def cmd_replay(args):
    from agent.replay import replay

    if not args:
        print("ERROR: Please provide the artifact path.")
        print("Usage: python main.py replay artifacts/ARTIFACT_FILE.json member_id=12345")
        sys.exit(1)

    artifact_path = args[0]
    if not os.path.exists(artifact_path):
        matches = glob.glob("artifacts/*.json")
        if matches:
            artifact_path = sorted(matches)[-1]
            print(f"  Auto-selected artifact: {artifact_path}")
        else:
            print(f"ERROR: No artifact found at {artifact_path}")
            sys.exit(1)

    params = {}
    for arg in args[1:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v

    print_banner()
    print(f"▶ Starting REPLAY run")
    print(f"  Artifact: {artifact_path}")
    print(f"  Params:   {params}\n")

    result  = replay(artifact_path=artifact_path, input_params=params)
    status  = result.get("status", "unknown")
    results = result.get("results", {})

    print(f"\n{'═'*50}")
    print(f"RESULT: {status.upper()}")
    if status == "success":
        print(f"Outputs: {json.dumps(results, indent=2)}")
    elif status == "business_outcome":
        print(f"Outcome: {results.get('outcome', 'see above')}")
    else:
        print("Check evidence/ folder for failure screenshots")
    print(f"{'═'*50}\n")


COMMANDS = {
    "bank":   cmd_bank,
    "replay": cmd_replay,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print_banner()
        print("Usage:")
        print("  python main.py bank")
        print("  python main.py replay <artifact.json> [member_id=VALUE]")
        print()
        print("Examples:")
        print("  Terminal 1:  python main.py bank")
        print("  Terminal 2:  python test_agent.py")
        print("  Terminal 2:  python main.py replay artifacts/lookup_member_balance_*.json member_id=12345")
        print("  Terminal 2:  python main.py replay artifacts/lookup_member_balance_*.json member_id=67890")
        print("  Terminal 2:  python main.py replay artifacts/lookup_member_balance_*.json member_id=99999")
        sys.exit(0)

    COMMANDS[sys.argv[1]](sys.argv[2:])