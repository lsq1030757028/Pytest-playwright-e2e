# Repository Security Baseline Threat Model

> Threat model: `TM-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Parent SPEC: `SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Goal: Issue #52  
> Status: `CANDIDATE`

## 1. Protected assets

- source code, tests, SPECs, evidence, release assets, and Git history;
- GitHub Actions identity, `GITHUB_TOKEN`, repository Secrets, environments, packages, and artifacts;
- contributor and maintainer trust decisions;
- dependency and Action provenance;
- security findings, suppressions, and remediation records;
- repository-owner accounts and externally managed credentials.

## 2. Actors

- trusted repository owner and authorized maintainers;
- scheduled or manual GitHub Relay agents operating under Lease/Fencing;
- ordinary contributors and Dependabot;
- untrusted fork pull-request authors;
- accidental credential committer;
- malicious contributor attempting token, Secret, artifact, or runner abuse;
- compromised third-party Action, package, binary, or upstream release;
- attacker using an already published credential found in Git history.

## 3. Trust boundaries

### TB1 — Public contribution boundary

Untrusted pull-request content crosses into GitHub-hosted execution. The workflow definition and event type determine whether a write-capable token or repository Secrets are exposed.

Required control: prefer `pull_request`; do not execute untrusted code with privileged `pull_request_target`; set explicit least-privilege permissions; do not pass repository Secrets to fork code.

### TB2 — Workflow supply-chain boundary

Workflow steps invoke Actions, installers, packages, and binaries maintained outside the repository.

Required control: immutable commit-SHA pins for new third-party Actions; documented provenance and license; bounded permissions; Dependabot coverage for GitHub Actions; no unaudited `curl | sh` execution.

### TB3 — Scanner-output boundary

Secret and code scanners convert potentially sensitive source/history into logs, annotations, SARIF, artifacts, and PR records.

Required control: redact values; minimize output; never upload raw repository bundles, environment variables, or complete candidate secrets; use narrow retention.

### TB4 — Automated dependency boundary

Dependabot produces externally sourced branch changes that may alter application or Workflow behavior.

Required control: normal CI/security/review gates; bounded update frequency and PR count; no auto-merge introduced by this Goal.

### TB5 — External GitHub settings boundary

Secret Scanning, Push Protection, Private Vulnerability Reporting, rulesets, and branch protection are controlled by GitHub settings and may be unavailable to the connected integration.

Required control: do not claim settings are enabled without direct evidence; record owner evidence separately; implementation must remain useful even when setting APIs are unavailable.

### TB6 — Public-history incident boundary

Once a credential is published, deletion from the latest branch does not revoke copies in clones, forks, caches, logs, or prior commits.

Required control: rotate/revoke first; assess scope; preserve evidence without reproducing values; use a separately approved history-rewrite plan only when justified.

## 4. Threat scenarios and controls

| ID | Scenario | Impact | Primary controls | Required evidence |
|---|---|---|---|---|
| T01 | A real credential is committed to current or historical content | Account/resource compromise | full-history scan, push protection, redaction, incident procedure | synthetic canary killed; real history zero unresolved findings |
| T02 | Secret scanner checks only a shallow checkout | Critical false green | full-depth fetch and explicit history mode | test asserts full-history invocation and detects an earlier synthetic commit |
| T03 | Scanner prints the full candidate secret | Secondary disclosure through logs/artifacts | redaction, non-verbose mode, output sanitization | canary value absent from captured output |
| T04 | Fork PR receives write token or repository Secret | Repository/package compromise | least-privilege permissions, trusted event selection, no privileged untrusted execution | static event/permission test and review |
| T05 | `pull_request_target` checks out and runs untrusted fork code | Privilege escalation | prohibit this combination | policy test fails on forbidden event/checkout pattern |
| T06 | Mutable Action tag is replaced upstream | Supply-chain compromise | immutable SHA pin, Dependabot update review | pin validation |
| T07 | Action or binary installer downloads unauthenticated content | Supply-chain compromise | checksum/signature/provenance verification; no `curl | sh` | workflow static validation |
| T08 | CodeQL analysis omits an active language or never uploads results | False assurance | explicit language inventory, real final-head run, SARIF/check verification | successful CodeQL check for selected matrix |
| T09 | CodeQL SARIF upload fails for an untrusted context | Missing evidence or broken external contribution | event-aware permissions/conditions; trusted push verification | fork-safe configuration review and main run |
| T10 | Benign example causes a broad allowlist | Future real leaks hidden | narrow path/rule/fingerprint suppression plus adjacent-positive regression | benign fixture passes; adjacent canary still fails |
| T11 | Dependabot updates Workflow Actions without security review | Supply-chain regression | GitHub Actions ecosystem coverage and normal gates | configuration validation and PR policy |
| T12 | Security check is flaky and repeatedly bypassed | Permanent control erosion | stability evidence, fail-closed change process, recorded rollback/replacement | repeated green runs or documented replacement gate |
| T13 | Public visibility is mistaken for proof of all settings | Incorrect closure claim | connector/owner evidence distinction | status report explicitly marks unverified external settings |
| T14 | Confirmed credential is removed but not revoked | Credential remains exploitable | incident checklist: revoke/rotate before cleanup | owner attestation without secret value |
| T15 | Security artifacts retain sensitive repository/history data | Expanded data exposure | no raw bundles; redacted metadata only; bounded retention | artifact-content inspection |
| T16 | A scanner or CodeQL finding is suppressed only to make CI green | Critical false green | explicit rationale, review, regression fixture, zero unresolved critical findings | PR review and test evidence |

## 5. Abuse cases

1. A fork PR changes the Workflow to echo contexts or environment variables.
2. A contributor adds an Action referenced by a floating branch/tag.
3. A documentation sample resembles a token and maintainers allowlist the entire directory.
4. An attacker commits a token in an early commit and deletes it before the PR tip.
5. A scanner annotation includes enough unredacted bytes to reconstruct the credential.
6. A dependency update modifies packaging/release behavior while appearing as routine maintenance.
7. An Agent claims Secret Scanning or branch protection is active because the repository is public.
8. A compromised scanner release returns success without performing a scan.

## 6. Security decisions

- Security checks are `DEV3`; they are not merged as an undocumented CI convenience.
- No new Workflow receives broad write permissions by default.
- New third-party Actions must use immutable SHA pins; human-readable version comments are allowed.
- Scanner selection remains open until Gitleaks and TruffleHog are compared against the test design.
- Real Secret values are never copied into Issue, PR, logs, artifacts, tests, or Chat.
- Scanner findings are decision inputs; confirmed active credentials require owner-controlled revocation/rotation.
- Enforcement via ruleset/branch protection occurs only after stable final-head and main evidence and may require the owner.
- Codex Security is outside this Goal.

## 7. Residual risks

- Pattern-based scanners cannot detect every secret or semantic vulnerability.
- CodeQL coverage is limited to supported languages, query suites, build visibility, and analyzed revision.
- A public repository can be cloned before remediation.
- External GitHub security settings may remain unverifiable to the connected integration.
- GitHub-hosted runner and third-party ecosystem compromise cannot be reduced to zero.
- Maintainers can still deliberately bypass controls through privileged settings; auditability and required checks reduce but do not eliminate this risk.

## 8. Review checklist

- [ ] Scope and authority match Issue #52.
- [ ] Fork PRs cannot receive write tokens or repository Secrets.
- [ ] No privileged event runs untrusted checkout/code.
- [ ] New Actions and scanner provenance are immutable and reviewable.
- [ ] Full history, redaction, false-positive, and adjacent-positive obligations are testable.
- [ ] Dependabot and vulnerability disclosure boundaries are covered.
- [ ] External GitHub setting claims are evidence-qualified.
- [ ] Rollback does not replace credential revocation.
- [ ] Critical false green remains zero.
