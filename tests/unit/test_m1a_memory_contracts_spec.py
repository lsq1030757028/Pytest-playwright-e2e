from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs/specs/m1a-memory-contracts-namespaces.yaml"
APPROVAL_PATH = ROOT / "docs/specs/m1a-memory-contracts-namespaces-approval.yaml"
EXAMPLES_PATH = ROOT / "tests/assets/memory/m1a/canonical-examples.yaml"
ROADMAP_PATH = ROOT / "docs/agent-os-roadmap.yaml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_m1a_spec_identity_scope_and_dev3_boundary() -> None:
    spec = load_yaml(SPEC_PATH)

    assert spec["spec_id"] == "SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES"
    assert spec["version"] == "1.0.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 28
    assert spec["milestone"] == "M1"
    assert spec["mandate_ref"] == "MANDATE-AUTONOMY-M1-M3@1.0.0"
    assert spec["assurance"]["spec_phase"] == "DEV3"
    assert spec["assurance"]["implementation_phase"] == "DEV3"
    assert "concrete_database_or_storage_vendor" in spec["scope"]["excludes"]
    assert "production_retrieval_runtime" in spec["scope"]["excludes"]
    assert "self_evolution_or_autonomous_promotion" in spec["scope"]["excludes"]


def test_memory_dimensions_and_session_boundary_are_separated() -> None:
    spec = load_yaml(SPEC_PATH)
    invariants = set(spec["core_separation_invariants"])
    session = spec["session_boundary"]

    assert {
        "memory_kind_is_not_lifecycle_state",
        "namespace_scope_is_not_relevance",
        "evidence_status_is_not_oracle_authority",
        "content_revision_is_not_effective_state_event",
        "session_history_is_not_governed_memory",
        "promoted_memory_is_not_fact_oracle_policy_or_permission",
        "storage_backend_is_not_contract_semantics",
    } == invariants
    assert session["session_is_memory_record"] is False
    assert session["raw_session_auto_promotion_forbidden"] is True
    assert {
        "explicit_formation_event",
        "declared_memory_kind",
        "namespace",
        "provenance",
        "candidate_state",
        "content_hash",
        "policy_and_permission_check",
    } == set(session["ingestion_to_memory_requires"])


def test_all_five_memory_kinds_have_type_specific_safety_rules() -> None:
    kinds = load_yaml(SPEC_PATH)["memory_kinds"]

    assert list(kinds) == ["WORKING", "SEMANTIC", "EPISODIC", "PROCEDURAL", "SKILL"]
    assert kinds["WORKING"]["ttl_required"] is True
    assert kinds["WORKING"]["promotion_allowed"] is False
    assert kinds["SEMANTIC"]["silent_decay_forbidden"] is True
    assert kinds["SEMANTIC"]["supersession_or_revalidation_required"] is True
    assert kinds["EPISODIC"]["derived_summary_must_be_new_memory"] is True
    assert kinds["PROCEDURAL"]["executable_code_embedded"] is False
    assert kinds["SKILL"]["unrestricted_executable_code_embedded"] is False
    assert "capability_ref" in kinds["SKILL"]["content_requirements"]


def test_identity_revision_and_hash_are_storage_independent() -> None:
    identity = load_yaml(SPEC_PATH)["identity_contract"]
    required = set(load_yaml(SPEC_PATH)["memory_revision_required_fields"])

    assert identity["logical_memory_id"]["storage_location_independent"] is True
    assert identity["revision_sequence"]["monotonic_per_memory"] is True
    assert identity["content_hash"]["algorithm"] == "sha256"
    assert identity["content_hash"]["canonical_format"] == (
        "RFC8785_style_canonical_json"
    )
    assert identity["content_hash"]["hash_change_requires_new_revision"] is True
    assert {
        "physical_storage_location",
        "database_internal_id",
        "ingestion_latency",
        "cache_metadata",
    } == set(identity["content_hash"]["excludes"])
    assert {
        "memory_id",
        "revision_id",
        "revision_number",
        "schema_version",
        "memory_kind",
        "namespace",
        "content",
        "provenance",
        "created_at",
        "created_by",
        "idempotency_key",
        "content_hash",
        "retention_policy",
    } == required


def test_namespace_and_acl_are_default_deny_before_relevance() -> None:
    spec = load_yaml(SPEC_PATH)
    namespace = spec["namespace_contract"]
    acl = spec["acl_contract"]

    assert namespace["canonical_segments"] == [
        "organization_id",
        "project_id",
        "scope_kind",
        "scope_id",
    ]
    assert set(namespace["scope_kinds"]) == {
        "ORGANIZATION",
        "PROJECT",
        "CAMPAIGN",
        "AGENT",
        "SHARED",
    }
    assert "relevance_cannot_expand_namespace" in namespace["rules"]
    assert "embedding_similarity_cannot_expand_namespace" in namespace["rules"]
    assert "wildcard_cross_project_query_forbidden_by_default" in namespace["rules"]
    assert acl["default_effect"] == "DENY"
    assert acl["deny_overrides_allow"] is True
    assert acl["relevance_cannot_grant_permission"] is True
    assert acl["memory_content_cannot_modify_acl"] is True
    assert acl["self_grant_forbidden"] is True
    assert acl["evaluation_order"][-1] == "default_deny"


def test_long_lived_memory_requires_resolvable_provenance() -> None:
    provenance = load_yaml(SPEC_PATH)["provenance_contract"]

    assert provenance["required_for_long_lived_memory"] is True
    assert {
        "source_refs",
        "evidence_refs",
        "source_content_hashes",
        "created_by_principal",
        "creator_type",
        "capability_or_formation_rule_ref",
        "requirement_revision_refs",
        "code_revision_refs",
        "environment_revision_refs",
        "model_or_provider_profile_refs",
        "parent_memory_refs",
        "transformation_kind",
    } == set(provenance["required_fields"])
    assert provenance["source_refs_must_resolve"] is True
    assert provenance["source_hashes_must_verify"] is True
    assert provenance["missing_or_unverifiable_provenance_action"] == "QUARANTINE"
    assert provenance["derived_memory_never_overwrites_source"] is True


def test_lifecycle_graph_rejects_direct_candidate_promotion_and_forgotten_revival() -> None:
    lifecycle = load_yaml(SPEC_PATH)["lifecycle_contract"]
    states = set(lifecycle["states"])
    transitions = lifecycle["transitions"]

    assert states == {
        "CANDIDATE",
        "VERIFIED",
        "PROMOTED",
        "CONFLICTING",
        "QUARANTINED",
        "SUPERSEDED",
        "REVOKED",
        "EXPIRED",
        "FORGOTTEN",
    }
    assert lifecycle["initial_state"] == "CANDIDATE"
    assert "PROMOTED" not in transitions["CANDIDATE"]
    assert transitions["FORGOTTEN"] == []
    assert lifecycle["content_mutation_via_state_event_forbidden"] is True
    assert lifecycle["illegal_transition_action"] == "REJECT"
    for source, targets in transitions.items():
        assert source in states
        assert set(targets) <= states


def test_promotion_is_retrieval_admission_not_protected_authority() -> None:
    promotion = load_yaml(SPEC_PATH)["promotion_contract"]

    assert promotion["meaning"] == "admitted_to_declared_retrieval_scope"
    assert set(promotion["never_means"]) == {
        "confirmed_fact",
        "oracle",
        "policy",
        "permission",
        "production_invariant",
        "unrestricted_executable_capability",
    }
    assert promotion["candidate_direct_promotion_forbidden"] is True
    assert promotion["verified_state_required"] is True
    assert promotion["oracle_policy_permission_change_forbidden"] is True
    assert promotion["scope_expansion_requires_new_promotion_event"] is True
    assert "rollback_or_disable_ref" in promotion["required_inputs"]


def test_retention_revoke_and_forget_remove_effective_content_safely() -> None:
    retention = load_yaml(SPEC_PATH)["retention_contract"]

    assert retention["WORKING"]["ttl_required"] is True
    assert retention["WORKING"]["effective_after_campaign_close"] is False
    assert retention["SEMANTIC"]["silent_time_decay_forbidden"] is True
    assert retention["expiration"]["evaluated_before_retrieval"] is True
    assert retention["revoke"]["immediate_effective_read_removal"] is True
    assert retention["forget"]["protected_content_unavailable"] is True
    assert retention["forget"]["caches_and_indexes_invalidated"] is True
    assert retention["forget"]["non_sensitive_tombstone_preserved"] is True
    assert {
        "original_content",
        "secret_or_personal_data",
        "raw_source_payload",
    } == set(retention["forget"]["tombstone_forbidden_fields"])


def test_compare_and_swap_conflict_and_idempotency_are_explicit() -> None:
    concurrency = load_yaml(SPEC_PATH)["revision_and_concurrency_contract"]

    assert concurrency["append_only_revisions"] is True
    assert concurrency["in_place_content_update_forbidden"] is True
    assert concurrency["compare_and_swap_required"] is True
    assert concurrency["stale_expected_head_action"] == "CONFLICT"
    assert concurrency["conflict_artifact_required"] is True
    assert concurrency["last_write_wins_forbidden"] is True
    assert concurrency["idempotency"] == {
        "same_key_same_payload": "RETURN_ORIGINAL_RESULT",
        "same_key_different_payload": "REJECT",
    }
    assert concurrency["conflict_resolution"]["creates_new_revision"] is True
    assert concurrency["conflict_resolution"]["parent_revision_refs_minimum"] == 2


def test_procedural_and_skill_memory_cannot_be_unrestricted_code_channels() -> None:
    compatibility = load_yaml(SPEC_PATH)["compatibility_contract"]

    assert compatibility["required_for"] == ["PROCEDURAL", "SKILL"]
    assert "required_permissions" in compatibility["fields"]
    assert compatibility["incompatible_memory_effective_action"] == "FILTER_AND_EVENT"
    assert compatibility["unrestricted_shell_or_code_payload_forbidden"] is True
    assert compatibility[
        "executable_reference_must_resolve_to_versioned_capability"
    ] is True


def test_m1b_ports_are_vendor_neutral_and_do_not_choose_retrieval_algorithm() -> None:
    ports = load_yaml(SPEC_PATH)["m1b_port_contract"]
    serialized = yaml.safe_dump(ports).lower()

    assert ports["storage_vendor_neutral"] is True
    assert set(ports["ports"]) == {
        "MemoryRevisionPort",
        "MemoryStatePort",
        "MemoryAclPort",
        "MemoryQueryPort",
        "MemoryAuditPort",
        "MemoryMaintenancePort",
    }
    query = ports["ports"]["MemoryQueryPort"]
    assert query["ranking_algorithm_defined_by_m1a"] is False
    assert query["embedding_required_by_m1a"] is False
    assert "no_vendor_specific_types_in_domain_contract" in (
        ports["portability_requirements"]
    )
    for forbidden in ("postgres", "redis", "sqlite", "mongodb", "pinecone", "milvus"):
        assert forbidden not in serialized


def test_m1_0_safety_scenarios_are_mapped_to_contract_clauses() -> None:
    mapping = load_yaml(SPEC_PATH)["m1_0_coverage_mapping"]

    assert set(mapping) == {f"MEM-S{index:03d}" for index in range(3, 17)}
    assert all(clauses for clauses in mapping.values())
    assert load_yaml(SPEC_PATH)["acceptance_gates"][
        "m1_0_safety_scenarios_mapped"
    ] == 14


def test_canonical_examples_cover_kinds_negative_paths_transitions_and_acl() -> None:
    examples = load_yaml(EXAMPLES_PATH)
    valid = examples["valid_examples"]
    invalid = examples["invalid_examples"]

    assert examples["spec_ref"] == "SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0"
    assert {item["memory"]["memory_kind"] for item in valid} == {
        "WORKING",
        "SEMANTIC",
        "EPISODIC",
        "PROCEDURAL",
        "SKILL",
    }
    assert all(item["expected"] == "ACCEPT" for item in valid)
    assert {
        "PROMOTION_DENIED",
        "PROVENANCE_MISSING",
        "ILLEGAL_TRANSITION",
        "NAMESPACE_DENIED",
        "ACL_DENIED",
        "REVISION_CONFLICT",
        "DUPLICATE_IDEMPOTENCY_KEY",
        "FORGOTTEN_CONTENT_UNAVAILABLE",
        "INVALID_SCHEMA",
    } <= {item["failure_code"] for item in invalid}
    assert ["CANDIDATE", "PROMOTED"] in examples["transition_cases"]["denied"]
    assert ["VERIFIED", "PROMOTED"] in examples["transition_cases"]["allowed"]
    acl_outcomes = {item["id"]: item["expected"] for item in examples["acl_cases"]}
    assert acl_outcomes == {
        "ACL-DEFAULT-DENY": "DENY",
        "ACL-EXPLICIT-ALLOW": "ALLOW",
        "ACL-DENY-OVERRIDES": "DENY",
    }


def test_m1a_spec_is_approved_closed_and_runtime_is_next() -> None:
    status = (ROOT / "docs/implementation-status.md").read_text(encoding="utf-8")
    roadmap = load_yaml(ROADMAP_PATH)
    approval = load_yaml(APPROVAL_PATH)

    assert "M1A Memory Contracts & Namespaces SPEC：MERGED / CLOSED" in status
    assert "M1A Runtime Contracts：MERGED / CLOSED" in status
    assert "M1B Store & Progressive Retrieval：NEXT / SPEC" in status
    assert "M1 Memory Gate：0 / 1" in status
    assert approval["status"] == "APPROVED"
    assert approval["spec_ref"] == "SPEC-M1A-MEMORY-CONTRACTS-NAMESPACES@1.0.0"
    assert approval["runtime_authorization"]["m1a_runtime_contracts_may_begin"] is True
    assert approval["runtime_authorization"]["m1b_store_and_retrieval_remains_blocked"] is True
    assert roadmap["next_execution_sequence"][0] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    m1 = next(item for item in roadmap["milestones"] if item["id"] == "M1")
    assert m1["active_module"] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    assert m1["module_status"]["M1A"] == "SPEC_MERGED_CLOSED"
    assert m1["module_status"]["M1A_RUNTIME_CONTRACTS"] == (
        "MERGED_CLOSED"
    )
    assert m1["module_status"]["M1B"] == "SPEC_NEXT"
    assert m1["module_status"]["M1.0"] == "MERGED"
