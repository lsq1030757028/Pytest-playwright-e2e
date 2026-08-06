# Repository Security Baseline Test Design

> Test Design: `TD-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Parent SPEC: `SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Threat Model: `TM-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Goal: Issue #52  
> Assurance: `DEV3 / UX0`  
> Status: `CANDIDATE`

## 1. Purpose

Define the cheapest sufficient but adversarial evidence proving that the repository security baseline detects meaningful defects, does not leak Secrets through its own evidence, remains safe for fork pull requests, and can be rolled back without silently weakening existing gates.

This document designs implementation evidence. It does not add or execute the security Workflows in the SPEC phase.

## 2. Truth boundaries and Oracles

| Obligation | Oracle |
|---|---|
| Full-history credential detection | a non-functional synthetic canary committed in an earlier commit of an ephemeral repository is detected even when absent from the final tree |
| Secret-output safety | the full canary value never appears in captured stdout, stderr, annotations, artifacts, or PR comments |
| Real repository history | the selected scanner reports zero unresolved findings for the final implementation revision and reachable history, or every finding has recorded remediation and independent re-scan |
| Fork safety | untrusted pull-request code cannot access repository Secrets or a write-capable token |
| Action provenance | every newly introduced third-party Action is pinned to an immutable commit SHA |
| CodeQL execution | selected active languages are genuinely analyzed and the final-head check/SARIF upload succeeds in an allowed context |
| Dependabot coverage | active Python dependency management and GitHub Actions are represented with bounded cadence and PR limits |
| Vulnerability disclosure | `SECURITY.md` contains all required private-reporting and coordinated-disclosure fields |
| Existing quality | full repository CI remains green; security checks do not replace existing evidence |
| Merge decision | unresolved critical security findings, review threads, blockers, and critical false greens are zero |

## 3. Evidence strategy

```text
Static policy validation
→ generated ephemeral boundary tests
→ real final-head GitHub Actions
→ independent review of fork/token and evidence boundaries
→ main verification
→ optional ruleset enforcement after stability evidence
```

Skipped layers:

- Browser/Playwright evidence: skipped because UX0 and no user Journey changes.
- Production Secret rotation: excluded; no real Secret acquisition or mutation is authorized.
- Live malicious fork execution: not required by default; event/permission configuration plus a controlled public fork test may be added only if static evidence is insufficient.
- Codex Security: explicitly excluded from Goal #52.

## 4. SPEC-phase validation

The SPEC PR must prove:

1. Markdown, YAML, threat model, and test design reference the same IDs, Goal, profile, scope, exclusions, invariants, and assets.
2. No implementation Workflow, branch rule, repository setting, or release gate is modified in the SPEC phase.
3. Existing `.github/dependabot.yml` is inventoried truthfully rather than reported as missing.
4. External GitHub settings are marked owner-controlled and connector-unverified where applicable.
5. Full repository CI passes on the SPEC final head.

Recommended validation implementation after SPEC review: a focused unit test parses the YAML and asserts the critical invariants and cross-file references. Until that test exists, PR review plus full CI is supporting evidence only and the SPEC remains `CANDIDATE`.

## 5. Implementation test matrix

### SEC-01 — Security Workflow structure

**Risk:** malformed or over-privileged Workflow.

Evidence:

- parse every new/changed Workflow YAML;
- assert explicit top-level/job permissions;
- reject broad `write-all` and unnecessary `contents: write`;
- reject `pull_request_target` combined with checkout/execution of untrusted PR content;
- reject new third-party Actions not pinned to a 40-character commit SHA;
- reject shell installation patterns equivalent to unaudited `curl | sh`;
- assert concurrency/cancellation behavior does not cancel authoritative main evidence incorrectly.

Failure must identify Workflow, job, step, and violated rule.

### SEC-02 — Scanner selection proof

**Risk:** selecting a scanner by popularity rather than falsifiable behavior.

Compare Gitleaks and TruffleHog using the same ephemeral repositories and record:

- full-history detection result;
- redaction behavior;
- exit-code determinism;
- runtime and network requirements;
- false-positive controls;
- license and maintained provenance;
- immutable installation/pinning path;
- output fields required for diagnosis.

Selection requires a written decision in the implementation PR. The losing candidate is recorded with rejection reasons; it is not silently omitted.

### SEC-03 — Historical synthetic canary

**Risk:** shallow checkout or working-tree-only scan.

Create an ephemeral Git repository during the test:

1. initialize a repository;
2. commit a generated, non-functional canary matching a supported detector pattern;
3. commit deletion of the canary;
4. run the selected scanner against complete history;
5. require a finding tied to the earlier commit;
6. require non-zero exit status;
7. inspect captured output and fail if the complete canary value appears.

The canary must not be usable against any provider and must not be committed to the real repository history.

### SEC-04 — Redaction mutation proof

**Risk:** scanner detects the secret but leaks it through evidence.

Mutation: enable verbose/raw output or remove the output sanitizer in an isolated test fixture.

Expected result: the evidence-safety assertion kills the mutation because the complete canary appears in captured output.

Acceptance: baseline output contains only allowed redacted fields and a stable redacted fingerprint.

### SEC-05 — False-positive and adjacent-positive proof

**Risk:** over-broad allowlist hides real leaks.

Fixtures:

- one benign documentation/example string that would otherwise trigger the selected detector;
- one adjacent synthetic positive in the same directory or file family.

Expected:

- the narrow suppression permits only the benign fixture;
- the adjacent positive still fails;
- removing or broadening the suppression changes the expected verdict and is caught by tests.

### SEC-06 — Real repository full-history scan

**Risk:** implementation works only against fixtures.

Run on the PR final head with full reachable history.

Acceptance:

- zero unresolved findings; or
- each finding has redacted Issue/PR evidence, credential-owner status, remediation, and an independent clean re-scan;
- no secret values in logs/artifacts;
- job and scanner versions/provenance recorded;
- shallow clone is not used.

A finding cannot be resolved only by deleting the latest file. Active credentials require owner-controlled revoke/rotate evidence without disclosing values.

### SEC-07 — CodeQL language and query coverage

**Risk:** green check without analyzing active code.

Evidence:

- inventory active source languages from repository metadata and build configuration;
- configure supported CodeQL languages deliberately;
- execute the Workflow on PR final head;
- verify init, analysis, and SARIF/check completion steps executed;
- verify no language silently skipped;
- record query suite and Action immutable pins.

If GitHub Advanced Security behavior differs between public/private states or fork contexts, record the actual event/context and keep unsupported claims out of status reports.

### SEC-08 — Fork and token isolation

**Risk:** untrusted PR obtains privilege.

Static assertions:

- security Workflows triggered by untrusted contributions use `pull_request`, not privileged execution of fork content;
- repository Secrets are not referenced in jobs that run untrusted code;
- token permissions are read-only unless a trusted-context upload requires a narrowly scoped permission;
- SARIF upload conditions cannot be exploited to run arbitrary privileged code;
- checkout `ref` is not attacker-controlled in a privileged context.

Independent review must map each event to its token and Secret trust level.

Optional controlled fork proof may be added after SPEC approval using only non-sensitive sentinel values; it must never expose a real Secret.

### SEC-09 — Dependabot validation

**Risk:** incomplete or noisy dependency coverage.

Validate:

- YAML syntax and version;
- Python package ecosystem matches the repository's actual dependency manager/files;
- GitHub Actions ecosystem is included;
- schedule is bounded;
- open-pull-request limit is bounded;
- target branch and directory are correct;
- labels/reviewer settings reference valid repository resources when used;
- no dependency PR auto-merge is introduced.

### SEC-10 — `SECURITY.md` contract

**Risk:** public contributors disclose vulnerabilities or credentials publicly because the reporting path is unclear.

Assert the document contains:

- supported versions/project status;
- private reporting path;
- acknowledgment and triage targets framed as targets, not guarantees;
- request for coordinated disclosure;
- prohibition on real customer data, credentials, destructive proof, or uncontrolled scanning;
- public disclosure and credit expectations;
- emergency instruction for an already exposed credential: revoke/rotate through the credential owner and do not paste it into an Issue.

### SEC-11 — Existing CI and release regression

**Risk:** security tooling breaks normal development or is used as a substitute for existing quality gates.

Evidence:

- full existing CI passes on final head;
- security checks run as additional checks;
- no existing assertion, test, or release gate is deleted or weakened;
- Workflow runtime/cost is measured and remains bounded;
- security artifacts do not include source bundles or environment dumps.

### SEC-12 — Stability and retry discipline

**Risk:** flaky control is bypassed.

Minimum evidence before required-check enforcement:

- final-head PR run passes;
- main run passes after merge;
- at least one deliberate failure proof exists for secret detection and policy validation;
- repeated runs are required only when diagnosing nondeterminism, not as blind retries;
- any flake becomes a blocker or Change Event, not an ignored result.

## 6. Review obligations

The reviewer must independently inspect:

- Goal/SPEC/Threat Model/Test Design consistency;
- event type, checkout ref, token permissions, and Secret references;
- action/binary provenance and immutable pins;
- scanner complete-history mode and redaction;
- CodeQL language matrix and actual executed steps;
- suppressions and adjacent-positive regression;
- artifacts and logs for prohibited data;
- Dependabot scope and absence of auto-merge;
- rollback and credential incident boundary;
- final diff contains no policy/permission widening beyond the approved SPEC.

## 7. Acceptance summary

Implementation may become `READY_TO_MERGE` only when:

- SEC-01 through SEC-12 applicable obligations pass;
- selected and skipped evidence is explained;
- real repository scan has zero unresolved findings;
- CodeQL and full CI are green on the final head;
- critical false green is zero;
- unresolved review threads, blockers, and critical findings are zero;
- rollback is credible;
- external ruleset/branch-protection enforcement is either completed by the owner or explicitly recorded as a post-main owner step.

Merge is not closure. Goal #52 reaches `CLOSED` only after main verification, status/ledger update, required external-owner evidence, and branch cleanup.
