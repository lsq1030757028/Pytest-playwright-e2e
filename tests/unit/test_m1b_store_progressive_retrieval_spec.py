from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_MD = ROOT / "docs/specs/m1b-store-progressive-retrieval-spec.md"
SPEC_YAML = ROOT / "docs/specs/m1b-store-progressive-retrieval.yaml"
THREAT_MD = ROOT / "docs/security/m1b-store-progressive-retrieval-threat-model.md"
TEST_DESIGN_MD = ROOT / "docs/testing/m1b-store-progressive-retrieval-test-design.md"
WORKFLOW = ROOT / ".github/workflows/m1b-store-progressive-retrieval-spec.yml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_spec_identity_authority_and_beta_role_are_truthful() -> None:
    spec = load_yaml(SPEC_YAML)
    markdown = SPEC_MD.read_text(encoding="utf-8")

    assert spec["spec_id"] == "SPEC-M1B-STORE-PROGRESSIVE-RETRIEVAL"
    assert spec["version"] == "0.1.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 62
    assert spec["work_item_id"] == "M1B-STORE-RETRIEVAL-SPEC"
    assert spec["parent_campaign_issue"] == 59
    assert spec["top_level_campaign_issue"] == 65
    assert spec["beta_slice_support"] == "BETA-D"
    assert spec["blocks_beta_a"] is False
    assert spec["product_claim"] == "SPEC_ONLY"
    assert "It is a subsystem, not the product endpoint" in markdown
    assert "This SPEC PR contains no runtime implementation" in markdown


def test_no_normative_vendor_is_selected() -> None:
    spec = load_yaml(SPEC_YAML)
    selection = spec["normative_vendor_selection"]

    assert set(selection) == {
        "database",
        "vector_engine",
        "embedding_provider",
        "graph_engine",
        "cache",
        "cloud",
    }
    assert set(selection.values()) == {"UNSELECTED"}
    assert spec["vendor_neutrality"] == {
        "physical_adapter_may_vary": True,
        "logical_memory_id_stable_across_migration": True,
        "canonical_content_hash_stable_across_migration": True,
        "relevance_provider_is_not_authority": True,
    }


def test_all_m1a_ports_and_authority_invariants_are_preserved() -> None:
    spec = load_yaml(SPEC_YAML)
    preserved = spec["m1a_contracts_preserved"]

    assert set(preserved["ports"]) == {
        "MemoryRevisionPort",
        "MemoryStatePort",
        "MemoryAclPort",
        "MemoryQueryPort",
        "MemoryAuditPort",
        "MemoryMaintenancePort",
    }
    assert {
        "immutable_revision",
        "append_only_state_acl_audit_events",
        "authenticated_principal",
        "namespace_before_relevance",
        "acl_before_content_release",
        "provenance_and_content_hash",
        "head_compare_and_swap",
        "idempotency_bound_to_authenticated_request",
        "retention_revoke_expire_forget",
        "candidate_never_becomes_oracle",
    } == set(preserved["invariants"])


def test_primary_store_remains_authoritative_over_indexes_and_cache() -> None:
    spec = load_yaml(SPEC_YAML)
    authority = spec["store_authority"]

    assert authority["primary_store_authoritative"] is True
    assert authority["indexes_are_derived"] is True
    assert authority["caches_are_derived"] is True
    assert authority["search_scores_are_non_authoritative"] is True
    assert authority["content_release_requires_primary_revalidation"] is True
    assert authority["index_or_cache_cannot_resurrect_invalid_memory"] is True


def test_physical_isolation_happens_before_search() -> None:
    spec = load_yaml(SPEC_YAML)
    isolation = spec["physical_isolation"]
    pipeline = spec["filter_pipeline"]

    assert isolation["authorized_partition_handles_before_search"] is True
    assert isolation["global_cross_project_search"] is False
    assert isolation["shared_scope_requires_membership_and_acl"] is True
    assert isolation["unauthorized_candidate_counts_visible"] is False
    assert isolation["unauthorized_similarity_visible"] is False
    assert pipeline["order"][:5] == [
        "authenticate_principal",
        "resolve_exact_namespace_handles",
        "evaluate_acl",
        "resolve_head_and_effective_lifecycle",
        "apply_retention_and_forget_barrier",
    ]
    assert pipeline["order"][-3:] == [
        "discover_and_rank_relevance",
        "primary_revalidate_selected_refs",
        "release_content",
    ]
    assert set(pipeline["filter_before_ranking"].values()) == {True}


def test_mutation_transactions_are_atomic_and_audited() -> None:
    spec = load_yaml(SPEC_YAML)
    transactions = spec["transaction_contract"]

    assert transactions["all_or_nothing"] is True
    assert transactions["acknowledgement_requires_commit"] is True
    assert transactions["partial_commit_result"] == "INVALID_TRANSACTION"
    assert set(transactions["append_revision"]) == {
        "idempotency_reservation",
        "immutable_revision_append",
        "head_compare_and_swap",
        "audit_event_append",
        "index_outbox_append",
    }
    assert "acl_epoch_advance" in transactions["acl_change"]
    assert "content_release_barrier_advance" in transactions["forget"]
    assert "invalidation_outbox_append" in transactions["forget"]


def test_consistency_and_outbox_rules_fail_closed() -> None:
    spec = load_yaml(SPEC_YAML)
    consistency = spec["consistency"]

    assert consistency["per_logical_memory_write"] == "SERIALIZABLE_OR_EQUIVALENT"
    assert consistency["compare_and_append_conflict"] == "EXPLICIT_CONFLICT"
    assert consistency["query_view"] == "PRIMARY_VALIDATED_SNAPSHOT"
    assert consistency["read_your_writes"] is True
    assert consistency["monotonic_head_reads"] is True
    assert consistency["index_delivery"] == "AT_LEAST_ONCE_IDEMPOTENT"
    assert consistency["outbox_sequence_per_namespace"] == "MONOTONIC"
    assert consistency["cache_fill_after_primary_validation"] is True


def test_read_modes_never_release_invalid_lifecycle_states() -> None:
    spec = load_yaml(SPEC_YAML)
    policy = spec["lifecycle_release_policy"]

    assert policy["ADVISORY"]["allowed"] == ["CANDIDATE", "VERIFIED", "PROMOTED"]
    assert policy["ADVISORY"]["candidate_must_be_labeled"] is True
    assert policy["EVIDENCE_BEARING"]["allowed"] == ["VERIFIED", "PROMOTED"]
    assert policy["PRODUCTION_RETRIEVAL"]["allowed"] == ["PROMOTED"]
    assert set(policy["always_excluded"]) == {
        "CONFLICTING",
        "QUARANTINED",
        "SUPERSEDED",
        "REVOKED",
        "EXPIRED",
        "FORGOTTEN",
    }


def test_progressive_stages_are_ordered_and_cumulatively_bounded() -> None:
    spec = load_yaml(SPEC_YAML)
    stages = spec["progressive_stages"]

    assert [stages[name]["order"] for name in ("HOT", "WARM", "COLD")] == [1, 2, 3]
    assert [
        stages[name]["candidate_limit"] for name in ("HOT", "WARM", "COLD")
    ] == [24, 96, 256]
    assert [stages[name]["release_limit"] for name in ("HOT", "WARM", "COLD")] == [
        6,
        12,
        20,
    ]
    assert [stages[name]["token_limit"] for name in ("HOT", "WARM", "COLD")] == [
        2000,
        6000,
        12000,
    ]
    assert [
        stages[name]["latency_budget_ms"] for name in ("HOT", "WARM", "COLD")
    ] == [250, 1000, 3000]
    assert stages["budgets_are_cumulative"] is True
    assert stages["no_automatic_stage_skip"] is True


def test_recall_channels_and_fusion_are_deterministic_non_authority_signals() -> None:
    spec = load_yaml(SPEC_YAML)
    channels = spec["recall_channels"]
    fusion = spec["fusion"]

    assert set(channels) == {
        "EXACT_REF",
        "METADATA",
        "KEYWORD",
        "VECTOR",
        "GRAPH",
        "ARCHIVE",
    }
    assert all(item["authority"].startswith("NON_AUTHORITY") for item in channels.values())
    assert channels["EXACT_REF"]["required_recall_percent"] == 100
    assert channels["VECTOR"]["optional"] is True
    assert channels["GRAPH"]["optional"] is True
    assert fusion["algorithm"] == "WEIGHTED_RECIPROCAL_RANK_FUSION"
    assert fusion["reciprocal_rank_constant"] == 60
    assert fusion["default_weights"] == {
        "EXACT_REF": 100,
        "METADATA": 4,
        "KEYWORD": 3,
        "VECTOR": 2,
        "GRAPH": 1,
        "ARCHIVE": 1,
    }
    assert fusion["score_rounding_decimal_places"] == 12
    assert fusion["score_may_override_filter"] is False
    assert fusion["score_may_create_oracle_authority"] is False


def test_cursor_is_bound_to_actor_authority_query_and_epochs() -> None:
    spec = load_yaml(SPEC_YAML)
    cursor = spec["cursor_contract"]

    assert cursor["opaque"] is True
    assert cursor["integrity_protected"] is True
    assert {
        "actor_identity_digest",
        "authorized_namespace_digest",
        "request_digest",
        "read_mode",
        "filter_profile_version",
        "fusion_profile_version",
        "primary_snapshot_ref",
        "index_snapshot_refs",
        "stage",
        "channel_cursors",
        "last_sort_key",
        "acl_epoch",
        "forget_barrier_epoch",
    } == set(cursor["bound_fields"])
    assert cursor["actor_or_query_change_result"] == "CURSOR_INVALID"
    assert cursor["expired_or_tampered_result"] == "CURSOR_INVALID"
    assert cursor["raw_content_in_cursor"] is False


def test_forget_barrier_spans_every_release_surface_and_restore_path() -> None:
    spec = load_yaml(SPEC_YAML)
    forget = spec["invalidation_and_forget"]

    assert forget["revoke_expire_forget_advance_barrier"] is True
    assert forget["every_query_checks_current_barrier"] is True
    assert forget["content_release_after_forget_ack"] is False
    assert forget["backup_restore_requires_tombstone_replay_before_reads"] is True
    assert forget["index_rebuild_requires_tombstone_and_state_stream_first"] is True
    assert set(forget["verification_surfaces"]) == {
        "primary_store",
        "keyword_index",
        "vector_index",
        "graph_index",
        "cache",
        "archive",
        "replay_bundle",
    }


def test_degraded_modes_never_bypass_primary_authority() -> None:
    spec = load_yaml(SPEC_YAML)
    modes = spec["degraded_modes"]

    assert modes["PRIMARY_STORE_UNAVAILABLE"]["content_release"] == "BLOCKED"
    assert modes["INDEX_UNAVAILABLE"]["maximum_stage"] == "HOT"
    assert modes["VECTOR_UNAVAILABLE"]["result_status"] == "DEGRADED"
    assert modes["GRAPH_UNAVAILABLE"]["result_status"] == "DEGRADED"
    assert modes["CACHE_UNAVAILABLE"]["action"] == "bypass_cache"
    assert modes["ACL_OR_FORGET_EPOCH_UNKNOWN"]["content_release"] == "BLOCKED"
    assert modes["retry_policy"]["maximum_per_channel"] == 1
    assert modes["retry_policy"]["no_retry_after_authority_failure"] is True
    assert modes["retry_policy"]["no_retry_storm"] is True


def test_benchmark_thresholds_make_safety_and_replay_non_negotiable() -> None:
    spec = load_yaml(SPEC_YAML)
    thresholds = spec["benchmark"]["thresholds"]

    assert thresholds == {
        "critical_unauthorized_release_count": 0,
        "forgotten_content_release_count": 0,
        "exact_ref_recall_percent": 100,
        "required_authority_memory_recall_percent": 100,
        "noncritical_labeled_recall_percent_minimum": 95,
        "noncritical_labeled_precision_percent_minimum": 90,
        "replay_equivalence_percent": 100,
        "deterministic_order_percent": 100,
        "p95_default_latency_ms_maximum": 3000,
        "p95_hot_latency_ms_maximum": 250,
    }
    assert spec["benchmark"]["ground_truth_hidden_from_actor"] is True


def test_migration_and_implementation_gates_preserve_identity_and_scope() -> None:
    spec = load_yaml(SPEC_YAML)
    migration = spec["migration_and_rollback"]
    gate = spec["implementation_gate"]

    assert migration["preserve_memory_revision_and_event_identity"] is True
    assert migration["preserve_canonical_hash"] is True
    assert migration["tombstone_and_acl_before_content"] is True
    assert migration["no_read_cutover_before_replay_and_diff_green"] is True
    assert migration["rollback_cannot_resurrect_forgotten_content"] is True
    assert migration["destructive_migration_forbidden"] is True
    assert gate["implementation_allowed_after_spec_merge"] is True
    assert gate["implementation_work_item_separate"] is True
    assert gate["selected_vendor_is_not_domain_authority"] is True
    assert gate["m1c_memory_formation_out_of_scope"] is True
    assert gate["shared_memory_coordination_out_of_scope"] is True
    assert gate["autonomous_promotion_out_of_scope"] is True


def test_threat_model_and_test_design_cover_store_specific_failures() -> None:
    threat = THREAT_MD.read_text(encoding="utf-8")
    design = TEST_DESIGN_MD.read_text(encoding="utf-8")

    assert all(f"M1B-T{index:02d}" in threat for index in range(1, 33))
    for phrase in (
        "Cross-project vector exfiltration",
        "Forgotten content through stale cache",
        "Ranking poison",
        "Cursor replay after ACL removal",
        "Backup resurrection",
        "Partial provider outage",
    ):
        assert phrase in threat
    for phrase in (
        "Primary Store integration",
        "Isolation and authorization",
        "Progressive retrieval",
        "Fusion and ranking",
        "Revoke, expire and Forget",
        "Migration and rollback",
        "Retrieval benchmark",
    ):
        assert phrase in design


def test_workflow_is_least_privilege_and_runs_focused_validation() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "pull_request_target" not in workflow
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e" in workflow
    assert "tests/unit/test_m1b_store_progressive_retrieval_spec.py" in workflow
    assert "uv run ruff check" in workflow
    assert "uv run pytest" in workflow
