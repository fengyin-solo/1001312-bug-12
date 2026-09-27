"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_GROUPS, SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        # 分段数据：module -> {分段名: [记录]}，各段独立存放，不与主表混在一起。
        self._groups: dict[str, dict[str, list[dict[str, Any]]]] = {
            module: {
                stage: [dict(row) for row in rows]
                for stage, rows in stages.items()
            }
            for module, stages in SEED_GROUPS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def stages(self, module: str) -> dict[str, list[dict[str, Any]]]:
        """返回某模块的分段容器；没有分段数据的模块拿到空容器，不影响主表。"""
        return self._groups.setdefault(module, {})

    def stage_rows(self, module: str, stage: str) -> list[dict[str, Any]]:
        return self.stages(module).setdefault(stage, [])

    def find_in_groups(self, module: str, entry_id: int) -> tuple[str, dict[str, Any]] | None:
        """在某模块的全部分段里按 id 找记录，返回（所在分段, 记录）。"""
        for stage, rows in self.stages(module).items():
            for row in rows:
                if int(row.get("id", 0)) == entry_id:
                    return stage, row
        return None

    def next_group_id(self, module: str) -> int:
        return max(
            (
                int(row.get("id", 0))
                for rows in self.stages(module).values()
                for row in rows
            ),
            default=0,
        ) + 1

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        # 分段模块（如管网巡查）不在主表里，单独汇总：未复核的算待处理。
        for name, stages in self._groups.items():
            all_rows = [row for rows in stages.values() for row in rows]
            done_stage = "已复核"
            modules.append({
                "name": name,
                "created": len(all_rows),
                "pending": sum(1 for stage, rows in stages.items() if stage != done_stage for _ in rows),
                "abnormal": sum(1 for row in all_rows if str(row.get("异常描述") or "").strip() not in ("", "无异常")),
            })
            modules.sort(key=lambda item: str(item["name"]))
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
