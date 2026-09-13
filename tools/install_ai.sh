#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: skill_lib_ai_installer
#   module_name: install_ai
#   module_kind: installer
#   summary: installs the canonical skill-lib tools/ai.sh into the caller's PATH, preferring Termux $PREFIX/bin and otherwise ~/.local/bin
#   owner: skill-lib
#   public_surface: bash tools/install_ai.sh
#   internal_surface: PATH target selection and symlink installation
#   auth_boundary: none
#   storage_boundary: writes one ai.sh symlink and, outside an already-on-PATH bin directory, one idempotent ~/.profile PATH line
#   network_boundary: none
#   user_data_boundary: no credentials read or written
#   admin_only: false
#   tests: tests/test_ai_launcher.py
#   rollout: explicit user invocation
#   rollback: remove the installed ai.sh symlink and marked PATH line if one was added
#   requires: bash
#   since: 2026-09-12
#   unresolved: a current shell cannot inherit a newly appended PATH line from a child process
# === END MODULE_BUILD ===

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SOURCE_DIR/ai.sh"
PROFILE="${A0_AI_PROFILE:-$HOME/.profile}"

if [[ -n "${A0_AI_BIN_DIR:-}" ]]; then
  BIN_DIR="$A0_AI_BIN_DIR"
elif [[ -n "${PREFIX:-}" && -d "$PREFIX/bin" && -w "$PREFIX/bin" ]]; then
  BIN_DIR="$PREFIX/bin"
else
  BIN_DIR="$HOME/.local/bin"
fi

TARGET="$BIN_DIR/ai.sh"
[[ -f "$SOURCE" ]] || { printf 'ERROR: canonical launcher missing: %s\n' "$SOURCE" >&2; exit 2; }
mkdir -p "$BIN_DIR"
chmod 0755 "$SOURCE"
ln -sfn "$SOURCE" "$TARGET"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  mkdir -p "$(dirname "$PROFILE")"
  touch "$PROFILE"
  path_line="export PATH=\"$BIN_DIR:\$PATH\" # skill-lib ai launcher"
  if ! grep -Fqx "$path_line" "$PROFILE"; then
    printf '\n%s\n' "$path_line" >> "$PROFILE"
  fi
  printf 'PATH updated for future login shells in %s\n' "$PROFILE"
  printf 'for this shell: export PATH=%q:\$PATH\n' "$BIN_DIR"
fi

printf 'installed: %s -> %s\n' "$TARGET" "$SOURCE"
bash "$TARGET" --help

# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
