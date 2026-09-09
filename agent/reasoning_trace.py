"""Render a decision_trail (from agent.controller.run_pipeline) into a clean,
human-readable multi-line string for console or UI display."""


def format_trace(decision_trail):
    lines = []
    for i, entry in enumerate(decision_trail, start=1):
        lines.append(f"[{i}] {entry['step']}")
        lines.append(f"    input:    {entry['input']}")
        lines.append(f"    result:   {entry['result']}")
        lines.append(f"    decision: {entry['decision']}")
    return "\n".join(lines)
