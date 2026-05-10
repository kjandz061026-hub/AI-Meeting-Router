from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.models import AIConfig


class LLMClient:
    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def _normalize_base_url(self, base_url: str) -> str:
        return base_url.rstrip("/")

    async def create_self_intro(self, config: AIConfig) -> str:
        system_prompt = (
            "你即将加入一个多智能体讨论系统。请用中文做简短自我介绍，必须包含："
            "名字、擅长领域与能力、上下文窗口大小(token数)、工作风格或个性。"
            '控制在150字以内，并以严格JSON格式输出：{"name":"...","expertise":"...",'
            '"context_window":...,"style":"..."}。'
            f"你的名字是：{config.name}，上下文窗口约：{config.context_window} token。"
        )
        payload = {
            "model": config.model,
            "messages": [{"role": "system", "content": system_prompt}],
            "temperature": 0.4,
            "stream": False,
        }
        response = await self._post_json(config, payload)
        content = response["choices"][0]["message"]["content"]
        parsed = self._extract_intro_json(content)
        return (
            f"{parsed['name']}，擅长{parsed['expertise']}，上下文窗口约{parsed['context_window']} token，"
            f"风格是{parsed['style']}。"
        )

    async def stream_chat(
        self,
        config: AIConfig,
        system_prompt: str,
        user_content: str,
    ) -> AsyncIterator[str]:
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._normalize_base_url(config.base_url)}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta

    async def _post_json(self, config: AIConfig, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._normalize_base_url(config.base_url)}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def check_status(self, config: AIConfig) -> tuple[str, str]:
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": "请用中文简短回答：连接测试。"}
            ],
            "temperature": 0,
            "max_tokens": 256,
            "stream": False,
        }
        try:
            response = await self._post_json(config, payload)
            if (
                isinstance(response, dict)
                and response.get("choices")
                and response["choices"][0].get("message", {}).get("content") is not None
            ):
                return "available", ""
            return "error", "无效响应"
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                error_payload = exc.response.json()
                detail = (
                    error_payload.get("error", {}).get("message")
                    or error_payload.get("message")
                    or exc.response.text
                )
            except Exception:
                detail = exc.response.text
            return "error", f"HTTP {exc.response.status_code} {detail}"
        except Exception as exc:
            return "error", str(exc)

    def _extract_intro_json(self, content: str) -> dict[str, Any]:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("self intro json not found")
        parsed = json.loads(content[start : end + 1])
        required = {"name", "expertise", "context_window", "style"}
        if not required.issubset(parsed):
            raise ValueError("self intro json missing fields")
        return parsed
