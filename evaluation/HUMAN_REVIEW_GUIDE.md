# V0.1 Independent Human Review Guide

## Purpose

This review validates the provisional development-fixture labels independently
of the implementation that is measured against them. It is a release gate, not a
request to make the labels agree with current predictions.

Two engineers review independently before adjudication. A separate holdout
custodian owns repository selection, licensing, label isolation, and release-only
evaluation under `HOLDOUT_POLICY.md`.

## Review packet

The current fixtures are compact seed corpora. Before freezing the release
review packet, the fixture owner must expand them toward the target sizes in the
evaluation protocol, version the resulting provisional labels, and regenerate
their fingerprints. Independent reviewers should review that frozen candidate
packet; reviewing the small seeds and then replacing them would waste the review.

Give each reviewer only:

- this guide;
- `counting-rules/v1.md`;
- each fixture's `manifest.json`, repository snapshot, and `golden.json`;
- the normative labelling sections of `../docs/EVALUATION_PROTOCOL.md`.

Do not give either reviewer the other reviewer's decisions. Prefer hiding current
platform predictions during the independent pass so implementation behavior does
not become the label authority.

## Fixtures

Review all labels in:

- `fixtures/fx-small/golden.json`;
- `fixtures/fx-fastapi/golden.json`;
- `fixtures/fx-messy/golden.json`;
- `fixtures/fx-polyglot/golden.json`.

## Checklist

For every fixture, verify:

1. **Language profile:** first-party language assignments, primary language,
   repository type, generated/vendor exclusions, and extractor status.
2. **Symbols:** completeness and correctness of modules, classes, functions,
   methods, nested functions, module constants, and route records. Confirm names,
   qualified names, types, signatures, decorators, and exact source spans.
3. **Imports and relationships:** imported names, aliases, relative levels,
   type-checking status, inheritance, and re-exports. Do not accept guessed edges.
4. **Routes:** HTTP method, normalized path, handler, module, and source span.
5. **Unresolved evidence:** original target text, resolution status, reason, and
   source span remain honest and complete.
6. **Questions:** query class, answerability, required slots, expected resources,
   essential claims, optional claims, citations, and answer/abstention behavior.
7. **Safety:** ambiguous evidence remains ambiguous, unsupported questions
   abstain, and source qualifiers are not strengthened.

Use the counting rules literally. In particular, do not count lambdas,
parameters, local variables, imported names, or re-exports as new symbols.

## Independent decision record

For each reviewed label, record:

```text
fixture:
label path or stable identity:
decision: ACCEPT | CHANGE | UNCERTAIN
proposed value (when CHANGE):
repository evidence: path and inclusive line range
counting-rule reference:
rationale:
reviewer identity:
reviewed at:
```

Every `CHANGE` or `UNCERTAIN` decision needs repository evidence and a counting-
rule reference. Reviewers do not edit `golden.json` during the independent pass.

## Adjudication

After both passes:

1. Compare decisions by stable label identity.
2. Adjudicate every disagreement with both reviewers or a named adjudicator.
3. Clarify and version the counting rules when ambiguity caused disagreement.
4. Apply accepted label changes, bump the affected label/fixture versions, and
   deliberately update fingerprints and baselines.
5. Rerun every V0.1 gate.
6. Record reviewer identities, numeric first-pass agreement from `0.0` to `1.0`,
   adjudication completion, and the exact reviewed fixture-version map in
   `review.json`.
7. After all technical and holdout gates pass, a named human records the final
   approval status, time, and non-sensitive evidence reference under
   `release_approval`.

Reviewer names, agreement values, and approvals must reflect observed human work;
they must never be synthesized by an agent.

## Holdout review

The holdout custodian verifies provenance and licensing, pins one repository with
75–250 Python files, and ensures it includes a web framework, tests, relative
imports, aliases, and unsupported questions. Holdout labels remain separate from
feature development and run only at release-candidate boundaries or approved
audits. Development receives pass/fail and material regression information, not
detailed labels suitable for tuning.

The reviewed manifest and release result are recorded at
`evaluation/holdout/manifest.json` and `evaluation/holdout/result.json`; their
schemas are `holdout-manifest.schema.json` and `holdout-result.schema.json`.

## Exit condition

Human review passes only when both independent passes and adjudication are
complete, updated labels pass all technical gates, the holdout passes at a release
boundary, and the named human approver records V0.1 release approval.
