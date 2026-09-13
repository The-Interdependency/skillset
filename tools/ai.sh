# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
set -euo pipefail

# === MODULE_BUILD ===
# id: skill_lib_ai_launcher
#   module_name: ai
#   module_kind: cli
#   summary: canonical Termux-side SSH/tmux launcher for coding-agent CLIs on the a0 development VM with health, restart, key propagation, and persistent remote pane logs
#   owner: skill-lib
#   public_surface: ai.sh start|attach|status|restart|logs|keys|grok|codex|deepcode|shell
#   internal_surface: remote bash quoting, tmux session/window lifecycle, key-to-tmux propagation
#   auth_boundary: SSH host alias and third-party CLIs own authentication; launcher never prints key values
#   storage_boundary: remote pane logs under ~/.local/state/a0/logs; no secret persistence
#   network_boundary: SSH to configured VM host only
#   user_data_boundary: provider key values are only copied from the VM login environment into the VM tmux server environment
#   admin_only: false
#   tests: tests/test_ai_launcher.py
#   rollout: explicit install via tools/install_ai.sh
#   rollback: remove installed ai.sh symlink; canonical source remains in skill-lib
#   requires: local bash + ssh; remote bash + tmux; optional remote grok/codex/deepcodei CLIs
#   since: 2026-09-12
#   unresolved: third-party CLI executable names and provider authentication methods may change
# === END MODULE_BUILD ===

HOST="${A0_AI_HOST:-a0}"
SESSION="${A0_AI_SESSION:-a0}"
REMOTE_LOG_SUBDIR="${A0_AI_REMOTE_LOG_SUBDIR:-.local/state/a0/logs}"
GROK_CMD="${A0_GROK_CMD:-grok}"
CODEX_CMD="${A0_CODEX_CMD:-codex --yolo}"
DEEPCODE_CMD="${A0_DEEPCODE_CMD:-deepcodei}"
SHELL_CMD="${A0_SHELL_CMD:-exec \"\${SHELL:-/bin/bash}\" -l}"
KEY_VARS="${A0_AI_KEY_VARS:-OPENAI_API_KEY XAI_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY}"

usage() {
  cat <<'EOF'
usage: ai.sh [command]

commands:
  start                 ensure a0 tmux session and expected windows exist
  attach                attach to the a0 tmux session
  status | -list        show expected windows and actual pane/process state
  restart NAME          restart grok, codex, deepcode, shell, or all
  -restart NAME         compatibility alias for restart
  logs [NAME]           tail persistent remote pane log (default: deepcode)
  keys                  propagate VM login-shell provider keys into tmux; print presence only
  grok | -grok          ensure/select Grok and attach
  codex | -codex        ensure/select Codex and attach
  deepcode|-deepcode|-deepcodei
                        ensure/select DeepCode and attach
  shell                 ensure/select VM shell and attach
  menu                  interactive selector (default)

configuration:
  A0_AI_HOST, A0_AI_SESSION, A0_GROK_CMD, A0_CODEX_CMD,
  A0_DEEPCODE_CMD, A0_SHELL_CMD, A0_AI_KEY_VARS
EOF
}

q() { printf '%q' "$1"; }

remote() {
  local script="$1"
  ssh "$HOST" "bash -lc $(q "$script")"
}

remote_tty() {
  local script="$1"
  ssh -tt "$HOST" "bash -lc $(q "$script")"
}

require_remote() {
  if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" 'command -v tmux >/dev/null 2>&1'; then
    printf 'ERROR: cannot reach %s non-interactively with remote tmux available\n' "$HOST" >&2
    return 1
  fi
}

session_exists() {
  remote "tmux has-session -t $(q "$SESSION") 2>/dev/null"
}

window_exists() {
  local name="$1"
  session_exists && remote "tmux list-windows -t $(q "$SESSION") -F '#W' | grep -Fxq $(q "$name")"
}

pane_dead() {
  local name="$1"
  remote "tmux display-message -p -t $(q "$SESSION:$name.0") '#{pane_dead}'"
}

pipe_log() {
  local name="$1" target="$SESSION:$1.0" command
  command="cat >> \"\$HOME/$REMOTE_LOG_SUBDIR/$name.log\""
  remote "mkdir -p \"\$HOME/$REMOTE_LOG_SUBDIR\"; tmux pipe-pane -o -t $(q "$target") $(q "$command")"
}

sync_keys() {
  session_exists || return 0
  local script
  script="for key in $KEY_VARS; do value=\"\${!key-}\"; if [[ -n \"\$value\" ]]; then tmux set-environment -t $(q "$SESSION") \"\$key\" \"\$value\"; fi; done"
  remote "$script"
}

keys_status() {
  ensure_session
  sync_keys
  local script
  script="for key in $KEY_VARS; do if tmux show-environment -t $(q "$SESSION") \"\$key\" >/dev/null 2>&1; then printf '%-18s present\\n' \"\$key\"; else printf '%-18s missing\\n' \"\$key\"; fi; done"
  remote "$script"
}

ensure_session() {
  require_remote
  if ! session_exists; then
    remote "tmux new-session -d -s $(q "$SESSION") -n shell"
  fi
  remote "tmux set-option -w -t $(q "$SESSION:shell") remain-on-exit on 2>/dev/null || true; mkdir -p \"\$HOME/$REMOTE_LOG_SUBDIR\""
  pipe_log shell || true
  sync_keys || true
}

spec() {
  case "$1" in
    shell) printf '0|shell|%s\n' "$SHELL_CMD" ;;
    grok) printf '1|grok|%s\n' "$GROK_CMD" ;;
    codex) printf '2|codex|%s\n' "$CODEX_CMD" ;;
    deepcode) printf '3|deepcode|%s\n' "$DEEPCODE_CMD" ;;
    *) return 2 ;;
  esac
}

ensure_window_shell() {
  local index="$1" name="$2"
  ensure_session
  if window_exists "$name"; then
    remote "tmux set-option -w -t $(q "$SESSION:$name") remain-on-exit on"
    pipe_log "$name" || true
    return 0
  fi

  local occupied
  occupied="$(remote "tmux list-windows -t $(q "$SESSION") -F '#I:#W' | grep '^${index}:' || true")"
  if [[ -n "$occupied" ]]; then
    printf 'ERROR: expected window %s at index %s, but %s occupies it\n' "$name" "$index" "$occupied" >&2
    return 3
  fi
  remote "tmux new-window -d -t $(q "$SESSION:$index") -n $(q "$name")"
  remote "tmux set-option -w -t $(q "$SESSION:$name") remain-on-exit on"
  pipe_log "$name" || true
}

respawn() {
  local name="$1" command_line="$2" binary pane_command
  binary="${command_line%% *}"
  if ! remote "command -v $(q "$binary") >/dev/null 2>&1"; then
    printf 'ERROR: %s is not installed on %s\n' "$binary" "$HOST" >&2
    return 127
  fi
  sync_keys || true
  pane_command="exec bash -lc $(q "$command_line")"
  remote "tmux respawn-pane -k -t $(q "$SESSION:$name.0") $(q "$pane_command")"
  pipe_log "$name" || true
}

ensure_agent() {
  local agent="$1" row index name command_line dead
  row="$(spec "$agent")"
  IFS='|' read -r index name command_line <<<"$row"
  ensure_window_shell "$index" "$name"
  dead="$(pane_dead "$name")"
  if [[ "$agent" != shell && "$dead" == 1 ]]; then
    respawn "$name" "$command_line"
  fi
}

start_all() {
  ensure_window_shell 0 shell
  ensure_agent grok || true
  ensure_agent codex || true
  ensure_agent deepcode || true
}

restart_one() {
  local agent="$1" row index name command_line
  row="$(spec "$agent")" || {
    printf 'ERROR: unknown restart target: %s\n' "$agent" >&2
    return 2
  }
  IFS='|' read -r index name command_line <<<"$row"
  ensure_window_shell "$index" "$name"
  if [[ "$agent" == shell ]]; then
    local pane_command
    pane_command="exec bash -lc $(q "$command_line")"
    remote "tmux respawn-pane -k -t $(q "$SESSION:$name.0") $(q "$pane_command")"
    pipe_log "$name" || true
  else
    respawn "$name" "$command_line"
  fi
}

restart() {
  local target="${1:-all}"
  case "$target" in
    all)
      restart_one shell || true
      restart_one grok || true
      restart_one codex || true
      restart_one deepcode || true
      ;;
    grok|codex|deepcode|shell) restart_one "$target" ;;
    *) printf 'ERROR: restart target must be grok, codex, deepcode, shell, or all\n' >&2; return 2 ;;
  esac
}

status() {
  require_remote
  if ! session_exists; then
    printf 'session %-12s missing on %s\n' "$SESSION" "$HOST"
    return 1
  fi
  remote "tmux list-panes -s -t $(q "$SESSION") -F '#{window_index}\\t#{window_name}\\tdead=#{pane_dead}\\tpid=#{pane_pid}\\tcommand=#{pane_current_command}' | sort -n"
}

attach_window() {
  local name="$1"
  remote_tty "tmux select-window -t $(q "$SESSION:$name") && exec tmux attach-session -t $(q "$SESSION")"
}

open_agent() {
  local agent="$1" row index name command_line dead
  row="$(spec "$agent")"
  IFS='|' read -r index name command_line <<<"$row"
  ensure_window_shell "$index" "$name"
  dead="$(pane_dead "$name")"
  if [[ "$agent" != shell && "$dead" == 1 ]]; then
    respawn "$name" "$command_line"
  fi
  attach_window "$name"
}

logs() {
  local name="${1:-deepcode}"
  case "$name" in shell|grok|codex|deepcode) ;; *) printf 'ERROR: unknown log: %s\n' "$name" >&2; return 2 ;; esac
  ensure_session
  remote "file=\"\$HOME/$REMOTE_LOG_SUBDIR/$name.log\"; if [[ -f \"\$file\" ]]; then tail -n ${A0_AI_LOG_LINES:-200} \"\$file\"; else printf 'no log yet: %s\\n' \"\$file\"; exit 1; fi"
}

menu() {
  ensure_session
  while true; do
    cat <<'EOF'

AI on a0:
  1) Grok
  2) Codex
  3) DeepCode
  4) Shell
  5) Keys
  6) Status
  7) Restart
  8) Logs
  0) Quit
EOF
    read -r -p '> ' choice
    case "$choice" in
      1) open_agent grok ;;
      2) open_agent codex ;;
      3) open_agent deepcode ;;
      4) open_agent shell ;;
      5) keys_status ;;
      6) status || true ;;
      7) read -r -p 'restart [grok/codex/deepcode/shell/all]: ' target; restart "${target:-all}" || true ;;
      8) read -r -p 'log [deepcode/codex/grok/shell]: ' target; logs "${target:-deepcode}" || true ;;
      0) return 0 ;;
      *) printf 'unknown choice\n' ;;
    esac
  done
}

case "${1:-menu}" in
  start) start_all ;;
  attach) ensure_session; remote_tty "exec tmux attach-session -t $(q "$SESSION")" ;;
  status|-list) status ;;
  restart) shift; restart "${1:-all}" ;;
  -restart) shift; restart "${1:-all}" ;;
  logs) shift; logs "${1:-deepcode}" ;;
  keys) keys_status ;;
  grok|-grok) open_agent grok ;;
  codex|-codex) open_agent codex ;;
  deepcode|-deepcode|-deepcodei) open_agent deepcode ;;
  shell) open_agent shell ;;
  menu) menu ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
# ratios: loc_comments=hmmm imports_exports=hmmm calls_definitions=hmmm
