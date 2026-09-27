"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        self._stage_tables: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def module_names(self) -> list[str]:
        return sorted(set(self._tables) | set(self._stage_tables))

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def register_stages(self, module: str, stages: list[str]) -> None:
        """把模块的存量记录按状态拆进分段存储，之后按段读写、在段间流转。"""
        buckets: dict[str, list[dict[str, Any]]] = {stage: [] for stage in stages}
        for row in self._tables.pop(module, []):
            stage = str(row.get("status") or "")
            buckets[stage if stage in buckets else stages[0]].append(row)
        self._stage_tables[module] = buckets

    def stage_names(self, module: str) -> list[str]:
        return list(self._stage_tables.get(module, {}))

    def stage_rows(self, module: str, stage: str) -> list[dict[str, Any]]:
        return self._stage_tables[module][stage]

    def all_rows(self, module: str) -> list[dict[str, Any]]:
        buckets = self._stage_tables.get(module)
        if buckets is None:
            return self.rows(module)
        return [row for bucket in buckets.values() for row in bucket]

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.all_rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.all_rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
