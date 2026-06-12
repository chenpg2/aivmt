"""Scoring pipeline: orchestrates scorers → CompetencyScore + Feedback."""

from __future__ import annotations

from typing import Optional, Sequence

from .llm.base import BaseLLMClient
from .scoring import BaseScorer, ScorerFactory
from .scoring.base import render_transcript
from .schemas import Case, CompetencyScore, Feedback, ScoringResult, Transcript
from .utils import get_logger

logger = get_logger(__name__)

#: Default sub-score weights for the overall competency score.
DEFAULT_WEIGHTS: dict[str, float] = {"history": 0.4, "segue": 0.4, "reasoning": 0.2}

_DEFAULT_SCORERS = ("checklist", "segue", "reasoning")

_FEEDBACK_SYS = {
    "zh": "你是带教老师,基于评分给出简短、可执行的formative反馈,只输出JSON。",
    "en": "You are a clinical tutor. Give brief, actionable formative feedback. Output JSON only.",
}


class ScoringPipeline:
    """Runs all scorers for an encounter and assembles the validated output."""

    def __init__(
        self,
        llm: BaseLLMClient,
        scorers: Optional[Sequence[BaseScorer]] = None,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        self.llm = llm
        self.scorers = list(scorers) if scorers is not None else [
            ScorerFactory(name) for name in _DEFAULT_SCORERS
        ]
        self.weights = dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS)

    def run(self, case: Case, transcript: Transcript) -> ScoringResult:
        """Score one encounter and return scores + feedback."""
        acc: dict = {}
        for scorer in self.scorers:
            acc.update(scorer.score(case, transcript, self.llm))
            logger.debug("Scorer %s done", scorer.name)

        history = float(acc.get("history_completion", 0.0))
        segue: dict[str, float] = acc.get("segue", {})
        reasoning = float(acc.get("reasoning", 0.0))
        segue_mean = sum(segue.values()) / len(segue) if segue else 0.0
        overall = (
            self.weights["history"] * history
            + self.weights["segue"] * segue_mean
            + self.weights["reasoning"] * reasoning
        )
        score = CompetencyScore(
            history_completion=history,
            segue=segue,
            reasoning=reasoning,
            overall=overall,
            item_scores=acc.get("item_scores", ()),
        )
        feedback = self._feedback(case, transcript, score)
        return ScoringResult(transcript.encounter_id, self.llm.model_id, score, feedback)

    def _feedback(self, case: Case, transcript: Transcript, score: CompetencyScore) -> Feedback:
        schema = '{"summary": "...", "strengths": ["..."], "improvements": ["..."]}'
        scores_line = (
            f"history_completion={score.history_completion:.2f}; "
            f"segue={ {k: round(v, 2) for k, v in score.segue.items()} }; "
            f"reasoning={score.reasoning:.2f}"
        )
        convo = render_transcript(transcript)
        if case.language == "zh":
            user = (
                f"病例:{case.title}\n评分:{scores_line}\n\n转录:\n{convo}\n\n"
                f"请基于评分与转录给出简短(2-3句总评)的 formative 反馈。"
                f"必须只返回JSON:{schema}"
            )
        else:
            user = (
                f"Case: {case.title}\nScores: {scores_line}\n\nTranscript:\n{convo}\n\n"
                f"Give brief formative feedback (2-3 sentence summary). Return ONLY JSON: {schema}"
            )
        out = self.llm.complete_json(_FEEDBACK_SYS[case.language], user, task="feedback")
        return Feedback(
            summary=out.get("summary", ""),
            strengths=tuple(out.get("strengths", ())),
            improvements=tuple(out.get("improvements", ())),
        )
