"""管网巡查接口：待巡查、巡查中、已复核三段数据分开维护。

覆盖开始巡查、填写记录、复核、登记与批量补录（失败可单条重试）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    BackfillPayload,
    BackfillResult,
    EntryPayload,
    PipeListResult,
)
from app.services.pipe import STAGES, PipeService

router = APIRouter(prefix="/api/pipe", tags=["管网巡查"])

service = PipeService()

LIST_FIELDS = ["巡查编号", "巡查路段", "巡查人员", "巡查日期", "管线状况", "井盖状况", "异常描述", "巡查状态"]


@router.get("", response_model=PipeListResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按巡查编号检索"),
    road: str | None = Query(default=None, description="按巡查路段检索"),
    inspector: str | None = Query(default=None, description="按巡查人员检索"),
    status: str | None = Query(default=None, description="待巡查、巡查中、已复核"),
    page: int = 1,
    size: int = 20,
) -> PipeListResult:
    """按巡查编号、路段、人员与状态过滤；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status is not None and status not in STAGES:
        raise HTTPException(status_code=400, detail=f"巡查状态只支持：{'、'.join(STAGES)}")
    items, total = service.list_entries(
        keyword=keyword, road=road, inspector=inspector, status=status, page=page, size=size
    )
    return PipeListResult(
        items=items,
        total=total,
        page=page,
        size=size,
        stage_counts=service.stage_counts(),
    )


@router.get("/export")
def export_entries() -> dict[str, object]:
    """导出管网巡查清单：三段的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pipe", "total": total, "items": items}


@router.post("/backfill", response_model=BackfillResult)
def backfill_entries(payload: BackfillPayload) -> BackfillResult:
    """批量补录：成功的追加，失败的列出巡查编号与原因，可只重试失败的那几条。"""
    if not payload.entries:
        return BackfillResult(ok=False, message="补录内容为空，未写入任何记录")
    created, blocked = service.backfill_entries(payload.entries)
    if blocked and not created:
        message = f"{len(blocked)} 条补录全部失败，被阻断的巡查编号：{'、'.join(item['巡查编号'] for item in blocked)}"
    elif blocked:
        message = f"已补录 {len(created)} 条；{len(blocked)} 条被阻断：{'、'.join(item['巡查编号'] for item in blocked)}"
    else:
        message = f"补录完成，共写入 {len(created)} 条"
    return BackfillResult(ok=not blocked, message=message, created=created, blocked=blocked)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条管网巡查明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"巡查记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记（或补录失败后单条重试）一条管网巡查；缺字段或编号重复时说明原因，不静默丢弃。"""
    entry, problems = service.create_entry(payload.values)
    if problems:
        return ActionResult(ok=False, message="；".join(problems))
    return ActionResult(ok=True, message="管网巡查已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条管网巡查执行开始巡查、填写记录、复核；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, blocked = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message, blocked=blocked)
    return ActionResult(ok=True, message=message, entry=entry)
