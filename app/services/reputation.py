"""
动态信誉引擎
在每轮讨论结束后，根据 AI 的客观行为自动更新信誉分数。
不需要额外的 AI 调用，纯规则计算。
"""

import re
from dataclasses import dataclass, field

from app.models import AIConfig, DiscussionMessage


@dataclass
class ReputationRecord:
    """单个 AI 的信誉记录"""
    ai_id: str
    ai_name: str
    score: float = 50.0  # 初始 50，范围 0-100
    history: list[float] = field(default_factory=list)  # 历史分数变化记录

    def update(self, delta: float, reason: str):
        self.score = max(0, min(100, self.score + delta))
        self.history.append(delta)


class ReputationEngine:
    """动态信誉引擎"""

    def __init__(self):
        self.records: dict[str, ReputationRecord] = {}

    def register(self, ai_id: str, ai_name: str):
        """注册一个 AI 参与者"""
        if ai_id not in self.records:
            self.records[ai_id] = ReputationRecord(ai_id=ai_id, ai_name=ai_name)

    def update_after_round(self, messages: list[DiscussionMessage], current_round: int):
        """一轮讨论结束后更新所有 AI 的信誉"""
        round_messages = [m for m in messages if m.round_number == current_round]
        all_messages = messages  # 包含历史消息

        for msg in round_messages:
            if msg.ai_id not in self.records:
                continue

            record = self.records[msg.ai_id]

            # 1. 被引用：后续 AI 的发言中提到了该 AI 的名字并表示认同
            subsequent = [m for m in all_messages if m.round_number > current_round or
                         (m.round_number == current_round and all_messages.index(m) > all_messages.index(msg))]

            for later_msg in subsequent:
                if msg.ai_name in later_msg.content:
                    # 检查是认同还是反驳
                    if self._is_agreement(later_msg.content, msg.ai_name):
                        record.update(10, f"被 {later_msg.ai_name} 引用并认同")
                    elif self._is_rebuttal(later_msg.content, msg.ai_name):
                        record.update(-15, f"被 {later_msg.ai_name} 反驳")

            # 2. 高置信低采纳
            if msg.confidence and msg.confidence > 80:
                was_cited = any(msg.ai_name in m.content for m in subsequent)
                if not was_cited:
                    record.update(-5, "高置信度但未被引用")

            # 3. 低置信低贡献
            if msg.confidence and msg.confidence < 40:
                record.update(-3, "低置信度")

            # 4. 推进共识：发言后下一轮平均置信度上升
            next_round = [m for m in all_messages if m.round_number == current_round + 1]
            if next_round and msg.confidence:
                current_avg = sum(m.confidence for m in round_messages if m.confidence) / max(1, len([m for m in round_messages if m.confidence]))
                next_avg = sum(m.confidence for m in next_round if m.confidence) / max(1, len([m for m in next_round if m.confidence]))
                if next_avg > current_avg:
                    record.update(5, "推进共识")

    def get_weight(self, ai_id: str) -> float:
        """获取 AI 的最终权重（0-1），结合静态画像和动态信誉"""
        if ai_id not in self.records:
            return 0.5

        record = self.records[ai_id]
        # 静态画像占 30%，动态信誉占 70%
        # 这里静态画像暂时用默认值 50，后续可接入能力画像
        static_score = 50
        dynamic_weight = (static_score * 0.3 + record.score * 0.7) / 100
        return max(0.1, min(1.0, dynamic_weight))

    def get_reputation_context(self) -> str:
        """生成信誉上下文，注入到下一轮的系统提示中"""
        if not self.records:
            return ""

        lines = ["[参与者动态信誉]"]
        for record in self.records.values():
            weight = self.get_weight(record.ai_id)
            level = "高" if weight > 0.7 else ("中" if weight > 0.4 else "低")
            lines.append(f"- {record.ai_name}：当前讨论权重 {level}（{weight:.2f}），信誉分 {record.score:.0f}/100")

        return "\n".join(lines)

    @staticmethod
    def _is_agreement(content: str, name: str) -> bool:
        """判断后续发言是否表示认同"""
        agreement_patterns = [
            f"{name}.*正确", f"{name}.*说得对", f"同意.*{name}",
            f"{name}.*有道理", f"支持.*{name}", f"{name}.*的观点.*很好",
            f"补充.*{name}", f"基于.*{name}", f"正如.*{name}",
        ]
        return any(re.search(p, content) for p in agreement_patterns)

    @staticmethod
    def _is_rebuttal(content: str, name: str) -> bool:
        """判断后续发言是否表示反驳"""
        rebuttal_patterns = [
            f"{name}.*不对", f"{name}.*错了", f"反驳.*{name}",
            f"不同意.*{name}", f"{name}.*的问题", f"{name}.*忽略",
            f"但是.*{name}", f"然而.*{name}", f"不过.*{name}",
        ]
        return any(re.search(p, content) for p in rebuttal_patterns)
