# Decisions

## 2026-09-08 — Close V0.1 technically before V0.2

- Decision: complete automated V0.1 closure before beginning V0.2.
- Human review and holdout work remain explicit release gates and may proceed
  separately; they will not be fabricated or weakened for a single maintainer.
- The technical result is named `V0.1 Technical Candidate` until fixture scale
  and the human gates pass.
- Model-backed M4 profiles remain disabled until their provider-specific and
  human holdout gates pass.

## 2026-09-08 — Use a lightweight L2 development workflow

- Decision: adopt only the minimal repository-development controls needed for
  shared state, knowledge routing, validation, and safe handoffs.
- The `.ai-sdlc/` layer governs development of this repository. The product's
  runtime orchestration remains governed by its normative specification and code.
- Additional process artifacts are created only when a concrete need appears.
