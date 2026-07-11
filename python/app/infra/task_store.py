from __future__ import annotations

from copy import deepcopy
from typing import Any


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def save(self, task_id: str, payload: dict[str, Any]) -> None:
        self._data[task_id] = deepcopy(payload)

    def get(self, task_id: str) -> dict[str, Any] | None:
        item = self._data.get(task_id)
        return deepcopy(item) if item else None


task_store = InMemoryTaskStore()
