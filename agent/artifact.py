# agent/artifact.py
#
# This file defines the ARTIFACT — the saved recipe of steps the AI discovered.
# Think of it like a cooking recipe:
#   - ingredients  = input_params  (what you pass in, e.g., member_id)
#   - steps        = the ordered list of UI actions to take
#   - final dish   = output_schema (what you get back, e.g., balance)
#
# Why Pydantic? It validates the data structure automatically.
# If a field is missing or the wrong type, it raises an error immediately.

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import json
import uuid
import os

# ─────────────────────────────────────────────────────────────────────────────
# A single locator — how to FIND an element on the page
# ─────────────────────────────────────────────────────────────────────────────
class Locator(BaseModel):
    strategy: Literal["text", "aria-label", "placeholder", "xpath", "css", "role"]
    value: str
    description: str = ""   # human-readable explanation

# ─────────────────────────────────────────────────────────────────────────────
# A single ACTION step — one thing the agent does
# ─────────────────────────────────────────────────────────────────────────────
class ActionStep(BaseModel):
    step_id: int
    description: str              # plain English: "Click the Login button"

    action_type: Literal[
        "navigate",   # go to a URL
        "click",      # click a button/link
        "type",       # type text into a field
        "read",       # read/extract text from the page
        "wait",       # wait for something to appear
        "select",     # select dropdown option
    ]

    # PRIMARY locator — the best way to find this element
    locator: Optional[Locator] = None

    # FALLBACK locators — tried in order if primary fails (legacy app resilience)
    fallback_locators: List[Locator] = Field(default_factory=list)

    # For "navigate" steps: the URL to go to
    url: Optional[str] = None

    # For "type" steps: what to type.
    # Use {{param_name}} for values that change per run (e.g., {{member_id}})
    value: Optional[str] = None

    # For "read" steps: the key name to store the extracted text under
    extract_as: Optional[str] = None

    # For "wait" steps: what text/element to wait for
    wait_for: Optional[str] = None

    # CHECKPOINT: after this step, the page should contain this text.
    # Used to verify the step actually worked.
    checkpoint_text: Optional[str] = None

    # RISK: "safe" actions can be retried; "irreversible" need human approval
    risk_level: Literal["safe", "irreversible"] = "safe"

    # How long to wait after this action (milliseconds)
    wait_after_ms: int = 500


# ─────────────────────────────────────────────────────────────────────────────
# The full ARTIFACT — the complete saved capability
# ─────────────────────────────────────────────────────────────────────────────
class Artifact(BaseModel):
    # Unique ID for this artifact
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Version lets you update artifacts over time without breaking old replays
    version: str = "1.0"

    # Human-readable name for this capability
    capability_name: str

    # What this capability does (for human reviewers and AI agents)
    description: str

    # The starting URL for this flow
    target_url: str

    # INPUT PARAMETERS — what the caller must supply each time
    # e.g., {"member_id": "string", "amount": "number"}
    input_params: Dict[str, str] = Field(default_factory=dict)

    # OUTPUT SCHEMA — what this capability returns when successful
    # e.g., {"savings_balance": "string", "member_name": "string"}
    output_schema: Dict[str, str] = Field(default_factory=dict)

    # The ordered list of steps
    steps: List[ActionStep] = Field(default_factory=list)

    # SUCCESS CONDITION — text that must appear on screen when the goal is done
    success_condition: str

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: str = "discovery-agent"

    # Safety: domains/URLs this artifact is allowed to touch
    allowed_domains: List[str] = Field(default_factory=list)

    # ── Methods ──────────────────────────────────────────────────────────────

    def save(self, directory: str = "artifacts") -> str:
        """Save the artifact as a JSON file. Returns the file path."""
        os.makedirs(directory, exist_ok=True)
        filename = f"{self.capability_name.replace(' ', '_').lower()}_{self.id}.json"
        filepath = os.path.join(directory, filename)
        with open(filepath, "w") as f:
            f.write(self.model_dump_json(indent=2))
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "Artifact":
        """Load an artifact from a JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        return cls(**data)

    def substitute_params(self, params: Dict[str, Any]) -> "Artifact":
        """
        Replace {{param_name}} placeholders with actual values.
        Returns a NEW artifact with values filled in (original is unchanged).
        Example: step has value="{{member_id}}", params={"member_id": "12345"}
                 → step becomes value="12345"
        """
        import copy
        artifact_copy = self.model_copy(deep=True)
        for step in artifact_copy.steps:
            if step.value and "{{" in step.value:
                for key, val in params.items():
                    step.value = step.value.replace(f"{{{{{key}}}}}", str(val))
            if step.url and "{{" in step.url:
                for key, val in params.items():
                    step.url = step.url.replace(f"{{{{{key}}}}}", str(val))
        return artifact_copyß