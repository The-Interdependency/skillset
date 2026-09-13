#!/usr/bin/env bash
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: skill_lib_ai_launcher
#   module_name: ai
#   module_kind: cli
#   summary: canonical tmux launcher for coding-agent CLIs on the development VM with pane health, restart, and persistent pane logs
#   owner: skill-lib
#   public_surface: ai start|attach|status|restart|logs|grok|codex|deepcode|shell
#   internal_surface: tmux session/window lifecycle helpers
#   auth_boundary: launched CLIs own their authentication
#   storage_boundary: writes logs under ~/.local/state/a0/logs only
#   network_boundary: none directly
#   user_data_boundary: does not read or print provider credentials
#   admin_only: false
#   tests: tests/test_ai_launcher.py
#   rollout: explicit install via tools/install_ai.sh
#   rollback: remove ~/.local/bin/ai wrapper
#   requires: bash, tmux; optional grok/codex/deepcode CLIs
#   since: 2026-09-12
#   unresolved: host-local third-party CLI command names may change
# === END MODULE_BUILD ===

SESSION="${A0_AI_SESSION:-a0}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
LOG_DIR="${A0_AI_LOG_DIR:-$STATE_HOME/a0/logs}"
SHELL_CMD="${A0_SHELL_CMD:-${SHELL:-/bin/bash} -l}"
GROK_CMD="${A0_GROK_CMD:-grok}"
CODEX_CMD="${A0_CODEX_CMD:-codex --yolo}"
DEEPCODE_CMD="${A0_DEEPCODE_CMD:-deepcode}"
mkdir -p "$LOG_DIR"

usage() {
  cat <<'EOF'
usage: ai [start|attach|status|restart [agent|all]|logs [agent]|grok|codex|deepcode|shell|menu]
EOF
}

require_tmux() { command -v tmux >/dev/null 2>&1 || { echo 'tmux is required' >&2; exit 127; }; }
has_session() { tmux has-session -t "$SESSION" 2>/dev/null; }
window_exists() { has_session && tmux list-windows -t "$SESSION" -F '#W' | grep -Fxq "$1"; }

ensure_session() {
  require_tmux
  has_session || tmux new-session -d -s "$SESSION" -n bash
}

ensure_window() {
  local index="$1" name="$2"
  ensure_session
  if ! window_exists "$name"; then
    if tmux list-windows -t "$SESSION" -F '#I' | grep -Fxq "$index"; then
      tmux new-window -d -t "$SESSION" -n "$name"
    else
      tmux new-window -d -t "$SESSION:$index" -n "$name"
    fi
  fi
  tmux set-option -w -t "$SESSION:$name" remain-on-exit on >/dev/null
}

pipe_log() {
  local name="$1" file="$LOG_DIR/$1.log" quoted
  quoted="$(printf '%q' "$file")"
  tmux pipe-pane -o -t "$SESSION:$name.0" "cat >> $quoted"
}

launch() {
  local index="$1" name="$2" command_line="$3" binary quoted
  ensure_window "$index" "$name"
  binary="${command_line%% *}"
  pipe_log "$name"
  if ! command -v "$binary" >/dev/null 2>&1; then
    printf 'command unavailable: %s\n' "$binary" >&2
    return 127
  fi
  quoted="$(printf '%q' "$command_line")"
  tmux respawn-pane -k -t "$SESSION:$name.0" "exec bash -lc $quoted"
  pipe_log "$name"
}

ensure_shell() {
  ensure_window 2 bash
  pipe_log bash
}

start_all() {
  ensure_session
  launch 0 grok-4-fast "$GROK_CMD" || true
  launch 1 codex "$CODEX_CMD" || true
  ensure_shell
  launch 3 deepcode "$DEEPCODE_CMD" || true
}

status() {
  require_tmux
  has_session || { printf 'session %s missing\n' "$SESSION"; return 1; }
  tmux list-panes -a -t "$SESSION" -F '#{window_index}\t#{window_name}\tdead=#{pane_dead}\tpid=#{pane_pid}\tcommand=#{pane_current_command}' | sort -n
}

restart_one() {
  case "$1" in
    grok|grok-4-fast) launch 0 grok-4-fast "$GROK_CMD" ;;
    codex) launch 1 codex "$CODEX_CMD" ;;
    deepcode) launch 3 deepcode "$DEEPCODE_CMD" ;;
    shell|bash) launch 2 bash "$SHELL_CMD" ;;
    *) printf 'unknown target: %s\n' "$1" >&2; return 2 ;;
  esac
}

restart() {
  local target="${1:-all}"
  if [[ "$target" == all ]]; then
    restart_one grok || true
    restart_one codex || true
    restart_one shell || true
    restart_one deepcode || true
  else
    restart_one "$target"
  fi
}

attach_window() {
  local name="$1"
  if [[ -n "${TMUX-}" ]]; then
    tmux switch-client -t "$SESSION:$name"
  else
    tmux select-window -t "$SESSION:$name"
    exec tmux attach-session -t "$SESSION"
  fi
}

open_agent() {
  local name="$1"
  case "$name" in
    grok|grok-4-fast) window_exists grok-4-fast || restart_one grok || true; attach_window grok-4-fast ;;
    codex) window_exists codex || restart_one codex || true; attach_window codex ;;
    deepcode) window_exists deepcode || restart_one deepcode || true; attach_window deepcode ;;
    shell|bash) window_exists bash || ensure_shell; attach_window bash ;;
  esac
}

logs() {
  local name="${1:-deepcode}" file="$LOG_DIR/${1:-deepcode}.log"
  [[ -f "$file" ]] || { printf 'no log yet: %s\n' "$file"; return 1; }
  tail -n "${A0_AI_LOG_LINES:-200}" "$file"
}

menu() {
  ensure_session
  while true; do
    printf '\n1 Grok  2 Codex  3 DeepCode  4 Shell  5 Status  6 Restart  7 Logs  8 Start/repair all  0 Exit\n'
    read -r -p '> ' choice
    case "$choice" in
      1) open_agent grok ;;
      2) open_agent codex ;;
      3) open_agent deepcode ;;
      4) open_agent shell ;;
      5) status || true ;;
      6) read -r -p 'restart [grok/codex/deepcode/shell/all]: ' target; restart "${target:-all}" || true ;;
      7) read -r -p 'log [deepcode/codex/grok-4-fast/bash]: ' target; logs "${target:-deepcode}" || true ;;
      8) start_all ;;
      0) return ;;
      *) echo 'unknown choice' ;;
    esac
  done
}

case "${1:-menu}" in
  start) start_all ;;
  attach) ensure_session; exec tmux attach-session -t "$SESSION" ;;
  status) status ;;
  restart) shift; restart "${1:-all}" ;;
  logs) shift; logs "${1:-deepcode}" ;;
  grok|grok-4-fast|codex|deepcode|shell|bash) ensure_session; open_agent "$1" ;;
  menu) menu ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac

# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
