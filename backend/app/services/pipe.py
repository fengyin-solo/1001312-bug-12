"""管网巡查业务规则：待巡查、巡查中、已复核三段分开存放，巡查记录只落在对应的巡查编号上。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pipe"
STAGES = ["待巡查", "巡查中", "已复核"]
REQUIRED_FIELDS = ["巡查编号", "巡查路段", "巡查人员", "巡查日期"]
RECORD_FIELDS = ["管线状况", "井盖状况", "异常描述"]
ACTIONS = ["开始巡查", "填写记录", "复核"]

store.register_stages(MODULE, STAGES)


def _normalize(values: dict[str, Any]) -> dict[str, str]:
    return {field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS + RECORD_FIELDS}


class PipeService:
    """巡查记录的三段流转与字段校验。"""

    # ---------- 读取 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._serialize_all()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("巡查编号", ""))]
        if status:
            rows = [row for row in rows if row["status"] == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        found = self._locate(entry_id)
        if found is None:
            return None
        stage, row = found
        return self._serialize(row, stage)

    def stats(self) -> dict[str, int]:
        return {stage: len(store.stage_rows(MODULE, stage)) for stage in STAGES}

    # ---------- 登记与补录 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        taken = {str(row.get("巡查编号") or "") for row in store.all_rows(MODULE)}
        entry, error = self._build_entry(values, taken)
        if entry is None:
            return None, error
        stage = str(entry["status"])
        store.stage_rows(MODULE, stage).append(entry)
        return self._serialize(entry, stage), ""

    def supplementary(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """批量补录：每条独立校验、独立落库，被阻断的条目不影响其他条目。"""
        taken = {str(row.get("巡查编号") or "") for row in store.all_rows(MODULE)}
        results: list[dict[str, Any]] = []
        for values in items:
            entry, error = self._build_entry(values, taken)
            code = str(values.get("巡查编号") or "").strip() or "（未填写巡查编号）"
            if entry is None:
                results.append({"ok": False, "code": code, "reason": error, "entry": None})
                continue
            stage = str(entry["status"])
            store.stage_rows(MODULE, stage).append(entry)
            taken.add(str(entry["巡查编号"]))
            results.append({"ok": True, "code": code, "reason": "", "entry": self._serialize(entry, stage)})
        return results

    # ---------- 动作流转 ----------

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str, list[str]]:
        found = self._locate(entry_id)
        if found is None:
            return None, f"管网巡查 {entry_id} 不存在或已归档", []
        stage, row = found
        code = str(row.get("巡查编号") or entry_id)

        if action == "开始巡查":
            if stage != "待巡查":
                return None, f"巡查编号 {code} 当前进度为「{stage}」，不能重复开始巡查", [code]
            self._move(row, stage, "巡查中")
            return self._serialize(row, "巡查中"), f"巡查编号 {code} 已开始巡查", []

        if action == "填写记录":
            if stage == "已复核":
                return None, f"巡查编号 {code} 已复核，异常描述不允许再修改", [code]
            data = _normalize(values)
            if not data["管线状况"]:
                return None, f"巡查编号 {code} 管线状况为空，不允许提交，请补充管线状况后重试", [code]
            for field in RECORD_FIELDS:
                row[field] = data[field]
            row["abnormal"] = bool(data["异常描述"])
            if stage != "巡查中":
                self._move(row, stage, "巡查中")
            return self._serialize(row, "巡查中"), f"巡查编号 {code} 巡查记录已保存，进度：巡查中", []

        if action == "复核":
            if stage != "巡查中":
                return None, f"巡查编号 {code} 当前进度为「{stage}」，只有巡查中的记录才能复核", [code]
            self._move(row, stage, "已复核")
            return self._serialize(row, "已复核"), f"巡查编号 {code} 已复核，记录已锁定", []

        return None, f"动作「{action}」不属于管网巡查可执行范围（可选：{'、'.join(ACTIONS)}）", []

    # ---------- 内部工具 ----------

    def _build_entry(self, values: dict[str, Any], taken: set[str]) -> tuple[dict[str, Any] | None, str]:
        data = _normalize(values)
        label = data["巡查编号"] or "（未填写巡查编号）"
        missing = [field for field in REQUIRED_FIELDS if not data[field]]
        if missing:
            return None, f"{label} 缺少必填字段：{'、'.join(missing)}"
        if data["巡查编号"] in taken:
            return None, f"巡查编号 {data['巡查编号']} 已存在，为保护历史巡查记录，本条登记被阻断"
        has_record = any(data[field] for field in RECORD_FIELDS)
        if has_record and not data["管线状况"]:
            return None, f"巡查编号 {data['巡查编号']} 管线状况为空，不允许提交"
        entry: dict[str, Any] = {
            "id": self._next_id(),
            "status": "巡查中" if has_record else "待巡查",
            "pending": True,
            "abnormal": bool(data["异常描述"]),
            **data,
        }
        return entry, ""

    def _next_id(self) -> int:
        return max((int(row.get("id", 0)) for row in store.all_rows(MODULE)), default=0) + 1

    def _locate(self, entry_id: int) -> tuple[str, dict[str, Any]] | None:
        for stage in STAGES:
            for row in store.stage_rows(MODULE, stage):
                if int(row.get("id", 0)) == entry_id:
                    return stage, row
        return None

    def _move(self, row: dict[str, Any], source: str, target: str) -> None:
        store.stage_rows(MODULE, source).remove(row)
        store.stage_rows(MODULE, target).append(row)
        row["status"] = target
        row["pending"] = target != STAGES[-1]

    def _serialize(self, row: dict[str, Any], stage: str) -> dict[str, Any]:
        data = dict(row)
        data["status"] = stage
        data["巡查状态"] = stage  # 列表、详情、复核弹窗统一以分段存储的进度为准
        data["pending"] = stage != STAGES[-1]
        return data

    def _serialize_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for stage in STAGES:
            for row in store.stage_rows(MODULE, stage):
                rows.append(self._serialize(row, stage))
        return rows
