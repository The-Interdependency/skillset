#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: gonol_authority_gate
#   module_name: check_gonol_authority
#   module_kind: checker
#   summary: fail-closed local regression gate for UCNS/Stack/EDCM gonol authority across active skill-lib surfaces
#   owner: skill-lib
#   public_surface: bash tools/check_gonol_authority.sh
#   internal_surface: active_files
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

active_files=(
  gonol-build/SKILL.md
  skills/gonol-build/SKILL.md
  char-compress/SKILL.md
  README.md
  AGENTS.md
  CLAUDE.md
  ORG_DISTRIBUTION.md
  skills.json
  tests/test_gonol_build_skill.py
  tests/test_char_compress_authority.py
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

for file in "${active_files[@]}"; do
  if grep -Fq 'EDCM owns text-domain gonol construction' "$file"; then
    printf 'FAIL: stale EDCM construction authority in %s\n' "$file" >&2
    exit 1
  fi
  if grep -Fq 'UCNS geometry / EDCM text construction' "$file"; then
    printf 'FAIL: stale UCNS/EDCM authority split in %s\n' "$file" >&2
    exit 1
  fi
done

echo 'gonol authority: OK'
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
