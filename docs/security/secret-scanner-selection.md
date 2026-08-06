# Secret Scanner Selection

> Decision: `SECURITY-SCANNER-SELECTION@1.0.0`  
> Parent SPEC: `SPEC-REPOSITORY-SECURITY-BASELINE@0.1.0`  
> Goal: Issue #52  
> Selected scanner: Gitleaks `8.30.1`

## Decision

Use the Gitleaks CLI as the repository's blocking full-history secret scanner. Install the Linux x64 release archive only after verifying this pinned SHA-256 digest:

```text
551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
```

The workflow uses `gitleaks git --log-opts="--all" --redact=100`, a dedicated finding exit code, no raw report artifact, and a generated earlier-commit canary proof.

## Candidate comparison

| Obligation | Gitleaks 8.30.1 | TruffleHog 3.96.0 |
|---|---|---|
| Complete Git history | Supported through the Git scanner and explicit Git log options | Supported through the Git source |
| Deterministic fail-closed exit | Explicit configurable finding exit code | Requires additional output and result-mode policy |
| Complete value redaction | Native `--redact=100`; independently tested by the workflow | Official quick-start output includes a raw result; safe redaction was not established |
| Offline default for this gate | Pattern detection does not require credential validation | Product design includes live credential validation and network-facing analysis |
| False-positive control | Config, ignore path, fingerprint, and baseline mechanisms | Detector/result filtering is available but would need a separate evidence wrapper |
| Pinned release evidence | Linux x64 archive and digest are pinned | Linux amd64 archive digest reviewed: `7105f1cd6577f058a9e39d0578f1a99c8a1e481e4d3512cd8a09acfe22a0fdc0` |
| CI integration size | Release archive is approximately 8 MB | Release archive is approximately 34 MB |

## Why TruffleHog is not executed as the blocking candidate

The same evidence obligations were applied to both candidates. TruffleHog failed the pre-execution evidence-safety boundary because its official quick-start output demonstrates a raw credential result and its core workflow includes live credential validation. Executing a candidate before proving complete output redaction could itself violate the Goal's zero-secret-in-evidence invariant.

This is a fail-fast rejection, not a claim that TruffleHog is generally unsafe. It may be reconsidered in a separate Change Event only after a pinned, offline, fully redacted wrapper proves the same historical-canary and adjacent-positive obligations without contacting credential providers.

## Evidence and limitations

The selected workflow proves that:

- a generated non-functional canary deleted from the final tree is found in an earlier commit;
- the complete canary does not appear in stdout, stderr, or the temporary JSON report;
- the real repository is scanned with a non-shallow checkout and all reachable refs;
- findings fail the check without uploading raw reports.

A green pattern scan does not prove that the repository contains no semantic vulnerability or every possible credential format. CodeQL, GitHub secret protection, review, credential rotation, and incident response remain separate controls.
