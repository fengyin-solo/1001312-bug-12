"""管网巡查业务规则：待巡查 / 巡查中 / 已复核三段分开存放。

- 三个分段各是一份独立列表，状态只由记录所在分段决定（列表页、详情页、复核弹窗看到的进度一致）。
- 异常描述等业务字段只写在对应巡查编号的那条记录上，绝不跨编号读写。
- 填写记录时管线状况必填，为空则阻断提交并列出被阻断的巡查编号。
- 已复核记录进入终态：异常描述不可再改，也不能重复复核。
- 新增 / 补录一律追加新记录，巡查编号重复会被拦下，历史记录不会被覆盖。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pipe"

STAGE_PENDING = "待巡查"
STAGE_DOING = "巡查中"
STAGE_REVIEWED = "已复核"
STAGES = [STAGE_PENDING, STAGE_DOING, STAGE_REVIEWED]

REQUIRED_FIELDS = ["巡查编号", "巡查路段", "巡查人员", "巡查日期"]
RECORD_FIELDS = ["管线状况", "井盖状况", "异常描述"]
DETAIL_FIELDS = REQUIRED_FIELDS + RECORD_FIELDS


class PipeService:
    # ---------- 查询 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        road: str | None = None,
        inspector: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        stage_names = [status] if status else STAGES
        rows: list[dict[str, Any]] = []
        for stage in stage_names:
            for row in store.stage_rows(MODULE, stage):
                rows.append(self._serialize(stage, row))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("巡查编号", ""))]
        if road:
            rows = [row for row in rows if road in str(row.get("巡查路段", ""))]
        if inspector:
            rows = [row for row in rows if inspector in str(row.get("巡查人员", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        found = store.find_in_groups(MODULE, entry_id)
        if found is None:
            return None
        stage, row = found
        return self._serialize(stage, row)

    def stage_counts(self) -> dict[str, int]:
        return {stage: len(store.stage_rows(MODULE, stage)) for stage in STAGES}

    # ---------- 登记 / 补录 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """登记（或补录单条重试）一条巡查；只追加、不覆盖，编号重复会被拦下。"""
        cleaned, missing = self._clean_required(values)
        if missing:
            return None, missing
        if self._find_by_code(cleaned["巡查编号"]) is not None:
            return None, [f"巡查编号「{cleaned['巡查编号']}」已存在，补录不会覆盖历史记录"]
        # 补录时若已带管线状况，直接进入巡查中；否则作为待巡查任务等待现场登记。
        has_pipe_condition = bool(str(values.get("管线状况") or "").strip())
        stage = STAGE_DOING if has_pipe_condition else STAGE_PENDING
        entry = {"id": store.next_group_id(MODULE), **cleaned}
        for field in RECORD_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        store.stage_rows(MODULE, stage).append(entry)
        return self._serialize(stage, entry), []

    def backfill_entries(
        self, entries: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """批量补录：成功的逐条追加；失败的退回原始下标、编号与原因，可只重试失败条目。"""
        created: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for index, values in enumerate(entries):
            entry, problems = self.create_entry(values)
            if entry is not None:
                created.append(entry)
                continue
            code = str(values.get("巡查编号") or "").strip() or "(未填编号)"
            blocked.append({"index": index, "巡查编号": code, "原因": "；".join(problems)})
        return created, blocked

    # ---------- 动作流转 ----------

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str, list[str]]:
        """执行动作。返回 (更新后的记录, 消息, 被阻断的巡查编号列表)。"""
        values = values or {}
        found = store.find_in_groups(MODULE, entry_id)
        if found is None:
            return None, f"巡查记录 {entry_id} 不存在或已归档", []
        stage, row = found
        code = str(row.get("巡查编号") or entry_id)

        if action == "开始巡查":
            if stage == STAGE_REVIEWED:
                return None, f"巡查编号 {code} 已复核，不能重新开始巡查", [code]
            if stage != STAGE_PENDING:
                return None, f"巡查编号 {code} 当前为{STAGE_DOING}，无需重复开始巡查", [code]
            self._move(row, STAGE_PENDING, STAGE_DOING)
            return self._serialize(STAGE_DOING, row), f"巡查编号 {code} 已开始巡查", []

        if action == "填写记录":
            if stage == STAGE_REVIEWED:
                return None, f"巡查编号 {code} 已复核，记录已锁定，不允许再改异常描述", [code]
            if stage != STAGE_DOING:
                return None, f"巡查编号 {code} 还未开始巡查，请先开始巡查再填写记录", [code]
            pipe_condition = str(values.get("管线状况") or "").strip()
            if not pipe_condition:
                return None, f"巡查编号 {code} 管线状况为空，不允许提交，请补充管线状况后重试", [code]
            # 只更新本编号自己这条记录上的业务字段，空值不动旧值，避免误清空。
            row["管线状况"] = pipe_condition
            cover = str(values.get("井盖状况") or "").strip()
            if cover:
                row["井盖状况"] = cover
            abnormal = str(values.get("异常描述") or "").strip()
            if abnormal:
                row["异常描述"] = abnormal
            return self._serialize(stage, row), f"巡查编号 {code} 的巡查记录已保存", []

        if action == "复核":
            if stage == STAGE_REVIEWED:
                return None, f"巡查编号 {code} 已复核，不能重复复核", [code]
            if stage != STAGE_DOING:
                return None, f"巡查编号 {code} 尚未填写巡查记录，暂不能复核", [code]
            self._move(row, STAGE_DOING, STAGE_REVIEWED)
            return self._serialize(STAGE_REVIEWED, row), f"巡查编号 {code} 已复核，异常描述已归档保留", []

        return None, f"动作「{action}」不属于管网巡查可执行范围", []

    # ---------- 内部辅助 ----------

    def _clean_required(self, values: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
        cleaned = {field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS}
        missing = [field for field in REQUIRED_FIELDS if not cleaned[field]]
        return cleaned, missing

    def _find_by_code(self, code: str) -> dict[str, Any] | None:
        for rows in store.stages(MODULE).values():
            for row in rows:
                if str(row.get("巡查编号") or "") == code:
                    return row
        return None

    def _move(self, row: dict[str, Any], from_stage: str, to_stage: str) -> None:
        source = store.stage_rows(MODULE, from_stage)
        source.remove(row)
        store.stage_rows(MODULE, to_stage).append(row)

    def _serialize(self, stage: str, row: dict[str, Any]) -> dict[str, Any]:
        """对外统一结构：进度一律取所在分段，占位字段「巡查状态」不再参与。"""
        item = {"id": row.get("id"), "status": stage}
        for field in DETAIL_FIELDS:
            item[field] = row.get(field, "") or ""
        item["巡查状态"] = stage
        item["abnormal"] = str(row.get("异常描述") or "").strip() not in ("", "无异常")
        return item
