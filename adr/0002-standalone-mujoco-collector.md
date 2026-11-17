# 独立采集模块与配置边界

Status: Accepted. User-approved decisions implemented in 87da096; software acceptance recorded in .scratch/issue_4/verification.md.

## Context / problem

Existing pace_sim2real package initialization imports Isaac Lab configuration. The native MuJoCo collector needs testable behavior independent of that import path. Physics and excitation settings have different owners and change independently.

## Alternatives

A monolithic collection script; a package module coupled to current initialization; refactoring package initialization to lazy imports; or a thin script with a standalone sibling module and TOML configuration.

## Decision and rationale

Use scripts/pace/data_collection_mujoco.py as CLI, scripts/pace/mujoco_collection.py as testable collection module and config/x5_collection.toml for run/trajectory/measurement settings. Keep physics and sensor noise authoritative in user-owned MJCF. This isolates the collector without unrelated package-initialization changes.

## Consequences / trade-offs

The entry point runs from a source checkout, with no new installed CLI or generic robot framework. Tests can exercise collection independently of Isaac Lab. Future library reuse may justify a separate packaging decision. Existing package root helpers cannot be imported blindly because they trigger the package initializer.

## Evidence

src/pace_sim2real/__init__.py and src/pace_sim2real/utils/__init__.py import Isaac Lab-dependent modules. See .scratch/issue_4/spec.md and interfaces.md for the implemented contract.

## Approval reference

Q8 described independent CLI/module plus TOML, retaining XML ownership of physics/noise; user replied “8. yes”. Q9/Q10 separately approved sampling/defaults and output replacement. Subsequent explicit Implement and Verify approvals are recorded in the Issue stage documents.
