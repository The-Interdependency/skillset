#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: skill_lib_ai_installer
#   module_name: install_ai
#   module_kind: installer
#   summary: installs a stable PATH wrapper that executes the canonical skill-lib tools/ai.sh in place
#   owner: skill-lib
#   public_surface: bash tools/install_ai.sh
#   internal_surface: none
#   auth_boundary: none
#   storage_boundary: writes ~/.local/bin/ai and an idempotent ~/.profile PATH line
#   network_boundary: none
#   user_data_boundary: no credentials read or written
#   admin_only: false
#   tests: tests/test_ai_launcher.py
#   rollout: explicit user invocation
#   rollback: rm ~/.local/bin/ai and remove the marked PATH line if undesired
#   requires: bash
#   since: 2026-09-12
#   unresolved: current shell cannot inherit PATH changes from a child process; reopen shell or source ~/.profile
# === END MODULE_BUILD ===

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SOURCE_DIR/ai.sh"
BIN_DIR="${A0_AI_BIN_DIR:-$HOME/.local/bin}"
TARGET="$BIN_DIR/ai"
PROFILE="${A0_AI_PROFILE:-$HOME/.profile}"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH" # skill-lib ai launcher'

[[ -f "$SOURCE" ]] || { printf 'ERROR: canonical launcher missing: %s\n' "$SOURCE" >&2; exit 2; }
mkdir -p "$BIN_DIR" "${XDG_STATE_HOME:-$HOME/.local/state}/a0/logs"

cat > "$TARGET" <<EOF
#!/usr/bin/env bash
exec bash $(printf '%q' "$SOURCE") "\$@"
EOF
chmod 0755 "$TARGET"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  touch "$PROFILE"
  if ! grep -Fqx "$PATH_LINE" "$PROFILE"; then
    printf '\n%s\n' "$PATH_LINE" >> "$PROFILE"
  fi
fi

printf 'installed: %s\n' "$TARGET"
printf 'source:    %s\n' "$SOURCE"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  printf 'PATH updated for future login shells in %s\n' "$PROFILE"
  printf 'for this shell: export PATH="$HOME/.local/bin:$PATH"\n'
fi
"$TARGET" --help

# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
