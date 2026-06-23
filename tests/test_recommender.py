"""Unit tests for next-step recommender scoring."""

from datetime import UTC, datetime

from bot.models import Task, TaskStatus
from bot.services.recommender import pick_next


def _task(
    task_id: int,
    *,
    parent_id: int | None = None,
    minutes: int | None = 5,
    priority: int = 0,
    created_at: datetime | None = None,
    status: str = TaskStatus.PENDING,
) -> Task:
    return Task(
        id=task_id,
        user_id=1,
        parent_id=parent_id,
        title=f"Task {task_id}",
        status=status,
        estimated_minutes=minutes,
        priority=priority,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_pick_next_prefers_shallower_task():
    root = _task(1, minutes=15)
    shallow = _task(2, parent_id=1, minutes=10)
    deep = _task(3, parent_id=2, minutes=3, created_at=datetime(2026, 1, 2, tzinfo=UTC))
    all_tasks = [root, shallow, deep]

    result = pick_next([shallow, deep], all_tasks)

    assert result is not None
    assert result.id == 2


def test_pick_next_respects_max_minutes():
    short = _task(1, minutes=5)
    long = _task(2, minutes=30)
    all_tasks = [short, long]

    result = pick_next([short, long], all_tasks, max_minutes=10)

    assert result is not None
    assert result.id == 1


def test_pick_next_returns_none_when_all_excluded():
    a = _task(1, minutes=5)
    b = _task(2, minutes=10)
    all_tasks = [a, b]

    result = pick_next([a, b], all_tasks, exclude_ids={1, 2})

    assert result is None


def test_pick_next_excludes_skipped_ids():
    a = _task(1, minutes=5)
    b = _task(2, minutes=10)
    all_tasks = [a, b]

    result = pick_next([a, b], all_tasks, exclude_ids={1})

    assert result is not None
    assert result.id == 2


def test_root_id_finds_top_level_goal():
    from bot.services.tasks import root_id

    root = _task(1)
    child = _task(2, parent_id=1)
    grandchild = _task(3, parent_id=2)
    by_id = {t.id: t for t in [root, child, grandchild]}

    assert root_id(grandchild, by_id) == 1


def test_pick_next_returns_none_when_empty():
    assert pick_next([], []) is None
