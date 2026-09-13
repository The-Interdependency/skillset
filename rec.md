# rec.md

## 2026-08-27T20:24:03Z Shallow Org Audit Recommendations

Usage Guidance:
- Treat this as a routing note for the next audit pass, not a full skill compliance certificate.
- After editing skills or tools, run the local stdlib checks before propagation.

### Provenance
- repository: `The-Interdependency/skill-lib`
- branch: `main`
- starting_commit: `ee553891b17662195f522912afa8fd8914a904a7`
- shallow_evidence: README, AGENTS, ORG_DISTRIBUTION, tool patterns, ratio scan, local targeted tests

### Findings
- Canonical skill source, drift tooling, compliance tooling, `llms.txt`, tests, workflows, and collection point are present.
- `python` is not on PATH in this workspace; `python3` is available and was used.
- Ratio coverage before this edit was `27/57` product source files, with `30` missing seals.
- This task added org report runners and tests under `tools/` and `tests/`.

### Recommendations
- Keep new org-wide runners in `skill-lib/tools` as canonical maintenance instruments.
- Prefer `python3` in newly documented commands unless the environment later restores a `python` shim.
- Run skill-lib drift, compliance, ratios, and unit tests before propagating any skill changes.
- Consider a future strict-ratio campaign for remaining unsealed source files, one family at a time.

### hmmm
- This shallow pass did not normalize historical skills or decide which remaining source files should be ratio-covered.
- No propagation PRs were opened.

## 2026-08-27T21:56:48Z Repair Pass

### Applied
- Repaired `msdmd` tree walking so `.agents` vendored skill directories are skipped.
- Added regression tests for the universal parser walker and collection runner.
- Verified canonical skill-lib with full unit, drift, compliance, and strict ratio gates.

### Validation
- `python3 -m unittest discover -s tests` passed: 199 tests.
- `python3 tools/check_skill_lib_drift.py` passed.
- `python3 tools/check_skill_compliance.py` passed.
- `python3 ratios/ratios_check.py --root . --strict` passed with `28` covered files, `0` gaps, `162` verified checks, and `6` `hmmm`.

### Remaining
- Commit the `msdmd` parser fix, then propagate it to downstream consumers so vendored provenance remains honest.

### hmmm
- Downstream consumers are refreshed to committed `skill-lib@ee553891b17662195f522912afa8fd8914a904a7`, not to this still-uncommitted parser repair.
