# AI SDLC Manifest

Status: active
Operating level: L2 — Agent Workflow
Scope: development of this repository only

This lightweight operating layer governs how humans and AI collaborate on the
Adaptive Agentic Engineering Platform repository. It does not define the product's
runtime agent control plane. Product behavior remains governed by the normative
documents under `docs/`.

## Foundation

| Artifact | Purpose |
|---|---|
| `../AGENTS.md` | Repository operating contract |
| `AGENT-RUNTIME.md` | Runtime capability and safety boundary |
| `KNOWLEDGE-REGISTRY.md` | Canonical project-knowledge routing |
| `WORKFLOW-STATE.md` | Material delivery state and open gates |
| `DECISIONS.md` | Material development-process decisions |

Handoff packets and additional capability files are created only when a genuine
transfer or capability need exists. Their absence grants no additional authority.
