#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

grep -Fq 'UCNS      = gonol objects, constructors, and underlying geometry' gonol-build/SKILL.md
grep -Fq 'Stack     = active language-gonol construction research workspaces' gonol-build/SKILL.md
grep -Fq 'EDCM      = measurement and evaluation of constructed outputs' gonol-build/SKILL.md
! grep -Fq 'EDCM = text-domain gonol construction' gonol-build/SKILL.md
! grep -Fq 'EDCM owns text-domain gonol construction' char-compress/SKILL.md

echo 'gonol authority: OK'
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
