from __future__ import annotations

from pathlib import Path

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.llm import LLMClient
from app.models import (
    AIConfig,
    AIConfigCreate,
    AIConfigUpdate,
    AIOrderUpdate,
    DiscussionRequest,
    DiscussionRecord,
    DiscussionSummary,
)
from app.services.discussion import DiscussionService
from app.storage import ensure_storage, load_ais, save_ais, list_discussions, load_discussion

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI Meeting")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ensure_storage()
llm_client = LLMClient()
discussion_service = DiscussionService(llm_client)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "discuss.html", {"page": "discuss"})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "config.html", {"page": "config"})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "history.html", {"page": "history"})


@app.get("/discuss", response_class=HTMLResponse)
async def discuss_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "discuss.html", {"page": "discuss"})


@app.get("/api/ais")
async def list_ais() -> list[AIConfig]:
    return load_ais()


@app.post("/api/ais")
async def create_ai(payload: AIConfigCreate) -> dict:
    configs = load_ais()
    config = AIConfig(**payload.model_dump(), order=len(configs))
    try:
        config.self_intro = await llm_client.create_self_intro(config)
    except Exception:
        config.self_intro = payload.self_intro
        configs.append(config)
        save_ais(configs)
        return {"self_intro_failed": True, "ai": config.model_dump()}
    configs.append(config)
    save_ais(configs)
    return config.model_dump()


@app.put("/api/ais/order")
async def reorder_ais(payload: AIOrderUpdate) -> list[AIConfig]:
    configs = load_ais()
    config_map = {item.id: item for item in configs}
    reordered = []
    for index, ai_id in enumerate(payload.ids):
        if ai_id in config_map:
            reordered.append(config_map[ai_id].model_copy(update={"order": index}))
    missing = [item for item in configs if item.id not in payload.ids]
    for item in missing:
        reordered.append(item.model_copy(update={"order": len(reordered)}))
    return save_ais(reordered)


@app.put("/api/ais/{ai_id}")
async def update_ai(ai_id: str, payload: AIConfigUpdate) -> AIConfig:
    configs = load_ais()
    for index, item in enumerate(configs):
        if item.id != ai_id:
            continue
        updated = item.model_copy(update=payload.model_dump(exclude_none=True))
        configs[index] = updated
        save_ais(configs)
        return updated
    raise HTTPException(status_code=404, detail="AI not found")


@app.delete("/api/ais/{ai_id}")
async def delete_ai(ai_id: str) -> dict[str, bool]:
    configs = [item for item in load_ais() if item.id != ai_id]
    save_ais(configs)
    return {"ok": True}


@app.get("/api/ais/status")
async def ai_status() -> list[dict[str, str]]:
    configs = load_ais()
    if not configs:
        return []

    tasks = [
        asyncio.sleep(0, result=("disabled", "")) if not config.enabled else llm_client.check_status(config)
        for config in configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    statuses = []
    for config, result in zip(configs, results):
        if isinstance(result, tuple):
            status, detail = result
        else:
            status, detail = "error", str(result)
        statuses.append({"id": config.id, "status": status, "detail": detail})
    return statuses


@app.get("/api/discussions")
async def list_discussion_history() -> list[DiscussionSummary]:
    items = list_discussions()
    return [DiscussionSummary.model_validate(item) for item in items]


@app.get("/api/discussions/{discussion_id}")
async def get_discussion(discussion_id: str) -> DiscussionRecord:
    try:
        return load_discussion(discussion_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Discussion not found")


@app.post("/api/discussions")
async def start_discussion(payload: DiscussionRequest) -> StreamingResponse:
    all_ais = load_ais()
    ais = [ai for ai in all_ais if ai.enabled]
    if not ais:
        raise HTTPException(status_code=400, detail="At least one enabled AI is required")
    # 根据前端传来的 compressor_id 查找压缩器 AI
    compressor_ai = None
    if payload.compressor_id:
        compressor_ai = next((ai for ai in all_ais if ai.id == payload.compressor_id), None)
    generator = discussion_service.run(payload, ais, compressor_ai)
    return StreamingResponse(generator, media_type="text/event-stream")


@app.post("/api/discussions/stop")
async def stop_discussion() -> dict[str, bool]:
    discussion_service.request_stop()
    return {"ok": True}
