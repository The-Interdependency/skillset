from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "tools" / "ai.sh"
INSTALLER = ROOT / "tools" / "install_ai.sh"


class AILauncherTests(unittest.TestCase):
    def test_launcher_is_canonical_tmux_surface(self) -> None:
        text = LAUNCHER.read_text(encoding="utf-8")
        for phrase in (
            'SESSION="${A0_AI_SESSION:-a0}"',
            'CODEX_CMD="${A0_CODEX_CMD:-codex --yolo}"',
            'DEEPCODE_CMD="${A0_DEEPCODE_CMD:-deepcode}"',
            "remain-on-exit on",
            "tmux pipe-pane",
            "#{pane_dead}",
            "#{pane_current_command}",
            "tmux respawn-pane -k",
            'LOG_DIR="${A0_AI_LOG_DIR:-$STATE_HOME/a0/logs}"',
        ):
            self.assertIn(phrase, text)

    def test_launcher_does_not_manage_provider_secrets(self) -> None:
        text = LAUNCHER.read_text(encoding="utf-8")
        for secret_name in (
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "ANTHROPIC_API_KEY",
            "XAI_API_KEY",
        ):
            self.assertNotIn(secret_name, text)

    def test_installer_places_stable_ai_command_on_user_path(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        for phrase in (
            '$HOME/.local/bin',
            'TARGET="$BIN_DIR/ai"',
            'exec bash',
            'skill-lib ai launcher',
            'chmod 0755 "$TARGET"',
        ):
            self.assertIn(phrase, text)

    def test_installer_executes_repo_source_instead_of_copying_it(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('SOURCE="$SOURCE_DIR/ai.sh"', text)
        self.assertNotIn('cp "$SOURCE" "$TARGET"', text)


if __name__ == "__main__":
    unittest.main()
