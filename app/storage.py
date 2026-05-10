from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.models import AIConfig, DiscussionRecord

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DISCUSSIONS_DIR = DATA_DIR / "discussions"
AI_CONFIG_PATH = DATA_DIR / "ais_config.json"

_lock = Lock()


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DISCUSSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not AI_CONFIG_PATH.exists():
        AI_CONFIG_PATH.write_text("[]", encoding="utf-8")


def _load_json(path: Path) -> list[dict]:
    ensure_storage()
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return []
    return json.loads(raw)


def _save_json(path: Path, payload: list[dict]) -> None:
    ensure_storage()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ais() -> list[AIConfig]:
    with _lock:
        items = _load_json(AI_CONFIG_PATH)
    configs = [AIConfig.model_validate(item) for item in items]
    return sorted(configs, key=lambda item: item.order)


def save_ais(configs: list[AIConfig]) -> list[AIConfig]:
    normalized = []
    for index, config in enumerate(sorted(configs, key=lambda item: item.order)):
        normalized.append(config.model_copy(update={"order": index}))
    with _lock:
        _save_json(AI_CONFIG_PATH, [item.model_dump() for item in normalized])
    return normalized


def save_discussion(record: DiscussionRecord) -> Path:
    ensure_storage()
    path = DISCUSSIONS_DIR / f"{record.id}.json"
    with _lock:
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def list_discussions() -> list[dict[str, Any]]:
    ensure_storage()
    if not DISCUSSIONS_DIR.exists():
        return []
    paths = sorted(DISCUSSIONS_DIR.glob("*.json"), key=lambda item: item.name, reverse=True)
    summaries: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            summaries.append(
                {
                    "id": data.get("id", path.stem),
                    "question": data.get("question", ""),
                    "final_answer": data.get("final_answer", ""),
                    "stop_reason": data.get("stop_reason", ""),
                    "metadata": data.get("metadata", {}),
                }
            )
        except Exception:
            continue
    return summaries


def load_discussion(discussion_id: str) -> DiscussionRecord:
    path = DISCUSSIONS_DIR / f"{discussion_id}.json"
    if not path.exists():
        raise FileNotFoundError("Discussion record not found")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return DiscussionRecord.model_validate(data)
