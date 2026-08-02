"""START triage, mapped onto report severity.

Picking HIGH/MEDIUM/LOW from a dropdown is a guess. START is the protocol
actual responders use at a mass-casualty scene: four observations anybody can
make without training or equipment, producing a category that means the same
thing to everyone who reads it.

    result = assess(can_walk=False, respiratory_rate=34)
    result.priority   # 'Immediate'
    result.severity   # 'HIGH'  -> what the report gets filed as
"""

from __future__ import annotations

from dataclasses import dataclass

from vitalscore import score_start

# START categories map onto our severity bands. Deceased maps to HIGH
# because it still needs someone there, it isn't "less urgent than Minor".
SEVERITY_OF = {
    "Immediate": "HIGH",
    "Delayed": "MEDIUM",
    "Minor": "LOW",
    "Deceased": "HIGH",
}

# Plain-English reason for each category, shown under the result.
EXPLANATION = {
    "Immediate": "Breathing, circulation or responsiveness is outside safe "
                 "limits. Needs help before anyone else here.",
    "Delayed": "Cannot walk, but breathing and circulation are stable and "
               "they are responsive. Needs help, can wait a little.",
    "Minor": "Able to walk. Injuries can wait; they may be able to help.",
    "Deceased": "Not breathing after the airway was repositioned. Under START "
                "this is triaged last so the living are reached first.",
}

QUESTIONS = [
    {"key": "can_walk", "type": "bool",
     "ask": "Can they walk?"},
    {"key": "breathing", "type": "bool",
     "ask": "Are they breathing?"},
    {"key": "respiratory_rate", "type": "int",
     "ask": "Roughly how many breaths per minute?"},
    {"key": "has_radial_pulse", "type": "bool",
     "ask": "Can you feel a pulse at their wrist?"},
    {"key": "follows_commands", "type": "bool",
     "ask": "Can they follow a simple instruction, like squeezing your hand?"},
]


@dataclass
class TriageResult:
    priority: str
    severity: str
    explanation: str
    can_walk: bool
    respiratory_rate: int | None


def assess(
    can_walk: bool,
    respiratory_rate: int | None,
    *,
    has_radial_pulse: bool | None = None,
    follows_commands: bool | None = None,
    airway_repositioned: bool = False,
) -> TriageResult:
    """Run START and translate the category into a report severity."""
    result = score_start(
        can_walk=can_walk,
        respiratory_rate=respiratory_rate,
        has_radial_pulse=has_radial_pulse,
        follows_commands=follows_commands,
        airway_repositioned=airway_repositioned,
    )
    priority = result.priority.value
    return TriageResult(
        priority=priority,
        severity=SEVERITY_OF[priority],
        explanation=EXPLANATION[priority],
        can_walk=can_walk,
        respiratory_rate=respiratory_rate,
    )
