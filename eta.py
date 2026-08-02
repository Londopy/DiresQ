"""Turn "in 45 minutes" into a check-in deadline, or refuse to guess.

This drives a safety timer. If nobody hears from a responder by their ETA the
board flags them, so a wrong deadline is worse than no deadline: too early and
the board cries wolf, too late and someone is missing for hours before anyone
notices. Everything here exists to avoid setting one from a guess.

    result = parse_eta("in 45 minutes")
    if result.accepted:
        assignment.eta = result.when
    else:
        show(result.message)      # ask, or fall back to the default interval
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import timefuzz

# A check-in interval longer than this is not a check-in, it is an off switch.
MAX_MINUTES = 240
# Warn but allow: long, not absurd.
WARN_MINUTES = 120
# Below this the timer fires before anyone has gone anywhere.
MIN_MINUTES = 5
# timefuzz reports how sure it is. Under this we ask rather than assume.
CONFIDENCE_FLOOR = 0.8


@dataclass
class EtaResult:
    accepted: bool
    when: datetime | None = None
    confidence: float = 0.0
    interpretation: str = ""
    message: str = ""
    warning: str = ""


def parse_eta(text: str, now: datetime | None = None) -> EtaResult:
    now = now or datetime.now(timezone.utc)
    text = (text or "").strip()

    if not text:
        return EtaResult(False, message="No ETA given.")

    try:
        result = timefuzz.parse(text, now=now)
    except timefuzz.ParseError:
        return EtaResult(
            False,
            message=f"Could not read {text!r} as a time. Try 'in 45 minutes'.",
        )
    except timefuzz.TimefuzzError as exc:
        return EtaResult(False, message=f"Could not read that as a time: {exc}")

    # Ambiguous carries candidates instead of a single answer, and has no
    # confidence at all. Never pick one on the responder's behalf.
    if isinstance(result, timefuzz.Ambiguous):
        return EtaResult(
            False,
            message=f"{text!r} could mean several things. Pick one or be specific.",
            interpretation=getattr(result, "reason", ""),
        )

    if isinstance(result, timefuzz.Range):
        # A range is the responder's own window; the deadline is its far end.
        when, confidence = result.end, result.confidence
    else:
        when, confidence = result.when, result.confidence

    interpretation = getattr(result, "interpretation", "") or text

    if confidence < CONFIDENCE_FLOOR:
        return EtaResult(
            False,
            when=when,
            confidence=confidence,
            interpretation=interpretation,
            message=f"Not confident enough about {text!r} to set a safety timer. "
                    f"Best guess was {interpretation}. Confirm it or be specific.",
        )

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    minutes = (when - now).total_seconds() / 60

    if minutes <= 0:
        return EtaResult(
            False, when=when, confidence=confidence, interpretation=interpretation,
            message=f"{interpretation} is in the past.",
        )

    if minutes > MAX_MINUTES:
        return EtaResult(
            False, when=when, confidence=confidence, interpretation=interpretation,
            message=f"Check-in intervals are capped at {MAX_MINUTES // 60} hours. "
                    f"Set a shorter one and extend it when you check in.",
        )

    if minutes < MIN_MINUTES:
        # Clamp rather than reject: they meant soon, just not that soon.
        when = now + timedelta(minutes=MIN_MINUTES)
        return EtaResult(
            True, when=when, confidence=confidence, interpretation=interpretation,
            warning=f"Rounded up to {MIN_MINUTES} minutes, the shortest interval.",
        )

    warning = ""
    if minutes > WARN_MINUTES:
        warning = (f"That is over {WARN_MINUTES // 60} hours away. "
                   f"Shorter intervals are safer.")

    return EtaResult(True, when=when, confidence=confidence,
                     interpretation=interpretation, warning=warning)
