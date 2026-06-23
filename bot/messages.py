from bot.models import Task


def format_next_step(task: Task, *, note: str | None = None) -> str:
    minutes = task.estimated_minutes or 5
    lines = [
        f"Your next step (~{minutes} min):",
        "",
        f'"{task.title}"',
    ]
    if note == "offline":
        lines.append("")
        lines.append(
            "(Ollama is not running — open the Ollama app, wait ~10 seconds, "
        "restart the bot, then try /breakdown again. Using simple steps for now.)"
        )
    elif note == "timeout":
        lines.append("")
        lines.append(
            "(AI took too long — model may still be loading. Using simple steps; try again in a minute.)"
        )
    elif note == "parse":
        lines.append("")
        lines.append("(AI reply was unclear — using simple steps.)")
    elif note == "fallback":
        lines.append("")
        lines.append("(Used simple steps — could not reach Ollama.)")
    elif note == "limit":
        lines.append("")
        lines.append("(Daily AI breakdown limit reached — using simple steps.)")
    return "\n".join(lines)


def format_empty() -> str:
    return (
        "Nothing to do right now.\n\n"
        "/add — add a task\n"
        "/list — see your tasks"
    )
