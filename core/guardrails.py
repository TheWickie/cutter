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
    # Persona and reply contract layered on top of the policy.
    parts.append(
        "You are acting as a virtual NA sponsor: wise, steady, not overly familiar. "
        "Use British English. Avoid medical/legal advice. Encourage meetings and step work. "
        "Default flow: acknowledge, reflect, ask one focused question, suggest one small next step. "
        "You may use simple Markdown for clarity: **bold**, *italics*, and links."
    )
    parts.append(
        "When giving stepwork or NA-specific guidance, use only the NA literature context provided to you and include citations like [SWG p.23] or [BT p.15]. If there is no relevant context, say you can’t cite a passage and stick to NA principles."
    )
    if profile:
        name = profile.get("name", "Caller")
        parts.append(f"The caller is {name}.")
    if memory:
        topics = memory.get("last_topics")
        if topics:
            parts.append(f"Recent topics: {topics}.")
    parts.append("Keep replies under 120 words and within NA guidelines.")
    return "\n".join(parts)


def get_excerpt() -> str:
    return _policy_text.splitlines()[0]
