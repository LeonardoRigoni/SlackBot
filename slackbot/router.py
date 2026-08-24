from __future__ import annotations

from dataclasses import dataclass

from slackbot.llm import LlmDecision, LlmRouter
from slackbot.rules import ChannelRule, find_keyword_rule, rules_to_prompt


@dataclass(frozen=True)
class RouteResult:
    target_channel: str | None
    keyword: str | None
    confidence: float
    priority: str
    summary: str
    questions: list[str]
    reason: str
    requires_manual_choice: bool
    requires_confirmation: bool


class MessageRouter:
    def __init__(
        self,
        llm: LlmRouter,
        rules: list[ChannelRule],
        confidence_threshold: float,
        auto_route_confidence_threshold: float,
        allow_llm_generated_questions: bool,
    ) -> None:
        self.llm = llm
        self.rules = rules
        self.confidence_threshold = confidence_threshold
        self.auto_route_confidence_threshold = auto_route_confidence_threshold
        self.allow_llm_generated_questions = allow_llm_generated_questions

    def route(self, message: str) -> RouteResult:
        allowed_channels = [rule.name for rule in self.rules]
        decision = self.llm.decide(
            message=message,
            rules_prompt=rules_to_prompt(self.rules),
            allowed_channels=allowed_channels,
            allow_generated_questions=self.allow_llm_generated_questions,
        )
        return self._normalize_decision(decision)

    def _normalize_decision(self, decision: LlmDecision) -> RouteResult:
        if not decision.target_channel or decision.confidence < self.confidence_threshold:
            return RouteResult(
                target_channel=None,
                keyword=decision.keyword,
                confidence=decision.confidence,
                priority=decision.priority,
                summary=decision.summary,
                questions=[],
                reason=decision.reason,
                requires_manual_choice=True,
                requires_confirmation=False,
            )

        keyword_rule = find_keyword_rule(self.rules, decision.target_channel, decision.keyword)
        configured_questions = keyword_rule.questions if keyword_rule else []
        questions = self._select_questions(decision, configured_questions)

        return RouteResult(
            target_channel=decision.target_channel,
            keyword=decision.keyword,
            confidence=decision.confidence,
            priority=decision.priority,
            summary=decision.summary,
            questions=questions,
            reason=decision.reason,
            requires_manual_choice=False,
            requires_confirmation=decision.confidence < self.auto_route_confidence_threshold,
        )

    def _select_questions(self, decision: LlmDecision, configured_questions: list[str]) -> list[str]:
        if not decision.needs_more_info:
            return []

        if configured_questions:
            configured_by_lower = {question.lower(): question for question in configured_questions}
            selected = [
                configured_by_lower[question.lower()]
                for question in decision.questions
                if question.lower() in configured_by_lower
            ]
            return selected

        if self.allow_llm_generated_questions:
            return decision.questions

        return []
