from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..memory_contracts import (
    AccessOperation,
    CompatibilityContext,
    LifecycleState,
    MemoryKind,
    MemoryNamespace,
    MemoryRevision,
    PrincipalContext,
    ReadMode,
    canonical_sha256,
)
from .index import IndexHit, SQLiteDerivedIndex
from .sqlite import SQLiteMemoryStore


class RetrievalStage(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class RetrievalStatus(StrEnum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_LIMITS = "COMPLETE_WITH_LIMITS"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"


class RecallChannel(StrEnum):
    EXACT_REF = "exact_ref"
    METADATA = "metadata"
    KEYWORD = "keyword"
    VECTOR = "vector"
    GRAPH = "graph"
    ARCHIVE = "archive"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageBudget(FrozenModel):
    candidate_limit: int = Field(ge=1)
    release_limit: int = Field(ge=1)
    token_limit: int = Field(ge=1)
    latency_ms: int = Field(ge=1)


DEFAULT_BUDGETS: dict[RetrievalStage, StageBudget] = {
    RetrievalStage.HOT: StageBudget(
        candidate_limit=24,
        release_limit=6,
        token_limit=2_000,
        latency_ms=250,
    ),
    RetrievalStage.WARM: StageBudget(
        candidate_limit=96,
        release_limit=12,
        token_limit=6_000,
        latency_ms=1_000,
    ),
    RetrievalStage.COLD: StageBudget(
        candidate_limit=256,
        release_limit=20,
        token_limit=12_000,
        latency_ms=3_000,
    ),
}

CHANNEL_WEIGHTS: dict[RecallChannel, float] = {
    RecallChannel.EXACT_REF: 100.0,
    RecallChannel.METADATA: 4.0,
    RecallChannel.KEYWORD: 3.0,
    RecallChannel.VECTOR: 2.0,
    RecallChannel.GRAPH: 1.0,
    RecallChannel.ARCHIVE: 1.0,
}

LIFECYCLE_PRIORITY = {
    LifecycleState.PROMOTED: 3,
    LifecycleState.VERIFIED: 2,
    LifecycleState.CANDIDATE: 1,
}


class RetrievalRequest(FrozenModel):
    request_id: str = Field(min_length=1)
    actor: PrincipalContext
    namespaces: tuple[MemoryNamespace, ...] = Field(min_length=1)
    read_mode: ReadMode
    objective_ref: str = Field(min_length=1)
    objective_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_refs: tuple[str, ...] = ()
    compatibility_context: CompatibilityContext | None = None
    evaluation_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    exact_refs: tuple[str, ...] = ()
    required_refs: tuple[str, ...] = ()
    minimum_releases: int = Field(default=1, ge=0, le=20)
    memory_kind: MemoryKind | None = None
    schema_version: str | None = None
    keywords: tuple[str, ...] = ()
    vector_query_ref: str | None = None
    graph_seed_refs: tuple[str, ...] = ()
    cold_escalation_reason: str | None = None
    cursor: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> RetrievalRequest:
        if (
            self.evaluation_time.tzinfo is None
            or self.evaluation_time.utcoffset() is None
        ):
            raise ValueError("evaluation_time must be timezone-aware")
        canonicals = [namespace.canonical for namespace in self.namespaces]
        if len(set(canonicals)) != len(canonicals):
            raise ValueError("namespaces must be unique and exact")
        return self

    def binding_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"cursor"})

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.binding_payload())


Ranker = Callable[[RetrievalRequest, tuple[MemoryRevision, ...]], tuple[str, ...]]


class ChannelContribution(FrozenModel):
    channel: RecallChannel
    rank: int = Field(ge=1)
    weighted_rrf: float = Field(ge=0)


class ReleasedMemory(FrozenModel):
    ref: str
    content_hash: str
    memory_kind: MemoryKind
    namespace: str
    lifecycle_state: LifecycleState
    content: dict[str, Any]
    fusion_score: float = Field(ge=0)
    release_reason: str
    contributions: tuple[ChannelContribution, ...]


class BudgetConsumption(FrozenModel):
    authorized_candidates: int = Field(ge=0)
    released: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)


class RetrievalResult(FrozenModel):
    status: RetrievalStatus
    stage_reached: RetrievalStage
    released: tuple[ReleasedMemory, ...]
    omitted_reasons: tuple[str, ...]
    budget: BudgetConsumption
    primary_snapshot: str
    index_snapshot: str
    filter_version: str = "m1b-filter@1"
    fusion_version: str = "weighted-rrf-k60@1"
    next_cursor: str | None = None
    evidence_digest: str


class ProgressiveMemoryRetriever:
    """M1B reference retriever: authority first, relevance second."""

    def __init__(
        self,
        store: SQLiteMemoryStore,
        *,
        index: SQLiteDerivedIndex | None = None,
        cursor_key: bytes,
        vector_ranker: Ranker | None = None,
        graph_ranker: Ranker | None = None,
        monotonic_ms: Callable[[], int] | None = None,
        sync_index: bool = True,
    ) -> None:
        if len(cursor_key) < 16:
            raise ValueError("cursor_key must contain at least 16 bytes")
        self.store = store
        self.index = index
        self.cursor_key = cursor_key
        self.vector_ranker = vector_ranker
        self.graph_ranker = graph_ranker
        self.monotonic_ms = monotonic_ms or (
            lambda: int(time.perf_counter() * 1000)
        )
        self.sync_index = sync_index

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        started = self.monotonic_ms()
        omitted: list[str] = []
        degraded = False

        permissions = [
            self.store.evaluate_permission(
                actor=request.actor,
                namespace=namespace,
                operation=AccessOperation.QUERY,
            )
            for namespace in request.namespaces
        ]
        if any(not permission.allowed for permission in permissions):
            return self._empty_result(
                request=request,
                status=RetrievalStatus.BLOCKED,
                stage=RetrievalStage.HOT,
                omitted=("AUTHORITY_BLOCKED",),
                started=started,
            )

        index_available = self.index is not None
        if self.index is not None and self.sync_index:
            try:
                while self.index.apply_pending(limit=256):
                    pass
            except sqlite3.Error:
                index_available = False
                degraded = True
                omitted.append("INDEX_UNAVAILABLE_PRIMARY_HOT_FALLBACK")
        elif self.index is None:
            degraded = True
            omitted.append("INDEX_UNAVAILABLE_PRIMARY_HOT_FALLBACK")

        if (
            index_available
            and self.index is not None
            and self.index.pending_count() > 0
        ):
            degraded = True
            omitted.append("INDEX_STALE_PRIMARY_REVALIDATION_REQUIRED")

        eligible = self._eligible_revisions(request)
        eligible = tuple(
            revision
            for revision in eligible
            if (
                request.memory_kind is None
                or revision.memory_kind is request.memory_kind
            )
            and (
                request.schema_version is None
                or revision.schema_version == request.schema_version
            )
        )
        eligible_map = {revision.ref: revision for revision in eligible}
        primary_snapshot = self._primary_snapshot(eligible)
        index_snapshot = (
            self.index.snapshot_digest(eligible_refs=tuple(eligible_map))
            if index_available and self.index is not None
            else canonical_sha256({"index": "unavailable"})
        )
        acl_epoch, forget_epoch = self._authority_epochs(request)

        cursor_stage: RetrievalStage | None = None
        offset = 0
        if request.cursor is not None:
            payload = self._decode_cursor(request.cursor)
            expected = self._cursor_binding(
                request=request,
                primary_snapshot=primary_snapshot,
                index_snapshot=index_snapshot,
                acl_epoch=acl_epoch,
                forget_epoch=forget_epoch,
            )
            for key, value in expected.items():
                if payload.get(key) != value:
                    raise ValueError(f"cursor binding mismatch: {key}")
            cursor_stage = RetrievalStage(payload["stage"])
            offset = int(payload["offset"])
            if offset < 0:
                raise ValueError("cursor offset is invalid")

        if not eligible:
            status = (
                RetrievalStatus.DEGRADED
                if degraded
                else RetrievalStatus.INSUFFICIENT_EVIDENCE
            )
            return self._empty_result(
                request=request,
                status=status,
                stage=RetrievalStage.HOT,
                omitted=tuple(omitted) or ("NO_EFFECTIVE_MEMORY",),
                started=started,
                primary_snapshot=primary_snapshot,
                index_snapshot=index_snapshot,
            )

        strong_refs = set(request.required_refs) | set(request.exact_refs)
        if not strong_refs <= set(eligible_map):
            missing_exact = not set(request.exact_refs) <= set(eligible_map)
            reason = (
                "EXACT_REF_UNRESOLVED"
                if missing_exact
                else "REQUIRED_REF_UNRESOLVED"
            )
            status = (
                RetrievalStatus.DEGRADED
                if degraded
                else RetrievalStatus.INSUFFICIENT_EVIDENCE
            )
            return self._empty_result(
                request=request,
                status=status,
                stage=RetrievalStage.HOT,
                omitted=tuple(omitted) + (reason,),
                started=started,
                primary_snapshot=primary_snapshot,
                index_snapshot=index_snapshot,
            )

        stages = (
            [cursor_stage]
            if cursor_stage is not None
            else [RetrievalStage.HOT, RetrievalStage.WARM, RetrievalStage.COLD]
        )
        final_stage = RetrievalStage.HOT
        final_ranked: list[
            tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
        ] = []
        final_candidates = 0
        status = RetrievalStatus.INSUFFICIENT_EVIDENCE

        for stage in stages:
            if stage is None:
                continue
            if stage is not RetrievalStage.HOT and not index_available:
                break
            if stage is RetrievalStage.COLD and not request.cold_escalation_reason:
                omitted.append("COLD_ESCALATION_REASON_REQUIRED")
                break

            budget = DEFAULT_BUDGETS[stage]
            channel_ranks, channel_omissions = self._channel_ranks(
                request=request,
                eligible=eligible,
                stage=stage,
                index_available=index_available,
            )
            for reason in channel_omissions:
                if reason not in omitted:
                    omitted.append(reason)
                    degraded = True

            ranked = self._fuse(eligible, channel_ranks)
            ranked = ranked[: budget.candidate_limit]
            final_stage = stage
            final_ranked = ranked
            final_candidates = len(ranked)

            preview, _tokens = self._page_with_budget(
                ranked,
                offset=offset,
                release_limit=budget.release_limit,
                token_limit=budget.token_limit,
            )
            coverage_met = self._coverage_met(
                request=request,
                stage=stage,
                preview=preview,
                cursor_page=cursor_stage is not None,
            )
            elapsed = max(0, self.monotonic_ms() - started)
            if coverage_met:
                status = (
                    RetrievalStatus.DEGRADED
                    if degraded
                    else RetrievalStatus.COMPLETE
                )
                break
            if elapsed >= budget.latency_ms:
                status = (
                    RetrievalStatus.DEGRADED
                    if degraded
                    else RetrievalStatus.COMPLETE_WITH_LIMITS
                )
                omitted.append("TIME_BUDGET_EXHAUSTED")
                break
            if stage is RetrievalStage.HOT and not index_available:
                status = RetrievalStatus.DEGRADED
                break
            if stage is RetrievalStage.WARM and not request.cold_escalation_reason:
                status = (
                    RetrievalStatus.DEGRADED
                    if degraded
                    else RetrievalStatus.COMPLETE_WITH_LIMITS
                )
                break
            if stage is RetrievalStage.COLD:
                status = (
                    RetrievalStatus.DEGRADED
                    if degraded
                    else RetrievalStatus.INSUFFICIENT_EVIDENCE
                )

        budget = DEFAULT_BUDGETS[final_stage]
        page, estimated_tokens = self._page_with_budget(
            final_ranked,
            offset=offset,
            release_limit=budget.release_limit,
            token_limit=budget.token_limit,
        )

        revalidated = {
            revision.ref: revision for revision in self._eligible_revisions(request)
        }
        released: list[ReleasedMemory] = []
        for revision, score, contributions in page:
            current = revalidated.get(revision.ref)
            if current is None or current.content_hash != revision.content_hash:
                if "PRIMARY_REVALIDATION_REJECTED" not in omitted:
                    omitted.append("PRIMARY_REVALIDATION_REJECTED")
                degraded = True
                continue
            state = self.store.get_effective_state(memory_id=current.memory_id)
            released.append(
                ReleasedMemory(
                    ref=current.ref,
                    content_hash=current.content_hash,
                    memory_kind=current.memory_kind,
                    namespace=current.namespace.canonical,
                    lifecycle_state=state,
                    content=dict(current.content),
                    fusion_score=score,
                    release_reason=(
                        "PRIMARY_REVALIDATED_AFTER_AUTHORITY_FIRST_FILTER"
                    ),
                    contributions=contributions,
                )
            )

        if degraded and status not in {
            RetrievalStatus.BLOCKED,
            RetrievalStatus.INSUFFICIENT_EVIDENCE,
        }:
            status = RetrievalStatus.DEGRADED
        if not released and status in {
            RetrievalStatus.COMPLETE,
            RetrievalStatus.COMPLETE_WITH_LIMITS,
        }:
            status = RetrievalStatus.INSUFFICIENT_EVIDENCE

        next_cursor = None
        next_offset = offset + len(page)
        if page and next_offset < len(final_ranked):
            cursor_payload = self._cursor_binding(
                request=request,
                primary_snapshot=primary_snapshot,
                index_snapshot=index_snapshot,
                acl_epoch=acl_epoch,
                forget_epoch=forget_epoch,
            )
            cursor_payload.update(
                {"stage": final_stage.value, "offset": next_offset}
            )
            next_cursor = self._encode_cursor(cursor_payload)

        elapsed = max(0, self.monotonic_ms() - started)
        evidence_payload = {
            "request_digest": request.request_digest,
            "stage": final_stage.value,
            "status": status.value,
            "released": [
                {
                    "ref": item.ref,
                    "hash": item.content_hash,
                    "score": item.fusion_score,
                }
                for item in released
            ],
            "omitted": tuple(omitted),
            "primary_snapshot": primary_snapshot,
            "index_snapshot": index_snapshot,
            "acl_epoch": acl_epoch,
            "forget_epoch": forget_epoch,
        }
        return RetrievalResult(
            status=status,
            stage_reached=final_stage,
            released=tuple(released),
            omitted_reasons=tuple(omitted),
            budget=BudgetConsumption(
                authorized_candidates=final_candidates,
                released=len(released),
                estimated_tokens=estimated_tokens,
                elapsed_ms=elapsed,
            ),
            primary_snapshot=primary_snapshot,
            index_snapshot=index_snapshot,
            next_cursor=next_cursor,
            evidence_digest=canonical_sha256(evidence_payload),
        )

    def _coverage_met(
        self,
        *,
        request: RetrievalRequest,
        stage: RetrievalStage,
        preview: list[
            tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
        ],
        cursor_page: bool,
    ) -> bool:
        if cursor_page:
            return bool(preview)
        if stage is RetrievalStage.HOT and (
            request.vector_query_ref or request.graph_seed_refs
        ):
            return False
        refs = {revision.ref for revision, _score, _contributions in preview}
        if len(preview) < request.minimum_releases:
            return False
        if not (set(request.required_refs) | set(request.exact_refs)) <= refs:
            return False
        if request.keywords:
            has_keyword = any(
                contribution.channel is RecallChannel.KEYWORD
                for _revision, _score, contributions in preview
                for contribution in contributions
            )
            if not has_keyword:
                return False
        return True

    def _eligible_revisions(
        self, request: RetrievalRequest
    ) -> tuple[MemoryRevision, ...]:
        if request.read_mode is ReadMode.ADVISORY:
            modes = (
                ReadMode.ADVISORY,
                ReadMode.EVIDENCE_BEARING,
                ReadMode.PRODUCTION_RETRIEVAL,
            )
        elif request.read_mode is ReadMode.EVIDENCE_BEARING:
            modes = (
                ReadMode.EVIDENCE_BEARING,
                ReadMode.PRODUCTION_RETRIEVAL,
            )
        else:
            modes = (ReadMode.PRODUCTION_RETRIEVAL,)
        selected: dict[str, MemoryRevision] = {}
        for mode in modes:
            revisions, _cursor = self.store.query_exact_authorized_namespaces(
                actor=request.actor,
                namespaces=request.namespaces,
                read_mode=mode,
                compatibility_context=request.compatibility_context,
                now=request.evaluation_time,
                limit=DEFAULT_BUDGETS[RetrievalStage.COLD].candidate_limit,
            )
            selected.update({revision.ref: revision for revision in revisions})
        return tuple(
            sorted(
                selected.values(),
                key=lambda revision: (
                    revision.namespace.canonical,
                    revision.ref,
                ),
            )
        )

    def _channel_ranks(
        self,
        *,
        request: RetrievalRequest,
        eligible: tuple[MemoryRevision, ...],
        stage: RetrievalStage,
        index_available: bool,
    ) -> tuple[dict[RecallChannel, tuple[str, ...]], tuple[str, ...]]:
        eligible_refs = tuple(revision.ref for revision in eligible)
        eligible_set = set(eligible_refs)
        channels: dict[RecallChannel, tuple[str, ...]] = {}
        omissions: list[str] = []

        channels[RecallChannel.EXACT_REF] = tuple(
            ref for ref in request.exact_refs if ref in eligible_set
        )

        if index_available and self.index is not None:
            metadata = self.index.metadata_rank(
                eligible_refs=eligible_refs,
                memory_kind=(
                    request.memory_kind.value if request.memory_kind else None
                ),
                schema_version=request.schema_version,
            )
            channels[RecallChannel.METADATA] = tuple(
                hit.ref for hit in metadata
            )
            if request.keywords:
                keyword = self.index.keyword_rank(
                    eligible_refs=eligible_refs,
                    keywords=request.keywords,
                )
                channels[RecallChannel.KEYWORD] = tuple(
                    hit.ref for hit in keyword
                )
        else:
            channels[RecallChannel.METADATA] = tuple(
                revision.ref
                for revision in sorted(
                    eligible,
                    key=lambda item: (item.created_at, item.ref),
                    reverse=True,
                )
            )
            if request.keywords:
                channels[RecallChannel.KEYWORD] = tuple(
                    hit.ref
                    for hit in self._primary_keyword_rank(
                        eligible, request.keywords
                    )
                )

        if stage in {RetrievalStage.WARM, RetrievalStage.COLD}:
            if request.vector_query_ref:
                if self.vector_ranker is None:
                    omissions.append("VECTOR_UNAVAILABLE")
                else:
                    channels[RecallChannel.VECTOR] = self._safe_adapter_ranks(
                        self.vector_ranker(request, eligible),
                        eligible_set,
                    )
            if request.graph_seed_refs:
                if self.graph_ranker is None:
                    omissions.append("GRAPH_UNAVAILABLE")
                else:
                    channels[RecallChannel.GRAPH] = self._safe_adapter_ranks(
                        self.graph_ranker(request, eligible),
                        eligible_set,
                    )
        if stage is RetrievalStage.COLD and self.index is not None:
            channels[RecallChannel.ARCHIVE] = tuple(
                hit.ref
                for hit in self.index.archive_rank(
                    eligible_refs=eligible_refs
                )
            )
        return channels, tuple(omissions)

    @staticmethod
    def _safe_adapter_ranks(
        refs: tuple[str, ...], eligible_set: set[str]
    ) -> tuple[str, ...]:
        seen: set[str] = set()
        safe: list[str] = []
        for ref in refs:
            if ref in eligible_set and ref not in seen:
                safe.append(ref)
                seen.add(ref)
        return tuple(safe)

    @staticmethod
    def _primary_keyword_rank(
        eligible: tuple[MemoryRevision, ...], keywords: tuple[str, ...]
    ) -> tuple[IndexHit, ...]:
        normalized = {
            keyword.casefold() for keyword in keywords if keyword.strip()
        }
        scored: list[tuple[int, datetime, str]] = []
        for revision in eligible:
            text = json.dumps(
                revision.content,
                ensure_ascii=False,
                sort_keys=True,
            ).casefold()
            matched = sum(1 for keyword in normalized if keyword in text)
            if matched:
                scored.append((matched, revision.created_at, revision.ref))
        scored.sort(
            key=lambda item: (-item[0], -item[1].timestamp(), item[2])
        )
        return tuple(
            IndexHit(ref=ref, rank=rank, score=matched)
            for rank, (matched, _created_at, ref) in enumerate(
                scored, start=1
            )
        )

    def _fuse(
        self,
        eligible: tuple[MemoryRevision, ...],
        channel_ranks: dict[RecallChannel, tuple[str, ...]],
    ) -> list[
        tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
    ]:
        eligible_map = {revision.ref: revision for revision in eligible}
        contribution_map: dict[str, list[ChannelContribution]] = {}
        for channel, refs in channel_ranks.items():
            for rank, ref in enumerate(refs, start=1):
                if ref not in eligible_map:
                    continue
                value = round(
                    CHANNEL_WEIGHTS[channel] / (60 + rank), 12
                )
                contribution_map.setdefault(ref, []).append(
                    ChannelContribution(
                        channel=channel,
                        rank=rank,
                        weighted_rrf=value,
                    )
                )
        ranked: list[
            tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
        ] = []
        for ref, contributions in contribution_map.items():
            revision = eligible_map[ref]
            score = round(
                sum(item.weighted_rrf for item in contributions), 12
            )
            ranked.append((revision, score, tuple(contributions)))

        def sort_key(
            item: tuple[
                MemoryRevision,
                float,
                tuple[ChannelContribution, ...],
            ],
        ):
            revision, score, contributions = item
            exact = any(
                contribution.channel is RecallChannel.EXACT_REF
                for contribution in contributions
            )
            state = self.store.get_effective_state(
                memory_id=revision.memory_id
            )
            return (
                -score,
                -int(exact),
                -len(contributions),
                -LIFECYCLE_PRIORITY.get(state, 0),
                -revision.created_at.timestamp(),
                revision.namespace.canonical,
                revision.ref,
            )

        ranked.sort(key=sort_key)
        return ranked

    @staticmethod
    def _estimate_tokens(revision: MemoryRevision) -> int:
        encoded = json.dumps(
            revision.content,
            ensure_ascii=False,
            sort_keys=True,
        )
        return max(1, math.ceil(len(encoded) / 4))

    def _page_with_budget(
        self,
        ranked: list[
            tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
        ],
        *,
        offset: int,
        release_limit: int,
        token_limit: int,
    ) -> tuple[
        list[tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]],
        int,
    ]:
        selected: list[
            tuple[MemoryRevision, float, tuple[ChannelContribution, ...]]
        ] = []
        tokens = 0
        for item in ranked[offset:]:
            if len(selected) >= release_limit:
                break
            cost = self._estimate_tokens(item[0])
            if selected and tokens + cost > token_limit:
                break
            if not selected and cost > token_limit:
                break
            selected.append(item)
            tokens += cost
        return selected, tokens

    @staticmethod
    def _primary_snapshot(revisions: tuple[MemoryRevision, ...]) -> str:
        return canonical_sha256(
            [
                {
                    "ref": revision.ref,
                    "hash": revision.content_hash,
                    "created_at": revision.created_at,
                }
                for revision in sorted(
                    revisions, key=lambda item: item.ref
                )
            ]
        )

    def _namespace_digest(self, request: RetrievalRequest) -> str:
        return canonical_sha256(
            sorted(namespace.canonical for namespace in request.namespaces)
        )

    def _cursor_binding(
        self,
        *,
        request: RetrievalRequest,
        primary_snapshot: str,
        index_snapshot: str,
        acl_epoch: str,
        forget_epoch: str,
    ) -> dict[str, Any]:
        return {
            "request_digest": request.request_digest,
            "actor_digest": canonical_sha256(request.actor),
            "namespace_digest": self._namespace_digest(request),
            "read_mode": request.read_mode.value,
            "primary_snapshot": primary_snapshot,
            "index_snapshot": index_snapshot,
            "acl_epoch": acl_epoch,
            "forget_epoch": forget_epoch,
            "filter_version": "m1b-filter@1",
            "fusion_version": "weighted-rrf-k60@1",
        }

    def _authority_epochs(
        self, request: RetrievalRequest
    ) -> tuple[str, str]:
        namespace_set = {
            namespace.canonical for namespace in request.namespaces
        }
        namespace_hashes = {
            namespace.namespace_hash for namespace in request.namespaces
        }
        with closing(sqlite3.connect(self.store.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            acl_rows = connection.execute(
                """
                SELECT namespace, rule_id, payload_json
                FROM acl_events
                ORDER BY sequence
                """
            ).fetchall()
            tombstone_rows = connection.execute(
                """
                SELECT memory_id, payload_json
                FROM tombstones
                ORDER BY memory_id
                """
            ).fetchall()
        acl_epoch = canonical_sha256(
            [
                {
                    "namespace": row["namespace"],
                    "rule_id": row["rule_id"],
                    "payload": json.loads(row["payload_json"]),
                }
                for row in acl_rows
                if row["namespace"] in namespace_set
            ]
        )
        tombstone_payloads: list[dict[str, Any]] = []
        for row in tombstone_rows:
            payload = json.loads(row["payload_json"])
            if payload["namespace_hash"] in namespace_hashes:
                tombstone_payloads.append(
                    {"memory_id": row["memory_id"], "payload": payload}
                )
        forget_epoch = canonical_sha256(tombstone_payloads)
        return acl_epoch, forget_epoch

    def _encode_cursor(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = hmac.new(
            self.cursor_key, raw, hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(signature + raw).decode().rstrip("=")

    def _decode_cursor(self, cursor: str) -> dict[str, Any]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode())
            signature, raw = decoded[:32], decoded[32:]
        except Exception as exc:
            raise ValueError("cursor is malformed") from exc
        expected = hmac.new(
            self.cursor_key, raw, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("cursor integrity check failed")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("cursor payload is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("cursor payload must be an object")
        return payload

    def _empty_result(
        self,
        *,
        request: RetrievalRequest,
        status: RetrievalStatus,
        stage: RetrievalStage,
        omitted: tuple[str, ...],
        started: int,
        primary_snapshot: str | None = None,
        index_snapshot: str | None = None,
    ) -> RetrievalResult:
        primary = primary_snapshot or canonical_sha256([])
        index = index_snapshot or canonical_sha256({"index": "none"})
        elapsed = max(0, self.monotonic_ms() - started)
        evidence = canonical_sha256(
            {
                "request": request.request_digest,
                "status": status.value,
                "stage": stage.value,
                "omitted": omitted,
                "primary_snapshot": primary,
                "index_snapshot": index,
            }
        )
        return RetrievalResult(
            status=status,
            stage_reached=stage,
            released=(),
            omitted_reasons=omitted,
            budget=BudgetConsumption(
                authorized_candidates=0,
                released=0,
                estimated_tokens=0,
                elapsed_ms=elapsed,
            ),
            primary_snapshot=primary,
            index_snapshot=index,
            evidence_digest=evidence,
        )
