"""任务表：Redis Hash（r1 同款，独立成模块便于阅读）。"""

import json

from redis_client import get_async_redis

R = get_async_redis()


class TaskStore:
    KEY = "agent:tasks"

    async def create(self, goal: str) -> dict:
        import uuid

        task_id = uuid.uuid4().hex[:8]
        task = {"task_id": task_id, "goal": goal, "state": "running"}
        await R.hset(self.KEY, task_id, json.dumps(task, ensure_ascii=False))
        return task

    async def get(self, task_id: str) -> dict | None:
        raw = await R.hget(self.KEY, task_id)
        return json.loads(raw) if raw else None

    async def set_state(self, task_id: str, state: str) -> None:
        task = await self.get(task_id)
        if task:
            task["state"] = state
            await R.hset(self.KEY, task_id, json.dumps(task, ensure_ascii=False))

    async def all(self) -> list[dict]:
        return [json.loads(v) for v in await R.hvals(self.KEY)]


STORE = TaskStore()
