# Issue #4 — Status

Current stage: CR1 Implement — #8/#9 implemented in 2d1f78d; review follow-up fixes under validation. Confirmed review base 3a02f00. Formal Verify/manual GUI acceptance not yet entered.

## Delivery

Implementation commit: 87da096. Tasks #5–#7 implemented and A1–A8 software-verified. Formal evidence: verification.md and verify-results.json. Published task links/dependencies: plan.md.

Checks: 40 tests passed; Pyright/Ruff passed; two-axis review 0 findings each. Independent short X5 CLI run produced 40 finite samples; invalid-duration failure preserved the output hash. Full details and exact commands are in verification.md.

## Cleanup

User requested intermediate-file cleanup and structured commits. Removed redundant local copies of published tickets, publication receipt, implementation/review logs and disposable /tmp probe/ticket files. Essential evidence was consolidated into research.md and verification.md. Retained requirements, research, spec, interfaces, plan, verification and this handoff; no decision history was silently discarded.

Repository agent instructions, skill configuration, glossary and accepted ADRs are durable project documents. User-owned X5 assets are retained unchanged, outside the code/documentation commits.

## Remaining boundaries

Physical collision/trajectory acceptance is user-owned. Full 20 s sweep and interactive desktop visibility were not verified. Existing license hook references a missing template; other applicable hooks passed. No pushes or GitHub Issue changes authorized by cleanup.

## CR1 next step

Resolve direction semantics, channel scope and visualization purpose with the user. Record confirmed requirements before requesting Research transition. No code edits, tests, commits or tracker writes performed for CR1.

CR1 round 1: full-trajectory sign inversion and observation-only real-time viewer confirmed. Direction channel scope remains ambiguous in Q2 and requires clarification.

CR1 Q2 resolved: all 12 position and 4 velocity channels have independent direction signs. Next requirement questions cover window-close and unavailable-display behavior. Remain in Explore.

CR1 Q4/Q5 confirmed: closing the window continues headlessly; requested viewer startup failure reports an error and preserves prior data. Requirements are consolidated in requirements.md. Next step is Research after user approval; no CR1 code changes, tests or commits have been performed.

CR1 Research approval: “进入 Research 阶段”. Installed MuJoCo 3.17.0 viewer source and official docs investigated. Separate viewer state/process is a recommendation, not accepted architecture. Proposed experiments are in research.md; none executed. Next: experiment approval, results, then request Specify approval.

CR1 experiments approved by user (“允许执行两个临时实验”) and completed: E1 viewer closed at step 10, continued to 40, all five arrays exactly match headless baseline despite display-copy mutations; E2 invalid-display child exited 1 in 1.099 s and was reaped. Timeout path and manual camera/window-manager actions remain untested. Evidence: research.md and cr1-research-results.json. Recommend isolated viewer process; architecture not yet accepted. Next: explicit Specify approval; do not implement or advance automatically.

CR1 Specify started: draft amendments in spec.md/interfaces.md; proposed viewer isolation ADR 0003. Round Q7–Q9 covers direction configuration compatibility, isolation architecture and viewer enable/failure policy. Scheduling/snapshot/lifecycle details follow architecture confirmation. No implementation or tests run in this stage.

CR1 Specify Q7–Q9 explicitly approved (“7. yes 8. yes 9. yes”): direction defaults/compatibility, isolated viewer architecture, visualization switches and runtime failure policy. ADR 0003 Accepted for architecture. Remaining frontier Q10/Q11: pacing/cadence and state-transfer/lifecycle bounds. Stage remains Specify / Draft; no production changes or tests.

CR1 Q10/Q11 approved (“10. yes 11. yes”). Final specification: 30 Hz latest-state display, monotonic best-effort pacing, complete integration-state snapshots, 10 s startup and 2/1/1 s shutdown bounds. spec.md/interfaces.md and Accepted ADR 0003 synchronized. No open product-design decisions; next stage Plan requires explicit approval. This turn changes documents only; no runtime tests run.

CR1 Plan: proposed CR1-T1 independent direction signs and CR1-T2 isolated live viewer with complete lifecycle/error behavior. No functional blockers between them; suggested sequential execution reduces edit overlap. Each includes tests/documentation; parent Verify covers their integration. User review required by to-tickets step 4 before publication.

CR1 publication approved by user “yes”. First create returned EOF with no URL; subsequent read-back checks also failed. Do not blindly retry creation. See plan.md publication record and /tmp/pace-cr1-ticket-{1,2}.md. Resume already-authorized publication after connectivity recovers, starting with duplicate detection. No runtime tests or implementation changes.

CR1 publication recovered after user requested retry. #8 independent trajectory directions; #9 isolated live viewer and lifecycle handling. Exact bodies, labels, native parent relationship and empty blocking dependencies verified via REST. Earlier unknown create outcome resolved by duplicate checks before retries. No implementation started.

CR1 implementation checks: 67 tests passed; Pyright/Ruff passed; native X5 40-sample GUI/headless data exactly equal after renderer shutdown fix. Commit preparation and two-axis review pending; manual GUI and formal Verify remain outstanding. User confirmed comparison base 3a02f00. Commit authorized by invoked implement skill; no push/tracker changes authorized.

Review follow-up fixes validated: cancellation during escalation reaps child, timing tests directly observe capped publication/skipped frames, and IPC release no longer waits for traceback GC. Final full suite 70 passed in 13.69 s without warnings; Pyright0 and applicable pre-commit hooks passed. Follow-up commit and reviewer confirmation pending.
