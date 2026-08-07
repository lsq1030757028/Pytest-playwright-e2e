from __future__ import annotations

import math
import time

from pydantic import BaseModel, ConfigDict, Field

from .resilience import RetrievalReplayEvidence
from .retrieval import ProgressiveMemoryRetriever, RetrievalRequest, RetrievalStage


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RetrievalBenchmarkCase(FrozenModel):
    case_id: str = Field(min_length=1)
    request: RetrievalRequest
    required_refs: tuple[str, ...] = ()
    acceptable_refs: tuple[str, ...] = ()
    unauthorized_refs: tuple[str, ...] = ()
    forgotten_refs: tuple[str, ...] = ()


class RetrievalBenchmarkReport(FrozenModel):
    case_count: int = Field(ge=1)
    repetitions: int = Field(ge=3)
    critical_unauthorized_release_count: int = Field(ge=0)
    forgotten_content_release_count: int = Field(ge=0)
    exact_ref_recall_percent: float = Field(ge=0, le=100)
    required_authority_recall_percent: float = Field(ge=0, le=100)
    noncritical_recall_percent: float = Field(ge=0, le=100)
    noncritical_precision_percent: float = Field(ge=0, le=100)
    replay_equivalence_percent: float = Field(ge=0, le=100)
    deterministic_order_percent: float = Field(ge=0, le=100)
    p95_default_latency_ms: float = Field(ge=0)
    p95_hot_latency_ms: float = Field(ge=0)
    runtime_profile: str
    passed: bool


class RetrievalBenchmarkRunner:
    """Deterministic M1B benchmark with safety thresholds as hard gates."""

    def __init__(self, retriever: ProgressiveMemoryRetriever) -> None:
        self.retriever = retriever

    def run(
        self,
        cases: tuple[RetrievalBenchmarkCase, ...],
        *,
        repetitions: int = 3,
        runtime_profile: str = "sqlite-reference-single-runner@1",
    ) -> RetrievalBenchmarkReport:
        if not cases:
            raise ValueError("benchmark requires at least one case")
        if repetitions < 3:
            raise ValueError("deterministic benchmark requires at least three repetitions")

        unauthorized_release_count = 0
        forgotten_release_count = 0
        exact_expected = 0
        exact_found = 0
        required_expected = 0
        required_found = 0
        acceptable_expected = 0
        acceptable_found = 0
        released_total = 0
        replay_total = 0
        replay_equal = 0
        order_total = 0
        order_equal = 0
        latencies: list[float] = []
        hot_latencies: list[float] = []
        first_signatures: dict[str, tuple[str, ...]] = {}
        first_manifests: dict[str, str] = {}

        for case in cases:
            acceptable_set = set(case.acceptable_refs) | set(case.required_refs)
            exact_set = set(case.request.exact_refs)
            required_set = set(case.required_refs)
            for _ in range(repetitions):
                started = time.perf_counter()
                result = self.retriever.retrieve(case.request)
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies.append(elapsed_ms)
                if result.stage_reached is RetrievalStage.HOT:
                    hot_latencies.append(elapsed_ms)

                refs = tuple(item.ref for item in result.released)
                ref_set = set(refs)
                unauthorized_release_count += len(ref_set & set(case.unauthorized_refs))
                forgotten_release_count += len(ref_set & set(case.forgotten_refs))

                exact_expected += len(exact_set)
                exact_found += len(ref_set & exact_set)
                required_expected += len(required_set)
                required_found += len(ref_set & required_set)
                acceptable_expected += len(acceptable_set)
                acceptable_found += len(ref_set & acceptable_set)
                released_total += len(ref_set)

                if case.case_id not in first_signatures:
                    first_signatures[case.case_id] = refs
                else:
                    order_total += 1
                    if refs == first_signatures[case.case_id]:
                        order_equal += 1

                evidence = RetrievalReplayEvidence.capture(
                    request=case.request,
                    result=result,
                )
                if case.case_id not in first_manifests:
                    first_manifests[case.case_id] = evidence.manifest_digest
                else:
                    replay_total += 1
                    if evidence.manifest_digest == first_manifests[case.case_id]:
                        replay_equal += 1

        exact_recall = _percent(exact_found, exact_expected)
        required_recall = _percent(required_found, required_expected)
        noncritical_recall = _percent(acceptable_found, acceptable_expected)
        precision = _percent(acceptable_found, released_total)
        replay_equivalence = _percent(replay_equal, replay_total)
        deterministic_order = _percent(order_equal, order_total)
        p95_default = _p95(latencies)
        p95_hot = _p95(hot_latencies)

        passed = all(
            (
                unauthorized_release_count == 0,
                forgotten_release_count == 0,
                exact_recall == 100.0,
                required_recall == 100.0,
                noncritical_recall >= 95.0,
                precision >= 90.0,
                replay_equivalence == 100.0,
                deterministic_order == 100.0,
                p95_default <= 3000.0,
                p95_hot <= 250.0,
            )
        )
        return RetrievalBenchmarkReport(
            case_count=len(cases),
            repetitions=repetitions,
            critical_unauthorized_release_count=unauthorized_release_count,
            forgotten_content_release_count=forgotten_release_count,
            exact_ref_recall_percent=exact_recall,
            required_authority_recall_percent=required_recall,
            noncritical_recall_percent=noncritical_recall,
            noncritical_precision_percent=precision,
            replay_equivalence_percent=replay_equivalence,
            deterministic_order_percent=deterministic_order,
            p95_default_latency_ms=round(p95_default, 3),
            p95_hot_latency_ms=round(p95_hot, 3),
            runtime_profile=runtime_profile,
            passed=passed,
        )


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 100.0
    return round(100.0 * numerator / denominator, 6)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]
