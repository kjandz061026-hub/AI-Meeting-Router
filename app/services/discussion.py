from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.llm import LLMClient
from app.models import AIConfig, DiscussionMessage, DiscussionRecord, DiscussionRequest, SSEEvent
from app.services.reputation import ReputationEngine
from app.storage import save_discussion

try:
    import tiktoken
except Exception:  # pragma: no cover - optional runtime dependency
    tiktoken = None

CONFIDENCE_RE = re.compile(r"\[CONFIDENCE:(\d{1,3})\]", re.IGNORECASE)
FINAL_RE = re.compile(r"<FINAL_ANSWER>(.*?)</FINAL_ANSWER>", re.IGNORECASE | re.DOTALL)
SYSTEM_NOTE = "[系统：上一位参与者置信度不足但试图结束，请继续深入讨论。]"
TOKENIZER_TEST_SNIPPET = "本地多智能体讨论"
KNOWN_MODEL_ENCODINGS = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}

CONFIDENCE_CALIBRATION_PROMPT = """
[置信度校准标准 — 必须严格遵守]
你的置信度不是对你个人推理能力的自信程度，而是对"此发言在当前讨论语境下的可靠程度"的评估。
请严格参照以下标准打分，不要凭感觉：

- 0-20：纯粹的推测或头脑风暴，仅作为引子，极可能被反驳
- 21-40：有一定逻辑，但你明确知道自己缺少关键数据或存在重大假设
- 41-60：逻辑自洽，但你已经预判到其他参与者很可能从不同角度提出有力反驳
- 61-80：此观点综合了当前讨论的历史信息，你认为你能为它辩护，但仍有不确定性
- 81-100：此发言几乎无懈可击，综合了所有已有讨论，直接推动了共识形成

关键原则：如果一个分数高于 80，但你的发言不是最终答案，那你可能高估了自己。
在输出最终置信度之前，你必须执行以下自检：
1. 列出你核心论点的 3 个最重要的前提假设
2. 基于其他参与者的专长，指出谁最可能反驳你的哪个观点
3. 模拟该参与者会如何攻击你论点的最薄弱环节
4. 基于这次模拟攻防，你的置信度是否需要下调？

你的最终 [CONFIDENCE:数值] 必须反映这次自检的结果。

[置信度的真正含义]
记住，这个分数不是给你的知识打分，而是给你的这次"干预"对讨论的推动作用打分：
- 你是否只是重复了已知信息？（如果是，分数 < 60）
- 你是否只是换了个说法包装前人的观点？（如果是，分数 < 50）
- 你是否提出了全新角度或解决方案，同时分析了它的风险？（如果是，分数 60-85）
- 你的发言是否几乎无懈可击，将讨论直接推向终点？（如果是，分数 85+）

[关于收敛]
讨论的目标是找到一个可行的、逻辑自洽的答案，而不是追求完美。
当你认为当前讨论已经达成了一个合理的共识，即使不是最优解，也应该果断输出 [CONFIDENCE:95] 以上并给出 <FINAL_ANSWER>。
不要因为"还能再讨论"就犹豫不决——一个好的答案胜过无休止的讨论。
"""


def calibrate_confidence(raw_confidence: int, ai_config: AIConfig, message_content: str, history: list[DiscussionMessage]) -> int:
    """对原始置信度进行系统级修正"""
    score = raw_confidence

    # 1. 应用 AI 配置中的校准值
    score += ai_config.confidence_calibration

    # 2. 空话惩罚：发言没有引用任何人名且置信度 > 80，直接降为 60
    mentioned_names = [msg.ai_name for msg in history]
    if score > 80 and not any(name in message_content for name in mentioned_names):
        score = 60

    # 3. 高频警告：如果该 AI 历史发言置信度标准差极小（说明没认真校准）
    ai_scores = [msg.confidence for msg in history if msg.ai_id == ai_config.id and msg.confidence is not None]
    if len(ai_scores) >= 3:
        mean = sum(ai_scores) / len(ai_scores)
        variance = sum((x - mean) ** 2 for x in ai_scores) / len(ai_scores)
        std = variance ** 0.5
        if std < 5:  # 标准差小于 5，说明置信度几乎没变化
            import random
            score = int(score * random.uniform(0.8, 0.95))

    return max(0, min(100, score))


@dataclass
class DiscussionState:
    final_answer: str = ""
    stop_reason: str = ""
    next_note: str = ""


class TokenCounter:
    def __init__(self) -> None:
        self._mode: str | None = None
        self._cache: dict[str, object] = {}

    def count(self, text: str, model: str) -> int:
        if self._mode is None:
            self._mode = "tiktoken" if self._probe_tiktoken() else "estimate"

        if self._mode == "tiktoken":
            try:
                encoder = self._get_encoder(model)
                return len(encoder.encode(text))
            except Exception:
                self._mode = "estimate"

        return self._estimate(text)

    def _probe_tiktoken(self) -> bool:
        if tiktoken is None:
            return False

        script = (
            "import tiktoken\n"
            "enc = tiktoken.get_encoding('cl100k_base')\n"
            f"print(len(enc.encode({TOKENIZER_TEST_SNIPPET!r})))\n"
        )
        try:
            subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(Path(__file__).resolve().parent.parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
                check=True,
                text=True,
            )
            return True
        except Exception:
            return False

    def _get_encoder(self, model: str):
        if model not in self._cache:
            try:
                self._cache[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding_name = KNOWN_MODEL_ENCODINGS.get(model, "cl100k_base")
                self._cache[model] = tiktoken.get_encoding(encoding_name)
        return self._cache[model]

    def _estimate(self, text: str) -> int:
        ascii_chars = sum(1 for char in text if ord(char) < 128)
        non_ascii_chars = len(text) - ascii_chars
        return max(1, ascii_chars // 4 + non_ascii_chars)


class DiscussionService:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self._stop_event = asyncio.Event()
        self._token_counter = TokenCounter()
        self.reputation_engine = ReputationEngine()

    def request_stop(self) -> None:
        self._stop_event.set()

    def reset_stop(self) -> None:
        self._stop_event = asyncio.Event()

    async def run(self, request: DiscussionRequest, ais: list[AIConfig], compressor_ai: AIConfig | None = None) -> AsyncIterator[str]:
        self.reset_stop()
        self._compressor_ai = compressor_ai
        self.reputation_engine = ReputationEngine()
        for ai_config in ais:
            self.reputation_engine.register(ai_config.id, ai_config.name)
        state = DiscussionState()
        history: list[DiscussionMessage] = []
        participants = "\n".join(f"{ai.name}：{ai.self_intro or '暂无自我介绍'}" for ai in ais)
        meta_info = (
            "[用户原始问题]\n"
            f"{request.question}\n\n"
            "[参与者简介]\n"
            f"{participants}\n\n"
            "[讨论历史]\n"
        )

        for round_number in range(1, request.max_rounds + 1):
            for ai in ais:
                if self._stop_event.is_set():
                    state.final_answer = self._pick_best_answer(history, ais)
                    state.stop_reason = "manual_stop"
                    break

                yield self._format_event(
                    SSEEvent(event="ai_start", data={"ai_id": ai.id, "name": ai.name, "round": round_number})
                )

                system_prompt = self._build_system_prompt(ai.system_prompt, round_number, request.max_rounds, ai.name)
                user_content, compressed = await self._fit_context(ai, ais, meta_info, history, state.next_note)
                if compressed is not None:
                    history[:] = compressed

                full_text = ""
                async for delta in self.llm_client.stream_chat(ai, system_prompt, user_content):
                    full_text += delta
                    yield self._format_event(
                        SSEEvent(
                            event="delta",
                            data={"ai_id": ai.id, "name": ai.name, "round": round_number, "delta": delta},
                        )
                    )

                raw_confidence = self._extract_confidence(full_text)
                final_candidate = self._extract_final_answer(full_text)
                clean_text = self._strip_confidence(full_text).strip()
                calibrated_confidence = calibrate_confidence(raw_confidence, ai, full_text, history) if raw_confidence is not None else None
                history.append(
                    DiscussionMessage(
                        ai_id=ai.id,
                        ai_name=ai.name,
                        round_number=round_number,
                        content=clean_text,
                        confidence=calibrated_confidence,
                        final_answer_candidate=final_candidate,
                    )
                )

                yield self._format_event(
                    SSEEvent(
                        event="ai_log",
                        data={
                            "ai_id": ai.id,
                            "name": ai.name,
                            "round": round_number,
                            "question": request.question,
                            "system_prompt": system_prompt,
                            "user_content": user_content,
                            "raw_output": full_text,
                        },
                    )
                )

                yield self._format_event(
                    SSEEvent(
                        event="confidence",
                        data={
                            "ai_id": ai.id,
                            "name": ai.name,
                            "round": round_number,
                            "confidence": raw_confidence,
                            "calibrated": calibrated_confidence,
                            "calibration": ai.confidence_calibration,
                        },
                    )
                )
                yield self._format_event(
                    SSEEvent(event="ai_end", data={"ai_id": ai.id, "name": ai.name, "round": round_number})
                )

                if calibrated_confidence is not None and calibrated_confidence >= request.confidence_threshold:
                    state.final_answer = final_candidate or clean_text
                    state.stop_reason = "confidence_threshold"
                    yield self._format_event(
                        SSEEvent(event="final_answer", data={"answer": state.final_answer, "reason": state.stop_reason})
                    )
                    await self._persist_record(request, history, state)
                    yield self._format_event(SSEEvent(event="done", data={"reason": state.stop_reason}))
                    return

                if final_candidate and (calibrated_confidence is None or calibrated_confidence < request.confidence_threshold):
                    state.next_note = SYSTEM_NOTE
                else:
                    state.next_note = ""

            self.reputation_engine.update_after_round(history, round_number)
            if state.stop_reason:
                break

        if not state.final_answer:
            state.final_answer = self._pick_best_answer(history, ais)
            state.stop_reason = state.stop_reason or ("manual_stop" if self._stop_event.is_set() else "max_rounds")

        yield self._format_event(
            SSEEvent(event="final_answer", data={"answer": state.final_answer, "reason": state.stop_reason})
        )
        await self._persist_record(request, history, state)
        yield self._format_event(SSEEvent(event="done", data={"reason": state.stop_reason}))

    async def _persist_record(
        self,
        request: DiscussionRequest,
        history: list[DiscussionMessage],
        state: DiscussionState,
    ) -> None:
        record = DiscussionRecord(
            id=datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d%H%M%S"),
            question=request.question,
            confidence_threshold=request.confidence_threshold,
            max_rounds=request.max_rounds,
            final_answer=state.final_answer,
            stop_reason=state.stop_reason,
            messages=history,
            metadata={"message_count": len(history)},
        )
        save_discussion(record)

    def _build_system_prompt(self, role_prompt: str, round_number: int, max_rounds: int, ai_name: str) -> str:
        remaining = max_rounds - round_number
        identity = (
            f"你是多智能体讨论中的参与者，名称为 {ai_name}。\n"
            "当前轮次你只需要表达自己的观点，不要模拟其他参与者，也不要在回复中直接引用其他 AI 的名字。\n"
            "如果你要回应对方观点，请用你自己的语言总结和评述。"
        )
        rules = (
            "[讨论规则]\n"
            f"你是多专家讨论的参与者。当前为第 {round_number} 轮，最多 {max_rounds} 轮，剩余 {remaining} 轮。\n"
            "注意：早期讨论可能已被摘要，请依据最近发言推理。\n"
            "如果你认为已得到充分答案，请用 <FINAL_ANSWER>最终答案</FINAL_ANSWER> 给出。\n"
            "无论何时，回复末尾必须输出 [CONFIDENCE:0-100的整数]。"
        )
        prefix = f"{identity}\n{role_prompt}" if role_prompt else identity
        prompt = f"{prefix}\n\n{rules}".strip()

        prompt += "\n\n" + CONFIDENCE_CALIBRATION_PROMPT

        reputation_context = self.reputation_engine.get_reputation_context()
        if reputation_context:
            prompt += "\n\n" + reputation_context

        return prompt

    def _build_user_content(self, meta_info: str, history: list[DiscussionMessage], next_note: str) -> str:
        history_text = "\n\n".join(self._render_message(item) for item in history)
        content = meta_info + history_text
        if next_note:
            content += f"\n\n{next_note}"
        return content.strip()

    def _render_message(self, item: DiscussionMessage) -> str:
        if item.ai_name == "系统摘要":
            return item.content
        suffix = f"\n[CONFIDENCE:{item.confidence}]" if item.confidence is not None else ""
        return f"[第{item.round_number}轮][{item.ai_name}]\n{item.content}{suffix}"

    async def _fit_context(
        self,
        ai: AIConfig,
        ais: list[AIConfig],
        meta_info: str,
        history: list[DiscussionMessage],
        next_note: str,
    ) -> tuple[str, list[DiscussionMessage] | None]:
        working = [item.model_copy(deep=True) for item in history]
        safety_limit = min(int(ai.context_window * 0.8), ai.context_window - 1000)
        safety_limit = max(1024, safety_limit)
        content = self._build_user_content(meta_info, working, next_note)

        while self._count_tokens(content, ai.model) > safety_limit:
            target_round = self._pick_round_to_compress(working)
            if target_round is None:
                break
            original = [item for item in working if item.round_number == target_round]
            compressed_text = await self._compress_round(original, ais)
            replacement = DiscussionMessage(
                ai_id=f"summary-round-{target_round}",
                ai_name="系统摘要",
                round_number=target_round,
                content=compressed_text,
                compressed=True,
            )
            first_index = next(index for index, item in enumerate(working) if item.round_number == target_round)
            working = [item for item in working if item.round_number != target_round]
            working.insert(first_index, replacement)
            content = self._build_user_content(meta_info, working, next_note)

        return content, working if working != history else None

    def _pick_round_to_compress(self, history: list[DiscussionMessage]) -> int | None:
        if not history:
            return None
        rounds = sorted({item.round_number for item in history})
        return rounds[0]

    async def _compress_round(self, messages: list[DiscussionMessage], ais: list[AIConfig]) -> str:
        round_number = messages[0].round_number
        source_text = "\n\n".join(self._render_message(item) for item in messages)
        compressor = getattr(self, "_compressor_ai", None)
        if compressor:
            prompt = (
                "请把以下多智能体讨论压缩成中文摘要，保留关键观点、主要分歧、暂定结论和未解决问题。"
                "控制在180字以内，不要编造信息。"
            )
            try:
                chunks = []
                async for delta in self.llm_client.stream_chat(compressor, prompt, source_text):
                    chunks.append(delta)
                summary = "".join(chunks).strip()
                if summary:
                    return f"[第{round_number}轮讨论摘要]\n{summary}\n[摘要结束]"
            except Exception:
                pass

        short = source_text[:240]
        return f"[第{round_number}轮讨论摘要]\n保留关键观点、结论和分歧：{short}\n[摘要结束]"

    def _count_tokens(self, text: str, model: str) -> int:
        return self._token_counter.count(text, model)

    def _extract_confidence(self, text: str) -> int | None:
        match = CONFIDENCE_RE.search(text)
        if not match:
            return None
        return max(0, min(100, int(match.group(1))))

    def _extract_final_answer(self, text: str) -> str | None:
        match = FINAL_RE.search(text)
        return match.group(1).strip() if match else None

    def _strip_confidence(self, text: str) -> str:
        return CONFIDENCE_RE.sub("", text)

    def _pick_best_answer(self, history: list[DiscussionMessage], ais: list[AIConfig] | None = None) -> str:
        if not history:
            return "未产生有效讨论结果。"
        best = max(enumerate(history), key=lambda item: (item[1].confidence or -1, -item[0]))[1]
        return best.final_answer_candidate or best.content

    def _format_event(self, event: SSEEvent) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
