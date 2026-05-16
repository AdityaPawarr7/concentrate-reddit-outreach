"""Suggested reply angles for Concentrate's Reddit account — customize before posting."""

TEMPLATES = {
    "cost": (
        "If you're juggling multiple LLM providers, Concentrate gives you one API with "
        "routing/caching and typically lower token spend (~20% savings). Worth a look if "
        "cost is the pain point: https://concentrate.ai/"
    ),
    "cursor_claude": (
        "For Cursor / Claude Code — Concentrate lets you route to any model through one "
        "gateway (keys, logs, spend caps in one place). No lock-in to a single vendor: "
        "https://concentrate.ai/"
    ),
    "governance": (
        "On compliance/guardrails — Concentrate adds redaction, RBAC, and audit logs on "
        "top of multi-provider access. Handy when data can't leave your boundary: "
        "https://concentrate.ai/"
    ),
    "reliability": (
        "For provider outages — multi-provider failover through one API beats wiring "
        "fallbacks yourself. Concentrate handles that layer: https://concentrate.ai/"
    ),
    "general": (
        "Unified LLM gateway (one API, all major providers, orchestration + billing + "
        "guardrails). Might fit what you're describing: https://concentrate.ai/"
    ),
}


def template_for_angle(suggested_angle: str) -> str:
    angle = suggested_angle.lower()
    if "cost" in angle:
        return TEMPLATES["cost"]
    if "ide" in angle or "cursor" in angle or "claude code" in angle:
        return TEMPLATES["cursor_claude"]
    if "governance" in angle:
        return TEMPLATES["governance"]
    if "reliability" in angle:
        return TEMPLATES["reliability"]
    return TEMPLATES["general"]
