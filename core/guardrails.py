import os
from typing import Dict, Any

_policy_text = ""


def load_policy() -> None:
    global _policy_text
    path = os.path.join(os.path.dirname(__file__), "..", "guardrails", "na_uk_policy.md")
    with open(path, "r", encoding="utf-8") as f:
        _policy_text = f.read().strip()


def build_system_prompt(profile: Dict[str, Any], memory: Dict[str, Any]) -> str:
    parts = [_policy_text]
    if profile:
        name = profile.get("name", "Caller")
        parts.append(f"The caller is {name}.")
    if memory:
        topics = memory.get("last_topics")
        if topics:
            parts.append(f"Recent topics: {topics}.")
    parts.append("Reply briefly in British English and remain within NA guidelines.")
    return "\n".join(parts)


def get_excerpt() -> str:
    return _policy_text.splitlines()[0]
