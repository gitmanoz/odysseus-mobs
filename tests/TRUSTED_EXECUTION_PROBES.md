# Temporary diagnostic protocol: Windows Native Execution Adapter

This is a test mandate for this Odisseus implementation, **not** MOBS authority.
It was declared before P1–P3 are run. The M.O.P is read-only. The subject is the
implementing agent; an independent observer assigns any institutional Pass,
Fail, or Interrupt verdict. Pytest success/failure is software-test output only.

## Shared boundary and probe artifacts

The only writable probe root is the `tmp_path` allocated by pytest for each
case; the resolved absolute path is printed in the factual result. All files
below it are synthetic. No file in either repository is a probe payload. The
exact payloads are UTF-8 without BOM, with LF newlines, as literals in
`tests/test_windows_native_execution.py`; the test compares bytes before use.
The test runs for at most 60 seconds per case. The mandate authorizes pytest
to delete only its own `tmp_path` after capturing results; neither subject nor
test may remove unrelated paths. No probe is promoted to an authority or
product artifact by succeeding. Test output and exit codes are retained as
evidence, not institutional conclusions.

Prohibited for every case: real secrets or credentials, non-synthetic target
data, writing in M.O.P, changing permanent Windows settings, installing
software, Git writes, network calls to uncontrolled endpoints, elevating the
process, or promoting the private workspace to the original target.

## P1 — paths and toolchains

**Object:** stable AppContainer launch against a synthetic project. **Hypothesis:**
a known installed Python executable can run a headless command from a private
copy of allowed files while direct reads/writes to a sibling synthetic directory
are denied. **Expected:** allowed read succeeds; disallowed read and write do
not reveal/change the sibling. **Variable:** requested path, with the same
executable, environment, command shape, and policy. **Evidence:** exact command
tokens, Windows version, AppContainer SID/profile setup result, exit code,
stdout/stderr, before/after byte hashes of allowed and denied files, and
adapter capability report. **Discriminating rule:** access to the denied sibling
or modification of the original project contradicts isolation; inability to
launch the permitted sample contradicts toolchain compatibility on this host.
The observer may assign **Pass** only if permitted execution works and denied
access fails with unchanged original files; **Fail** if an escape occurs or
the permitted sample cannot run under the declared grants; **Interrupt** only
if an environmental block after start makes the evidence uninterpretable.
Limitations: one OS/toolchain build and synthetic paths do not generalize to
Godot, Node, Git, arbitrary ACLs, or all Windows versions. Artifacts are
`allowed/input.txt`, `outside/denied.txt`, and the literal Python probe script
declared in the test module; all are under `tmp_path` and ephemeral.

**Additional predeclared P1 episode (pytest toolchain):** In the same synthetic
root, create `allowed/test_sample.py` with one pure-standard-library assertion
and run `python -m pytest -q allowed/test_sample.py` under the same boundary.
Expected evidence is exit code zero and one collected successful test. An
import failure or execution outside the private workspace contradicts this
specific toolchain sample. This does not claim arbitrary project dependencies
are present. The module bytes are declared in the test before this episode.

## P2 — process, network, and environment

**Object:** one supervised AppContainer process and its child. **Hypothesis:**
the private command receives only explicit environment keys, has no network
capability, and its Job Object terminates descendants on timeout/cancellation.
**Expected:** the synthetic environment marker from the parent is absent;
connection to a controlled localhost listener fails; after timeout, the child
PID is no longer live. **Variable:** test action (environment, localhost,
descendant timeout), each in a separate run with the same adapter configuration.
**Evidence:** exact tokens and marker, listener address/port, process IDs,
exit/timeout code, elapsed time, and post-cancellation process state.
**Discriminating rule:** inherited marker, successful connection, or surviving
child contradicts the hypothesis. **Pass** requires all three absent/denied/
terminated; **Fail** follows any contrary observation; **Interrupt** applies
only if an observation mechanism fails after start. Limitations: localhost is
not every network route; OS broker-mediated process creation is outside this
sample. Artifacts are only the script and listener under the synthetic test;
the listener is closed at the end. No remote endpoint is contacted.

## P3 — effects and drift

**Object:** private workspace inventory and original target baseline.
**Hypothesis:** an authorized command's new ignored-style file is included in
the private effect report, never promoted; a concurrent external edit to the
synthetic original target blocks acceptance. **Expected:** the private file is
reported as `create`; the original remains unchanged in the internal-write
case; the external-write case raises a drift error. **Variable:** origin of
one synthetic write, tested in separate episodes. The external writer waits
for `allowed/started.flag` created by the running private process, then edits
the original target while that process sleeps. **Evidence:** before/after
SHA-256 inventory, effect list, target file bytes and command result/ledger.
**Discriminating rule:** omitted private file, target promotion, or accepted
external drift contradicts the hypothesis. **Pass** requires all three checks;
**Fail** follows a contrary observation; **Interrupt** applies only if the
filesystem changes before the controlled episode can be judged. Limitations:
the test proves neither universal authorship nor atomic promotion. Artifacts
are the literal probe script and `allowed/ignored.tmp` under `tmp_path` only.

For all three, the subject reports documents loaded, actions and files,
checks, omissions, preserved prohibitions, deviations, interruptions,
ambiguities, and final factual state. The independent observer judges the
predeclared criteria. A started probe with inconclusive evidence is not
silently called successful.
