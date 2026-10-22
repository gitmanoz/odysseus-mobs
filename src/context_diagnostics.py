"""Content-free observations of the existing prompt, never a compaction policy."""
import json

from src.model_context import estimate_tokens


def context_profile(messages, tool_schemas=None):
    buckets = {}
    seen_system = set()
    duplicate_system = 0
    duplicate_system_tokens = 0
    duplicate_protected = 0
    for message in messages:
        role = message.get("role", "unknown")
        if message.get("_mobs_persona_sources"):
            category = "persona"
        elif message.get("_governed_tool_protocol"):
            category = "tool_protocol"
        elif message.get("_governed_action_instruction"):
            category = "action_instruction"
        elif message.get("_protected"):
            category = "protected_context"
        else:
            category = role if role in {"system", "user", "assistant", "tool"} else "other"
        bucket = buckets.setdefault(category, {"messages": 0, "estimated_tokens": 0})
        bucket["messages"] += 1
        bucket["estimated_tokens"] += estimate_tokens([message])
        if role == "system":
            # Compare locally; never return source content, IDs, paths or hashes.
            content = json.dumps(message.get("content"), ensure_ascii=False, sort_keys=True)
            if content in seen_system:
                duplicate_system += 1
                duplicate_system_tokens += estimate_tokens([message])
                duplicate_protected += bool(message.get('_protected'))
            seen_system.add(content)
    schemas = tool_schemas or []
    schema_text = json.dumps(schemas, ensure_ascii=False, separators=(",", ":")) if schemas else ""
    return {
        "estimate_only": True,
        "messages": len(messages),
        "message_tokens_estimated": estimate_tokens(messages),
        "categories": buckets,
        "duplicate_system_messages": duplicate_system,
        "duplicate_system_tokens_estimated": duplicate_system_tokens,
        "duplicate_protected_messages": duplicate_protected,
        "tool_schema_count": len(schemas),
        "tool_schema_tokens_estimated": int(len(schema_text) * 0.3),
        "image_tokens_included": False,
    }
