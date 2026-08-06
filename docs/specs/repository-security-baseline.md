# Repository Security Baseline SPEC

> SPEC ID: `SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Status: `CANDIDATE`  
> Goal: Issue #52  
> Assurance: `DEV3 / UX0`  
> Authority: repository-owner instruction recorded in Issue #52  
> Phase: `SPEC_DRAFT`

## 1. Goal

Protect the public repository from credential leakage, vulnerable code paths, dependency drift, unsafe GitHub Actions execution, and unaudited vulnerability disclosure while preserving the existing GitHub-first development, evidence, review, release, and rollback gates.

This SPEC defines the security baseline only. Runtime Workflow implementation must use a separate implementation branch and PR after this SPEC is approved and merged to `main`.

## 2. Current baseline

Confirmed repository facts at SPEC creation:

- repository visibility is public;
- GitHub Actions can execute real repository steps;
- `.github/dependabot.yml` already exists;
- no CodeQL Workflow, full-history secret-scan Workflow, or root `SECURITY.md` is present on `main`;
- account-level push protection was shown enabled by the repository owner;
- the connected GitHub integration cannot read or change repository Secret Scanning settings, alerts, rulesets, or branch-protection settings.

The last two items are external-control boundaries. They may be referenced as owner evidence but must not be reported as connector-verified repository settings.

## 3. Scope

### 3.1 Included

1. CodeQL analysis for supported repository languages and GitHub Actions.
2. Full-history secret scanning with a maintained scanner selected during implementation.
3. Validation and strengthening of Dependabot coverage for active package ecosystems and GitHub Actions.
4. A root `SECURITY.md` describing supported versions, private reporting, response expectations, and coordinated disclosure.
5. Least-privilege Workflow permissions and explicit trusted/untrusted pull-request boundaries.
6. Security-specific evidence, failure handling, false-positive handling, rollback, and recovery.
7. A stable security-check set suitable for later branch/ruleset enforcement.

### 3.2 Excluded

- Codex Security integration;
- real Secret acquisition, disclosure, storage, or rotation;
- production or personal-data access;
- automatic public Git-history rewrite;
- Oracle, Experience Oracle, Policy-floor, or Permission widening;
- direct writes to `main`;
- automatic repository settings, ruleset, or branch-protection changes through unavailable permissions;
- M4, M5, or M6 scope.

A confirmed active credential in public history becomes a separate incident. Immediate rotation/revocation is an owner-controlled action; history rewriting requires an explicit recovery plan because it is disruptive and externally visible.

## 4. Authority and assurance

Security and release-gate behavior requires `DEV3`. The repository owner directly authorized this Goal in Chat and the authority is durably recorded in Issue #52. `MANDATE-AUTONOMY-M1-M3@1.0.0` remains active for product work but is not used to silently broaden this cross-cutting Goal.

UX is `UX0`: no product UI, copy, interaction, or user Journey changes. Human UAT is not required for the security tooling itself. Repository-owner confirmation remains required for external GitHub settings that the integration cannot read or change.

## 5. Security architecture

The implementation shall use separate, reviewable controls:

```text
Pull request / push
├── Existing full quality CI
├── CodeQL analysis
├── Full-history secret scan
└── Dependency update automation

Security finding
→ redact secret values
→ classify source and confidence
→ fail or warn according to approved rule
→ preserve diagnosable evidence
→ remediate / rotate / suppress with recorded rationale
→ rerun
```

### 5.1 CodeQL

- Run on pull requests and default-branch pushes.
- Use supported languages detected or explicitly configured for this repository.
- Use least-privilege top-level permissions; grant `security-events: write` only where required and safe.
- Pin third-party and GitHub Actions to immutable commit SHAs in the implementation PR.
- Do not expose repository Secrets to untrusted fork code.
- Upload SARIF only from trusted execution contexts allowed by GitHub.

### 5.2 Secret scanning

- Scan the complete reachable Git history, not only the working tree.
- Use a maintained scanner whose binary/action provenance is pinned and verified.
- Never print full secret values in logs, comments, artifacts, or Chat.
- A confirmed finding fails closed.
- False-positive suppression requires a narrow rule, owner/reviewer rationale, and a regression fixture proving the suppression does not hide adjacent real patterns.
- Generated evidence may include file path, commit identity, detector/rule ID, redacted fingerprint, and remediation state.

The implementation phase shall compare at least Gitleaks and TruffleHog against the test obligations before selecting one. Selection must consider deterministic offline execution, full-history support, redaction, supply-chain pinning, licensing, maintenance, and false-positive control.

### 5.3 Dependency automation

- Preserve the existing Dependabot asset.
- Cover every active package ecosystem used by the repository, including Python and GitHub Actions when applicable.
- Use bounded cadence and bounded open-PR count.
- Dependency PRs remain subject to normal CI, review, security, and release rules.
- No automatic merge is enabled by this SPEC.

### 5.4 Vulnerability disclosure

`SECURITY.md` shall define:

- supported versions/status;
- private reporting channel using GitHub Private Vulnerability Reporting when available;
- request not to publish exploit details before coordination;
- expected acknowledgment and triage targets without promising impossible resolution deadlines;
- prohibition on submitting real customer data, credentials, or destructive proof;
- public disclosure and credit expectations.

## 6. Trust boundaries

1. **Fork pull request → GitHub-hosted runner**: untrusted repository content; no write token or repository Secrets.
2. **Workflow definition → third-party Action/binary**: supply-chain boundary; immutable pin and provenance required.
3. **Scanner output → logs/artifacts/comments**: sensitive metadata boundary; redact values and minimize retention.
4. **Dependabot PR → merge path**: automated contributor boundary; normal gates remain mandatory.
5. **GitHub settings → repository evidence**: external owner-control boundary; unsupported connector reads must be reported as unverified.
6. **Public history → incident response**: immutable-distribution boundary; rotation precedes any history cleanup decision.

## 7. Required invariants

- real_secret_value_in_logs_or_artifacts: `0`;
- untrusted_pr_receives_repository_secret: `0`;
- untrusted_pr_receives_write_token: `0`;
- unpinned_third_party_action_in_new_security_workflows: `0`;
- confirmed_secret_finding_silently_ignored: `0`;
- security_assertion_removed_only_to_make_ci_green: `0`;
- branch_or_ruleset_state_claimed_without_evidence: `0`;
- direct_main_write: `0`;
- unresolved_critical_security_finding_at_merge: `0`;
- critical_false_green: `0`.

## 8. Failure modes

- scanner checks only the checkout depth and misses earlier commits;
- secret values are echoed by verbose tooling;
- CodeQL cannot upload SARIF from an untrusted fork context;
- broad `contents: write` or default token permissions are granted unnecessarily;
- mutable tags allow Action supply-chain drift;
- a documentation example triggers a false positive and receives an over-broad allowlist;
- a Dependabot update bypasses normal review;
- public visibility is mistaken for proof that all security features are enabled;
- a confirmed leaked credential is removed from the branch but remains active and valid;
- security scans become permanently flaky or prohibitively slow and are bypassed rather than redesigned.

## 9. Test and evidence obligations

The independent test design in `docs/testing/repository-security-baseline-test-design.md` is normative for implementation. Minimum obligations:

1. Schema and policy validation for this SPEC and machine-readable counterpart.
2. Static validation of least-privilege permissions and immutable action pins.
3. CodeQL executes real analysis and produces a successful check/SARIF result on the final head.
4. Secret scanner finds a non-functional synthetic canary in an ephemeral test repository and returns a non-zero result without printing the complete canary.
5. The same scanner passes the real full repository history with zero unresolved findings, or records and closes every finding before merge.
6. A benign fixture verifies false-positive handling without a broad suppression.
7. Fork/pull-request event configuration is statically and behaviorally reviewed for token/Secret isolation.
8. Dependabot configuration is validated for syntax, ecosystems, cadence, and limits.
9. `SECURITY.md` contains all required disclosure fields.
10. Full repository CI remains green.
11. Review threads, blockers, unresolved critical findings, and critical false greens are zero.

## 10. Evidence and retention

- GitHub Actions checks are authoritative.
- Security artifacts must contain only redacted, decision-relevant metadata.
- Do not upload raw scanner databases, full repository bundles, environment variables, or credentials.
- Evidence retention follows repository Actions retention; durable decisions and suppressions live in versioned repository assets or Issue/PR records.
- A green scan proves only the configured detectors and analyzed revision; it does not prove absence of every vulnerability.

## 11. Deployment and enforcement

Implementation is staged:

1. Add security Workflows and policy assets on an implementation branch.
2. Prove deterministic green execution on the PR final head.
3. Merge only after DEV3 review and all existing gates pass.
4. Verify the same checks on `main`.
5. Only after stable main evidence may the owner or an authorized integration make the checks required in a branch/ruleset.

The connector currently cannot change rulesets or branch protection. Required-check enforcement therefore remains an explicit owner-controlled external step unless a future authorized integration is available.

## 12. Rollback and recovery

- Revert the implementation PR to disable newly added Workflows and policy assets.
- Preserve failure evidence and suppression history.
- Never resolve an active leaked credential by rollback alone; revoke/rotate first through the credential owner.
- If a scanner is unstable, revert it to non-blocking or remove it only through a recorded Change Event and replacement plan; do not silently bypass it.
- If an Action/binary provenance is compromised, pin to a verified revision or disable the affected Workflow until reviewed.

## 13. Assets

Planned implementation assets:

- `.github/workflows/security-codeql.yml`;
- `.github/workflows/security-secrets.yml`;
- strengthened `.github/dependabot.yml` if required;
- `SECURITY.md`;
- optional narrowly scoped scanner configuration;
- security-specific validation tests and evidence.

SPEC-phase assets:

- `docs/specs/repository-security-baseline.md`;
- `docs/specs/repository-security-baseline.yaml`;
- `docs/security/repository-security-threat-model.md`;
- `docs/testing/repository-security-baseline-test-design.md`.

## 14. Merge eligibility

This SPEC PR may merge only when:

- Goal #52 and owner authority are accurately represented;
- DEV3 / UX0 classification is accepted;
- machine-readable policy, threat model, and test design agree with this document;
- required repository CI is green;
- review threads and blockers are zero;
- no runtime security Workflow or release-gate change is hidden inside the SPEC phase;
- rollback and external-owner boundaries are explicit.

SPEC merge does not close Goal #52. It authorizes a separate implementation phase.
