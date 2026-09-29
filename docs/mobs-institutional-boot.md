# MOBS Institutional Boot — Phase 2, first executable slice

This is a consumer implementation note, not an institutional authority.
Authority remains in the authorized MOBS repository, starting at `PROJECT_INDEX.md`
and governed by `PROJECT_RULES.md` and `AGENT_RUNTIME_INTEGRATION.md`.

## Existing components and boundary

The public `src.agent_loop.stream_agent_loop` remains the entrypoint. Its existing
streaming implementation, tool dispatcher, path confinement, plan-mode policy,
sessions and prompt compactor are reused. The existing chat UI/HTTP/session
flow carries proposals and human decisions; MCP integrations and MOBS Auto
model routing are reused. AI Helpers' `authority-brief` produces
orientation artifacts, not a validated content snapshot; this consumer therefore
reads the selected Index branch directly and does not copy its category map.

This slice performs boot plus tightly scoped filesystem mutation and local
development verification with the existing file and shell tools. It has no new
standalone UI, HTTP endpoint, execution CLI, dispatcher, model router or institutional
memory. Trusted Python callers supply `mobs_execution`; the existing chat
route constructs it only after exact proposal approval and snapshot review.
Ordinary calls, including MOBS Auto model selection alone, retain existing behavior.
Callers must explicitly mark **every** governed turn; inferred natural-language
classification and sticky institutional sessions are outside this slice. Only
the governed `bash` forms described below are enabled; the `python` tool,
Git mutation, publishing, deployment and credential-management tools remain
outside it.

## Chat mandate proposal

### Institutional reviewer authorization

Administrative access is still checked separately. Being an administrator or
running single-user does not grant institutional review authority. Review and
mandate approval require the existing authenticated browser cookie session;
anonymous access, disabled authentication, bearer API attribution and internal
tool impersonation cannot confirm a human review. Ordinary chat keeps its
existing authentication behavior.

`src/mobs_reviewer_authorization.py` consumes one explicit, founder-approved
deployment binding. Version 1 is a JSON document containing `format_version`,
`installation_id` and `authorization`. The authorization contains an `id`,
positive integer `version`, `state` (`active` or `revoked`), the account's
canonical auth-file realm, username and existing `created` incarnation metadata,
the institutional root, explicit categories and relative authority paths, and
founder approval evidence (reference, statement and statement SHA256).
It contains no password hash, session cookie or credential. Renaming or
recreating the account does not silently transfer its institutional authority.

The binding file must resolve outside both repositories. The exact file SHA256
and installation UUID are pinned at server startup through the deployment's
`MOBS_REVIEWER_BINDING_FILE`, `MOBS_REVIEWER_BINDING_SHA256` and
`ODYSSEUS_INSTALLATION_ID`. These are not browser settings or mandate fields.
No binding is automatically created, and no founder account is inferred.

Provisioning is an offline administrative action performed/confirmed by the
founder. Use `python -m src.mobs_reviewer_authorization --help` for the preparatory
command. It requires the existing auth file and selected username, an installation
UUID, authorization ID/version, institutional root, repeated `--category` and
`--authority-path` selections discovered through Index, an approval reference,
an explicit approval evidence file and `--founder-confirmed`. It creates a new
file exclusively and prints the three deployment values to inspect and install.
The founder must approve the complete resulting account/installation/scope
binding before pinning it, then restart the server through the trusted deployment
procedure. Merely invoking this command or providing its confirmation flag does
not enable authority in an already running server.

Keep the binding and deployment pins under operator-controlled protection,
outside agent-editable workspaces and browser-editable settings; do not place
the pins in a project `.env` that agent tools can modify. This trusts the
founder's out-of-band deployment bootstrap. A digest alone cannot identify the
founder, and the runtime does not claim to infer that identity. The approval
record is consumer configuration/provenance, not a new institutional authority.

Every persisted review carries the snapshot, reviewer, account digest,
installation, authorization ID/version, pinned binding digest and approval
reference. The existing JSON columns and ledger are reused; no new database
schema is introduced. The execution receipt must match the persisted human
decision. Client attempts to inject a binding, receipt, founder approval or
identity are rejected. Old reviews without authorization evidence require a
fresh human review; there is no automatic migration to authorized status.

The backend revalidates the authorization on reuse, approval, Boot, each
existing context verification boundary and stream reconnection. A revoked,
modified, substituted, incompatible or unprovisioned binding blocks continuity.
Editing a pinned file immediately invalidates it; an approved replacement needs
its own deployment pin/version and a new human review. Scope covers review of
selected institutional authorities; it grants no tool, mandate approval power
or permission to promote a document to authority. Snapshot changes still require
their own review, and review remains separate from mandate approval.

The existing `/api/chat_stream` route can create and run a reviewed proposal
without a client constructing `mobs_execution`. It accepts the explicit actions
`mobs_action=propose`, `review`, `approve`, or `cancel`, along with the already selected
target `workspace`, the local `mobs_authority_workspace` (or configured
`MOBS_WORKSPACE`), an explicit Decision Tree `mobs_category`, and a
`mobs_profile` of `read_only` or `development`.

The default execution profile is `read_only`. The integration authority's path
is discovered from the official Index rather than pinned in this consumer.
Conditional Programmer context is loaded for materialization; read-only Code
tasks do not load that role. Categories requiring unresolved directory/task
routing remain fail-closed and need an explicit routing adapter.

Each proposal has a unique `proposal_id` and a canonical `proposal_digest`
covering its exact mandate, capabilities, target baseline, source selection and
snapshot evidence. Review, approval and cancellation must echo the displayed
ID, digest and snapshot via `mobs_proposal_id`, `mobs_proposal_digest` and
`mobs_authority_snapshot`. Missing, altered, replaced and replayed versions are
rejected before a state transition. Conditional database updates prevent
concurrent replacement from consuming an approval for an older proposal.
The client cannot submit replacement permissions, evidence or approval flags.
Previous stored proposals lacking version identity must be proposed again.

`propose` reads `PROJECT_INDEX.md` first and returns `mobs_mandate_proposal` in
the existing chat SSE stream. It creates an authority snapshot from the source
repository branch, commit, working-tree fingerprint, selected authority paths
and their hashes. A `review` action records a human institutional review for
that exact snapshot only; it may be reused only when the snapshot ID remains
identical, the authenticated account incarnation matches, and its versioned
institutional authorization remains valid. A changed authority or source
baseline invalidates it. Review leaves the mandate pending; mandate approval
cannot create an authority review. Buttons appear after the readable evidence
and bind each human confirmation to that displayed version.

The proposal is stored only with that chat session alongside the selected
project, baselines, status and eventual ledger. `approve` authorizes the
objective and permissions only after the matching authority review exists. It
then revalidates saved evidence with Institutional Boot and invokes the existing
Agent Loop with the resulting explicit mandate. `cancel` cannot execute it.
The browser sends actions, version references and selected workspaces; it cannot submit a
mandate, authority hashes, baselines, review state, or approvals.

The review view includes the source repository, branch, commit, working-tree
status and fingerprint, selected authority paths and hashes, and read-only
authority contents. The MOBS composer control also selects a confirmed project
capability profile. Version 1 supports `generic` (real ordinary root entries),
`python` (existing `src`, `tests`, `docs`, Python configuration and requirements
files), and `godot` (a real `project.godot` plus recognized existing Godot
directories). The backend derives paths and commands; changing a profile or its
capabilities requires a new proposal. A Godot headless validation command is
offered only when a local Godot executable is already available.

## Input to the existing loop

The keyword accepts a Python dictionary with these required fields:

- `source`: authorized institutional repository snapshot.
- `target`: authorized execution repository snapshot (may be the same repository).
- `mandate`: nonempty scope/objective supplied by the responsible caller.
- `exclusions`: nonempty limits (use an explicit statement if there are none).
- `category`: exact Decision Tree branch label, e.g. `Código`.
- `authorities`: mapping of selected relative Markdown paths to reviewed SHA-256
  digests, including Index, AI_CONTEXT, PROJECT_RULES, the integration authority,
  all unconditional Markdown paths in the selected branch, and applicable
  conditional authorities selected by the reviewer.
- `authority_review`: `consistent`, supplied after institutional review of this
  exact content. Missing, ambiguous or contradictory reviews block execution.
- `objective`, `scope`, and `exclusions`: the executable objective, boundary and
  exclusions. `exclusions` must exactly match the boot-level exclusions.
- `allowed_paths`: nonempty POSIX-relative glob paths within the target project.
- `allowed_tools`: an explicit subset of `read_file`, `ls`, `grep`, `glob`,
  `get_workspace`, `write_file`, `edit_file`, `apply_patch`, and `bash`.
- `allowed_operations`: explicit operations. In addition to `read`, `write`,
  and `delete`, shell mandates can permit `test`, `lint`, `typecheck`,
  `build`, and `git_read`.
- `allowed_commands`: an explicit list of command prefixes. It is mandatory
  when `bash` is allowed, and a closed development grammar narrows it further:
  `pytest` / `python -m pytest`, `ruff check` or `ruff format`, `mypy`,
  `pyright`, `npm test` / `npm run lint|typecheck|build`, and read-only Git
  `status`, `diff`, `log`, `show`, or `branch [--show-current]`. Shell
  composition, absolute and parent paths, Git repository overrides and every
  other command form are rejected before the existing dispatcher runs.
- `approval_required_operations`: operations which require an approval marker;
  `approvals`: a mapping from operation to a nonempty approval identifier.
  `delete` and credential-like paths always require approval regardless of this
  list. Publication, deployment, force push, scope expansion and writes outside
  the target workspace are unsupported and blocked in this slice.
- `limits`: `{ "max_steps": 1..100, "time_limit_seconds": 1..3600 | null,
  "command_timeout_seconds": 1..600 | null }`. A shell mandate requires a
  non-null command timeout; it is passed to the existing `BashTool` for that
  one dispatcher call.

Each repository snapshot has exactly `path` (canonical absolute repository root),
`branch`, `head` (full immutable commit id), `working_tree_status` (porcelain
status with newline separators), and `working_tree_sha256`.
`capture_repository(path)` captures evidence **for review**, not authorization.
Do not recapture and accept changed baselines automatically. The tree fingerprint
includes status, staged/unstaged diffs and nonignored untracked contents. Ignored
files are outside the tree fingerprint; selected authority contents are always
rechecked separately. Submodules and detached HEADs are unsupported and block.

Authority hashes use `authority_digest(path.read_text(encoding="utf-8-sig"))`:
UTF-8 decoded text, universal newlines, no BOM. Digest creation is evidence
collection, not a semantic review. A caller must not manufacture `consistent`
merely because hashes match. This slice detects structural invalidity, conflict
markers, explicit unresolved review, unauthorized content changes, missing
required sources and baseline drift. It does **not** claim automated discovery of
arbitrary contradictions in natural-language prose. That review remains institutional.

Example after the mandate and snapshots have been reviewed:

```python
from src.agent_loop import stream_agent_loop

async for event in stream_agent_loop(
    endpoint_url, model, messages,
    owner=authorized_owner,
    workspace=reviewed_mandate['target']['path'],
    mobs_execution=reviewed_mandate,
    context_length=model_context_length,
):
    consume_existing_sse(event)
```

Provide the real model context capacity. The existing owner/admin check applies
before any institutional read. A configured explicit repository root is the
workspace discovery seed; the consumer resolves and checks its Git identity,
then reads Index as the first institutional document. It does not scan unrelated
folders, pick another repository, infer a branch, or fetch remotes.

## Fail-closed and context lifecycle

Only the selected sources are loaded, in Index-first order, with path confinement,
UTF-8/size/content validation and reviewed hashes. Unsupported/ambiguous Index
routing formats (including directory-only routes) stop rather than guess.
Conditional selection is explicit in the reviewed mandate; this first parser
supports direct Markdown file routes and does not invent a second routing map.

The protected institutional message is inserted after reduced-prompt selection
and before existing compaction, checked after compaction and before each round.
Authority text is not summarized or silently truncated. Capacity overflow blocks
when the caller supplies `context_length`. Repository and authority drift are
checked before model rounds, before tools and at completion. The source/target
snapshots and authority digests accompany the context for provenance.

Before every tool, the runtime verifies the source and target state, the time and
step limits, tool, operation, approval and affected paths. It then invokes the
same existing dispatcher. Governed shell calls use the dispatcher-bound target
workspace as their cwd and the mandate timeout. Git is read-only in this slice:
commit, push, pull, checkout/switch, reset, clean, rebase and merge cannot pass
the command grammar. Installation, deployment, publication and secret access are
also outside it. After an allowed mutation or command, it compares the
working-tree entries before and after it; a changed path outside reviewed paths
is external drift and blocks completion. The ledger records the command, its
operation, exit code, output digest and changed paths alongside before/after
snapshots. The original baseline remains in the context.

Events use existing SSE framing: `institutional_boot`, `institutional_mutation`,
`institutional_command`, `institutional_verified` and `institutional_blocked`; blocked runs also emit a readable `delta`. Completion
is delayed until the final verification succeeds. These events are available to
the runtime caller and the existing chat UI. Proposal/review persistence uses
the existing MOBS session tables; this alignment introduces no new schema.
Model output streamed before a subsequently detected drift remains provisional.
The checks are boundary checks, not filesystem locks or an OS security sandbox.

## Validation

`python -m pytest tests/test_mobs_institutional_boot.py tests/test_agent_loop.py
 tests/test_agent_rounds_exhausted.py tests/test_workspace_confine.py
 tests/test_mobs_auto_router.py -q`

Tests use temporary local repositories and mock model output; they cover real
Git snapshots, selected authority loading, errors, in-turn drift, actual prompt
compaction and execution of the existing loop. No live model or remote MOBS
service is required. No MOBS authority is changed by this implementation.
