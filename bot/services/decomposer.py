import asyncio
import json
import logging
import re
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.models import Task, User
from bot.services import tasks as task_svc

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You break overwhelming tasks into 3-5 tiny next actions.
Reply with ONLY a JSON array. No markdown fences, no wrapper object, no commentary.

Example (follow this shape exactly):
[
  {"title": "Open a blank doc and write the essay question at the top", "estimated_minutes": 5},
  {"title": "List 3 facts you already know about the topic", "estimated_minutes": 10},
  {"title": "Find one source link or textbook page to use", "estimated_minutes": 10}
]

Rules:
- Each title starts with a verb and is doable in one sitting
- estimated_minutes must be between 2 and 15"""


@dataclass
class SubtaskDraft:
    title: str
    estimated_minutes: int


def _extract_list(data) -> list | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "title" in data:
            return [data]
        for key in ("tasks", "subtasks", "steps", "items", "actions"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return None


def _parse_subtasks(raw: str) -> list[SubtaskDraft] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[\[{][\s\S]*[\]}]", text)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None

    items = _extract_list(data)
    if items is None or not (2 <= len(items) <= 6):
        return None

    result: list[SubtaskDraft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if len(title) < 3 or len(title) > 120:
            continue
        minutes = item.get("estimated_minutes", 5)
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = 5
        minutes = max(2, min(15, minutes))
        result.append(SubtaskDraft(title=title, estimated_minutes=minutes))

    if len(result) < 2:
        return None
    return result


def template_subtasks(title: str) -> list[SubtaskDraft]:
    return [
        SubtaskDraft(
            title=f'Write one sentence describing what "done" looks like for: {title[:80]}',
            estimated_minutes=5,
        ),
        SubtaskDraft(
            title="Gather anything you need on your desk or screen",
            estimated_minutes=5,
        ),
        SubtaskDraft(
            title="Do the smallest visible part for 5 minutes only",
            estimated_minutes=5,
        ),
    ]


def _chat_payload(prompt: str, *, smaller: bool = False) -> dict:
    user_msg = prompt
    if smaller:
        user_msg += "\n\nBreak this into 2-3 EVEN SMALLER steps (2-5 minutes each)."

    return {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {
            "num_predict": 350,
            "temperature": 0.2,
        },
    }


async def warm_ollama(*, attempts: int = 3, delay_seconds: float = 5.0) -> bool:
    """Load the model into memory so the first user request is fast."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": "ok"}],
        "stream": False,
        "options": {"num_predict": 5},
    }
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            logger.info("Ollama model %s warmed up", settings.ollama_model)
            return True
        except httpx.HTTPError as exc:
            logger.warning(
                "Ollama warm-up attempt %s/%s failed: %s",
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(delay_seconds)
    logger.warning(
        "Ollama not reachable at %s — open the Ollama app, then restart this bot.",
        settings.ollama_base_url,
    )
    return False


async def _call_ollama(prompt: str, *, smaller: bool = False) -> tuple[str | None, str]:
    """Returns (content, error) where error is empty, offline, or timeout."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = _chat_payload(prompt, smaller=smaller)

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                body = response.json()
                content = body.get("message", {}).get("content")
                return content, ""
        except httpx.ConnectError:
            if attempt == 0:
                await asyncio.sleep(5)
                continue
            return None, "offline"
        except httpx.TimeoutException:
            return None, "timeout"
        except httpx.HTTPError as exc:
            logger.warning("Ollama HTTP error: %s", exc)
            return None, "offline"
    return None, "offline"


async def break_down_task(
    session: AsyncSession,
    user: User,
    task: Task,
    *,
    smaller: bool = False,
) -> tuple[list[Task], str]:
    """Returns created child tasks and status: ok, fallback, limit, offline, timeout."""
    if not task_svc.can_breakdown(user):
        children = await _apply_subtasks(session, task, template_subtasks(task.title))
        return children, "limit"

    raw, err = await _call_ollama(f"Task to break down: {task.title}", smaller=smaller)
    if err:
        children = await _apply_subtasks(session, task, template_subtasks(task.title))
        return children, err

    drafts = _parse_subtasks(raw) if raw else None
    if drafts is None and raw:
        raw2, err2 = await _call_ollama(
            f"Task to break down: {task.title}\n\nReturn a JSON array of exactly 3 steps.",
            smaller=smaller,
        )
        if not err2 and raw2:
            drafts = _parse_subtasks(raw2)

    if drafts is None:
        logger.warning("Could not parse Ollama JSON: %s", (raw or "")[:200])
        drafts = template_subtasks(task.title)
        await task_svc.record_breakdown(session, user)
        children = await _apply_subtasks(session, task, drafts)
        return children, "parse"

    await task_svc.record_breakdown(session, user)
    children = await _apply_subtasks(session, task, drafts)
    return children, "ok"


async def _apply_subtasks(
    session: AsyncSession,
    parent: Task,
    drafts: list[SubtaskDraft],
) -> list[Task]:
    children: list[Task] = []
    for draft in drafts:
        child = await task_svc.create_task(
            session,
            parent.user_id,
            draft.title,
            parent_id=parent.id,
            estimated_minutes=draft.estimated_minutes,
        )
        children.append(child)
    return children
