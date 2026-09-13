#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: gonol_authority_gate
#   module_name: check_gonol_authority
#   module_kind: checker
#   summary: fail-closed local regression gate for UCNS/Stack/EDCM gonol authority across active skill-lib doctrine and projections
#   owner: skill-lib
#   public_surface: bash tools/check_gonol_authority.sh
#   internal_surface: doctrine_files
#   auth_boundary: none
#   storage_boundary: read-only repository files
#   network_boundary: none
#   user_data_boundary: none
#   admin_only: false
#   tests: tests/test_gonol_build_skill.py, tests/test_char_compress_authority.py
#   rollout: skill-lib CI gate
#   rollback: revert only with an explicit authority change and matching doctrine update
#   requires: gonol-build/SKILL.md, char-compress/SKILL.md, active skill-lib projections
#   since: 2026-09-12
#   unresolved: cross-repository authority truth is validated by each owning repository and Stack consistency gates
# === END MODULE_BUILD ===

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# These are operative doctrine/projection surfaces only. Unit tests deliberately
# contain forbidden phrases inside assertNotIn() calls and must not be scanned as
# prose claims by this literal regression gate.
doctrine_files=(
  gonol-build/SKILL.md
  skills/gonol-build/SKILL.md
  char-compress/SKILL.md
  README.md
  AGENTS.md
  CLAUDE.md
  ORG_DISTRIBUTION.md
  skills.json
)

grep -Fq 'UCNS      = gonol objects, constructors, and underlying geometry' gonol-build/SKILL.md
grep -Fq 'Stack     = active language-gonol construction research workspaces' gonol-build/SKILL.md
grep -Fq 'EDCM      = measurement and evaluation of constructed outputs' gonol-build/SKILL.md
grep -Fq 'EDCM owns measurement/evaluation only' gonol-build/SKILL.md
grep -Fq 'research workspace in `The-Interdependency/stack`' char-compress/SKILL.md
grep -Fq 'EDCM owns measurement/evaluation only' char-compress/SKILL.md

grep -Fq 'Stack language-construction research discipline' README.md
grep -Fq 'Stack language-construction research discipline' CLAUDE.md
grep -Fq 'exact owning Stack research workspace' AGENTS.md
grep -Fq 'Stack language-construction research' ORG_DISTRIBUTION.md

for file in "${doctrine_files[@]}"; do
  for stale in \
    'EDCM owns text-domain gonol construction' \
    'UCNS geometry / EDCM text construction' \
    'EDCM owns the admissible scale options' \
    'current UCNS geometry and EDCM admissible scale options' \
    'start in EDCM and consume current UCNS geometry'
  do
    if grep -Fq "$stale" "$file"; then
      printf 'FAIL: stale gonol authority in %s: %s\n' "$file" "$stale" >&2
      exit 1
    fi
  done
done

echo 'gonol authority: OK'
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
