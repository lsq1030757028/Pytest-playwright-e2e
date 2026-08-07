# M1C Memory Formation Test Design

## Purpose

Prove that Memory Formation creates governed Candidate Memory without silently converting execution data into authority.

## Test Families

### FORM-001 Explicit formation boundary

Input: session events, tool results, execution summaries.

Expected:
- no implicit Memory write exists;
- only an explicit Formation Event can create a Candidate Revision;
- source references are required.

### FORM-002 Candidate-only lifecycle

Expected:
- new long-lived Memory state is always `CANDIDATE`;
- formation cannot emit `VERIFIED` or `PROMOTED`;
- confidence score cannot bypass lifecycle rules.

### FORM-003 Provenance integrity

Reject:
- missing source reference;
- fabricated evidence ID;
- unresolved content hash;
- invalid creator/provider version.

### FORM-004 Poisoning resistance

Reject or quarantine:
- instructions inside source data;
- prompt injection text treated as commands;
- hidden benchmark answers;
- evaluator-only fixtures.

### FORM-005 Namespace isolation

Reject:
- source mixing across unauthorized namespaces;
- candidate creation from inaccessible source Memory.

### FORM-006 Deterministic duplication

Formation must choose exactly one:
- append same logical Memory with CAS;
- create new logical Candidate;
- mark conflict/quarantine;
- suppress exact duplicate with evidence.

Silent merge is forbidden.

### FORM-007 Replay

Same source events, formation rule version and configuration must produce identical formation evidence digest.

## Mutation Targets

Critical mutations that must fail:

1. remove Candidate-only check;
2. remove provenance validation;
3. allow source instruction execution;
4. bypass namespace validation;
5. skip idempotency key handling;
6. accept fabricated evidence references;
7. allow candidate flooding beyond budget.

## Completion Gate

- deterministic fixture replay = 100%;
- critical poisoning mutations killed = 100%;
- unauthorized formation = 0;
- fabricated provenance accepted = 0.
