# Security Policy

## Supported versions

This project is under active development. Security fixes are applied to the default branch and, when relevant, the latest published release. Older commits and unmaintained experimental branches are not supported independently.

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** option for this repository when it is available. This creates a private vulnerability report for the maintainers.

When that option is not visible, contact the repository owner through a private contact method listed on the owner's GitHub profile. Do not open a public Issue containing exploit details, credentials, tokens, customer data, or other sensitive material.

Include only the minimum information needed to reproduce and assess the problem:

- affected revision, component, and environment;
- impact and realistic attack preconditions;
- bounded reproduction steps using synthetic data;
- suggested remediation, when known.

Do not include real customer data, live credentials, destructive proof, uncontrolled scanning results, or evidence collected without authorization.

## Response targets

The maintainers target acknowledgment within 3 business days and initial triage within 7 business days. These are targets, not guaranteed resolution deadlines. Remediation timing depends on severity, reproducibility, affected users, and safe release requirements.

## Coordinated disclosure

Please allow time to validate, remediate, test, and release a fix before publishing technical details. Public disclosure and credit will be coordinated with the reporter when practical. This repository does not currently promise a bug bounty or monetary reward.

## Exposed credentials

An already exposed credential must be revoked or rotated by its owner first. Removing it from the latest file or commit does not invalidate copies in Git history, forks, clones, caches, or logs. Never paste the credential into an Issue, pull request, build log, artifact, or chat message.

## Safe research boundary

Security research must remain non-destructive, use synthetic data, avoid production or personal accounts, and stop when access beyond the authorized scope would be required. Denial-of-service tests, social engineering, persistence, data exfiltration, and automated scanning of unrelated systems are out of scope.
