# Changelog

## Unreleased — 2026-10-23

### Added

- Loaded-source coverage intervals and internal-gap reporting, bounded complete-line comparisons, explicit saved-draft clearing and concurrency guards, and reduced exports of observed tool-phase totals.
- Revalidate persisted source hashes, avoid phantom lines for empty reads, present CRLF cleanly while preserving copied text, and suppress continuation shortcuts when presentation was clipped.

- Observed source pagination/status, grouped pages, overlap warnings, loaded-source diagnostic links and explicit continuation/range copying, without automatic reads or submissions.
- Paged sealed-diff presentation, whitespace/newline inspection, aggregate file statistics and consultative notes bound to file/digest; full diff copying remains exact.
- Explicit task-draft save/restore through existing account preferences, scoped by conversation/workspace, plus consultative acceptance references and reduced diagnostic exports.
- Observed provider-stream and tool dispatch/handler timings; safe build identity, component-level package mismatch reports, optional source comparison and a pre-cleanup disk-space gate.

### Fixed

- Preserve valid file-read pages up to their existing 20K-character limit instead of clipping their presentation at the generic 10K limit; retain pagination metadata after reload.
- Prevent legacy anonymous task drafts from leaking to accounts after authentication is enabled, and prevent stale draft/source controls from crossing workspaces.
- Prefer the fresh web shell and restrict offline resource fallback to the current service-worker cache.

Validated with offline fixtures only. Desktop packaging/activation evidence is recorded separately from source validation; no model, GUI or governed Desktop E2E claim. Six follow-up architecture proposals remain unapproved.

## Unreleased — 2026-10-22

### Fixed

- Reconcile compatible legacy workspace changes: bounded file-read pagination preserves source references, exposes continuation offsets and flags partial lines without silently skipping unread content. Explicit Portuguese inspection requests are routed without granting execution authority.
- Remove artificial per-token text fades from the incremental renderer while retaining stable code-fence streaming.

- Reject ambiguous streaming tool identities, non-object optional code arguments and unconfirmed/truncated tool streams while preserving valid sibling calls.
- Close nested agent generators on cancellation, preserve replacement save barriers and report interrupted-response persistence failures without exposing storage details.
- Align Ollama thinking-suppression tests with the deliberate endpoint-wide policy; generation parameters remain unchanged.

- Preserve saved conversations during cleanup, reject ambiguous truncation requests and fail closed when image/upload ownership cannot be checked.
- Pin the packaged Python interpreter used by the existing Windows execution boundary; suppress transient console windows during background probes.
- Preserve complete local tool examples, document existing code-navigation tools and reject a governed command round that ends without a tool call.
- Guard native Ollama streaming against degenerate repetition and preserve session identity across asynchronous sends and navigation.
- Reject malformed native code-tool envelopes and schema-incompatible arguments before conversion; invalid native calls no longer fall back to executing textual examples. Preserve explicit empty file/replacement values and aligned valid calls.

### Added

- A common two-file workflow evaluation fixture and pinned replay cases for future self-development; readiness/roadmap entries distinguish local evidence from Desktop, model and engine admission gates. Templates remain draft and are not auto-installed.

- Content-free schema-family cost diagnostics and offline comparisons of existing read/development tool sets, without changing runtime selection or protected context.

- Build-time source fingerprints and package inventory manifests with required-component, source-drift and payload-integrity checks; the existing build invokes them without adding an installer or activation path.

- Browse successful file-read snapshots already loaded in a conversation, with workspace isolation, bounded literal search, line navigation and optional mandate-baseline references. This does not enumerate unread files or introduce a read API.
- Compare all files from one sealed candidate together or individually, with stale-reference guards; explain existing validation recipes without executing them.

- Read-only Desktop build preflight and guards for open canonical executables and linked cleanup targets; engineering evidence provenance, failure inspection guidance and an offline readiness matrix.

- Read-only presentation of reviewed proposals, sealed artifact previews and content-free context diagnostics.
- Studio conversation navigation, collapsible code, activity/file inspection, plan updates and a responsive context panel.
- Observational project scope and engineering review views, a local task-draft composer, tool-failure summaries and plan evidence counts; opening these views does not submit or authorize work.
- Content-free estimates of literal system-message repetition cost and protected copies, with context categories ordered by estimated weight.
- Three portable draft development workflows and a shared game-engine admission preparation covering Godot first, with Unity/Unreal compatibility studies; no new engine execution permissions or runtime integration.
- Review summaries include exact candidate digests/files; context diagnostics compare estimated message/category growth across rounds without removing protected sources.

### Changed

- Desktop builds can reuse verified existing dependencies with `-UseExistingDependencies`, without package installation or downloads. Canonical installation updates follow the founder's single-installation policy; legacy automatic dispatch/retry and parallel Docker deployment are not imported into the Desktop.

- Refine the Graphite/Champagne Studio shell, native Windows frame, conversation titles, operational indicators and public product assets while retaining legacy installation/data identifiers.
- Batch four fixed Git metadata-path queries while preserving before/after fingerprints, repository checks and restricted subprocess settings. One profiled multifile case reduced Git-helper invocations from 697 to 523 and call time from about 45 to 33 seconds; this is not a whole-suite or model-performance claim.

### Validation and limits

- Canonical consolidation passed 142 distinct focused regression cases, covering pagination, confinement, source provenance, routing, rendering boundaries, package integrity and build guards. This is offline/synthetic evidence; GUI and real-model E2E remain pending. Legacy branch/local files remain preserved for traceability; this consolidation does not approve automatic execution inferred from prose.

- The local-roadmap regression selection passed 254 distinct cases, plus one real governed-read/dispatcher case with synthetic provider output. Long-session coverage persisted/reopened 300 messages; workflows used a deliberately failing baseline, a correct candidate and a misleading candidate. No inference, Computer Use or binary activation occurred.

- The existing backup CLI was exercised with disposable SQLite WAL/configuration data through snapshot, verification and restore. No personal data, canonical package or active database was restored or replaced.

- Offline consolidation passed 220 distinct regression cases plus the 22-case two-file promotion audit. These fixtures do not certify Desktop Python E2E, real-model continuity or gameplay.

- The overnight campaign passed 306 distinct cases across separate test selections. A small real Qwen generation demonstrated the local tool-format correction; it did not dispatch a tool.
- The engineering-readiness selection passed 65 cases, including 20 isolated two-file promotion cases; 12 affected workflow/UI cases also passed after final refinements. These overlapping selections are not a full-suite or Desktop E2E certification.
- The subsequent offline-quality selections covered 172 distinct passing cases across protocol/dispatch, persistence/replay, UI/context and Git/promotion invariants. Model-generated repetition remains undiagnosed; no Computer Use, inference, installation or Godot project execution occurred in that cycle.
- The Desktop Python E2E remains unproven. Native automated input did not produce a verifiable effect; the last protocol changes are not yet activated in the open canonical executable.
- Institutional authority baseline: MOBS main at `009feb3558df7919070971656411f6c0a58cf8cf`. No institutional authority/state-machine change, new Computer Use runtime or Godot playtest is delivered here.
- This is a source checkpoint, not a binary release or an institutional product milestone. HISTORY.md was evaluated separately; no new milestone is asserted.
