# Issue #4 — Status

Current stage: CR2 Implement / Project-local kitless CLI fix verified. Collection/fit no longer access KitLauncher during parsing; default Newton and explicit PhysX short CLI runs pass. 92 tests and Pyright pass. Isaac Lab source untouched, existing user task-config edits preserved. Await user-approved Verify; no push/tracker writes.

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

Final CR1 handoff: both independent reviewers confirmed no remaining material Standards/Spec findings after 3076912. Complete test suite70 passed13.69s, no warnings; Pyright0; applicable pre-commit hooks passed with the pre-existing missing-license-template exception. Real X5 mixed-sign GUI/headless short runs produced identical five-tensor datasets. Work committed on current branch per implement skill. User-owned unstaged changes/assets preserved; no push or issue state changes. Next: user-approved Verify, including explicit manual camera/window-manager close evidence and acceptance reconciliation.

CR1 formal Verify authorized (“进入 Verify”) and software checks completed. Evidence: verification.md and cr1-verify-results.json. Independent CLI cases exited0/0/0/1 as expected; five tensors exactly matched and old output hash survived failed viewer startup. Human GUI acceptance question is pending. No production code changes, new commits, pushes or GitHub writes this stage.

CR2 initiated from user request to preserve PaceCfg leg_order/wheel_order and extend data_collection/fit/CMA-ES to wheel velocities. Read-only source review underway; requirements.md records confirmed scope, current integration gaps and round1 questions. Stage order restarts at Explore for this new scope; no production edits, simulations, commits or tracker writes.

CR2 Q1–Q3 confirmed: pure-leg/three-field compatibility (time,dof_pos,des_dof_pos clarified), mixed MuJoCo/Isaac Lab data support, joint leg/wheel fitting outcome with separate errors, and explicit task/data mismatch failure. Next Explore questions Q4/Q5 cover wheel parameter scope and shared vs separate control delays.

CR2 Q4/Q5 confirmed: wheel armature/damping/friction identification; position encoder bias for legs only, no new wheel measurement bias; one shared leg/wheel delay. Next Explore Q6–Q8: supported backends, initially moving wheels and mixed saved fitting results.

CR2 Q6–Q8 confirmed: retain Newton/PhysX, support nonzero initial wheel speeds, persist/show both response groups. Final Explore frontier Q9/Q10 covers data timing/command semantics and software versus user-owned physical fitting acceptance. Research is not yet authorized.

CR2 Q9/Q10 confirmed (“9. yes 10. yes”): aligned actual-sample timestamps and pre-delay desired-command semantics; bounded controlled software identification acceptance, with real-model convergence/physical plausibility user-owned. Explore complete; research handoff recorded in requirements.md. No code changes, tests, simulations, commits or tracker writes in this turn.

CR2 Research: installed Isaac Lab3.0.0 source, cmaes0.13.1 metadata/source and current data/optimizer consumers investigated. Key risks: action mapping, legacy timestamps, source-dependent bias physics, mixed-unit loss, parameter count and result provenance. Research.md records alternatives and E1/E2 proposals; none run. User native trajectory edit conflicts with CR1 contract and awaits clarification; preserve working tree.

User trajectory clarification supersedes prior CR1 physical-center formula for forthcoming alignment: (centers+sin)*amplitudes*directions, with no prior direction multiplication. Current initialization/history mismatch recorded; no production edits made.

CR2 experiments: CPU exit0 (8 generations/population2; warnings and current-layout/zero-score defects documented); Newton2env40step probe passed13.004s; Kit PhysX failed before simulation3.001s due absent IsaacSim, with OVPhysX also not installed. Durable evidence cr2-research-results.json. No production edits or dependency installation. Research design decisions remain for explicit Specify approval.

2026-11-17 checkpoint: user explicitly requested retesting after Isaac Sim installation, normalization, VS Code cache ignore rules and a local commit. EULA explicitly accepted for test processes. PhysX USD import-order failure resolved only in the temporary probe; PhysX passed9.003s and Newton passed8.003s. Added .vscode database/cache ignores, normalized 14 Python files and removed a dangling incomplete import. Preserved user functional edits and recorded remaining failures; no CR2 implementation or stage advance, push, dependency installation or issue write. Next: user-approved Specify to resolve documented contracts and plan production fixes.

CR2 Specify entry (2026-11-17): re-read Issue4, Research evidence, requirements and existing interfaces. Added Draft CR2 specification/interface amendments and asked Q11–Q13. Confirmed requirements and ADR0004 preserved; other physical/data/architecture choices are Proposed. Remaining rounds cover group mapping, initialization, parameter layout/delay, results and measurable acceptance; create/approve consequential ADRs as decisions settle. No production changes, simulations, tests, commits, pushes or GitHub writes.

CR2 Specify Q11–Q13: user chose unified Isaac Lab feedback-and-measurement subtractive bias, rejecting source-specific modes; accepted explicit legacy timing and configurable group scales/weights. ADR0005 records the approved physics change; native realization and initial-state consequences are proposed Q14/Q15, parameter layout Q16. Existing measurement-only native data compatibility remains open. Documents only; no new tests or code changes.

Q14/Q15 explicitly approved: native position command/history and collection physical initial position use desired+b; saved targets remain desired; noise stays measurement-only. Fit restores measured leg position+b and measured wheel velocity, with task-configured missing states recorded each rollout. Q16 remains pending.

Q16–Q19 approved as recorded in spec.md. Q17 explicitly rejects metadata sidecars; declarations belong in fit configuration. Q20 separately asks about rejecting old measurement-only datasets; do not infer that policy from Q17. Q21/Q22 ask delay and bounded controlled acceptance. Native physical migration and old-data timing remain distinct. No production edits or tests.

Q20–Q22 accepted; user explicitly excludes old measurement-only-model compatibility and limits structure/new files to necessity. Final Draft details added to existing spec/interfaces, retaining current classes/entry points and proposing only one shared helper plus one focused test file. Q23 review covers these necessary additions, field/signature/schema details, timing tolerance and stopping rules. No Plan or implementation yet.

CR2 Specify complete: Q23 user answer “批准最终契约及两个必要文件”. Final spec.md consolidation and interfaces.md concrete section are authoritative. No unresolved product/contract questions; future runtime failures require honest verification and explicit design reconsideration rather than silent changes. Only documentation changed; git diff --check passed. Next: user-approved Plan, then bounded tasks with dependencies and test/documentation obligations. No auto-commit, push, GitHub write or production code edit.

CR2 Plan entry: approved specification mapped into four end-to-end slices with tests/docs per ticket, no standalone refactor and no additional structural scope. Initial frontier T1/T2; native collection is not a false prerequisite for fitting against Isaac/synthetic reference. Drafts and acceptance/dependency reasoning are in plan.md. No tracker writes, runtime tests, production changes, commits or pushes. Next: review granularity/edges/merge-split, then publish approved tasks under #4.

CR2 publication complete: #10–#13 created and verified against approved bodies, native parent and blocker edges. Parent content/state/comments unchanged; no earlier issue states changed. Durable links/evidence summary in plan.md. Documentation diff check passed; no runtime tests, commits or pushes. Next: explicitly authorized Implement, starting available frontier #10/#11.

CR2 Implement checks: #10–#13 code implemented;86 tests passed with2 documented upstream population2 warnings; targeted Pyright0. Both backend ActionManager smoke, controlled20-generation fit (>50% objective reduction) and decimation2 delay checks passed. Native-to-fit format roundtrip and actual X5 collection/one-generation fit CLI passed. Details in verification.md and cr2-implement-results.json. User confirmed ecefbfe review base; preparing local implementation commit and mandatory two-axis review. No formal Verify transition or tracker changes.

CR2 implementation review complete: 90 tests passed, Pyright0, short X5 collection rerun passed. Newton warns and strips ratio variables per user clarification; actuator coverage validation now precedes writes. Two independent reviewers confirmed no remaining material findings. Local implementation commit 2a3ddda plus follow-up fix commit; no push/issue edits. See verification.md and cr2-implement-results.json.

Collection follow-up: removed action-transform handling, prepacked commands, typed mapping and contiguous device buffers with completed-data transfer. Newton X5 2env400step five-repeat median 0.558168→0.520894 seconds versus original three-field loop adapter (6.7% less time); equivalent mixed adapter outputs match. Original ecefbfe cannot run unchanged. Full suite91passed, Pyright0, both backend40step smoke passed. Reviewers confirmed no material findings. Detailed evidence and reproducible benchmark sources retained in cr2-implement-results.json.

Kitless CLI follow-up authorized by user “修改代码解决上述问题”: replaced generic launcher argument registration with pure project argparse flags in the existing helper. Both scripts retain official preset/runtime resolution. Regression red/green confirms no parsing-time isaacsim import. Default ANYmal Newton CLI completed with EULA variable absent; explicit PhysX branch also completed with previously authorized test-only acceptance. 92 tests passed; Pyright0; source and evidence recorded in verification.md. No external source changes or inclusion of user task-config edits.
