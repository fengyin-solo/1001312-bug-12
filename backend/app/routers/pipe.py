"""管网巡查接口：登记、补录、填写记录与复核；待巡查、巡查中、已复核三段分开存放。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload, PageResult, SupplementaryItemResult, SupplementaryResult
from app.services.pipe import ACTIONS, STAGES, PipeService

router = APIRouter(prefix="/api/pipe", tags=["管网巡查"])

service = PipeService()


class SupplementaryPayload(BaseModel):
    """批量补录提交内容：每条记录独立校验，失败的可只重试该条。"""

    items: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/stats", response_model=dict[str, int])
def stage_stats() -> dict[str, int]:
    """三段进度各自的记录数；统计卡片、列表、详情、复核弹窗同源。"""
    return service.stats()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出管网巡查清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pipe", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按巡查编号检索"),
    status: str | None = Query(default=None, description="待巡查、巡查中、已复核"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按巡查编号与进度过滤管网巡查列表；没有数据时返回空页，不报错。"""
    if status and status not in STAGES:
        raise HTTPException(status_code=400, detail=f"进度「{status}」不存在，可选：{'、'.join(STAGES)}")
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条管网巡查明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"管网巡查 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条管网巡查；缺字段或巡查编号重复时说明原因，不覆盖历史记录。"""
    entry, error = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=error)
    return ActionResult(ok=True, message=f"管网巡查 {entry['巡查编号']} 已登记，进度：{entry['巡查状态']}", entry=entry)


@router.post("/supplementary", response_model=SupplementaryResult)
def supplementary_entries(payload: SupplementaryPayload) -> SupplementaryResult:
    """批量补录：每条独立校验，被阻断的巡查编号随原因一并返回，可只重试失败的那条。"""
    if not payload.items:
        return SupplementaryResult(ok=False, message="补录内容为空，没有可提交的记录")
    results = [SupplementaryItemResult(**item) for item in service.supplementary(payload.items)]
    blocked = [item.code for item in results if not item.ok]
    message = f"补录完成：成功 {len(results) - len(blocked)} 条，阻断 {len(blocked)} 条"
    if blocked:
        message += f"，被阻断的巡查编号：{'、'.join(blocked)}"
    return SupplementaryResult(ok=not blocked, message=message, results=results)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条管网巡查执行开始巡查、填写记录、复核；被阻断时说明原因并列出巡查编号。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, blocked = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message, blocked=blocked)
    return ActionResult(ok=True, message=message, entry=entry)
