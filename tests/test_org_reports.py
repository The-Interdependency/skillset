# ratios: loc_comments=70:34 imports_exports=7:2 calls_definitions=40:7
"""Tests for org-wide recommendation and ratio report runners."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import aggregate_org_rec as recs  # noqa: E402
import org_ratio_compare as ratios  # noqa: E402

# === CHECKS ===
# id: check_org_rec_append_only
#   proves: org_rec_append_only
#   call: self::test_aggregate_append_preserves_existing_content
#   requires: python3, posix_shell
#   timeout: 5
#   mutates: filesystem
#   cleanup: tempdir_teardown
#
# id: check_org_rec_missing_repo_visible
#   proves: org_rec_missing_repo_visible
#   call: self::test_aggregate_lists_missing_rec_files
#   requires: python3, posix_shell
#   timeout: 5
#   mutates: filesystem
#   cleanup: tempdir_teardown
#
# id: check_org_rec_remaining_fallback
#   proves: org_rec_remaining_fallback
#   call: self::test_aggregate_uses_remaining_when_latest_block_has_no_recommendations
#   requires: python3, posix_shell
#   timeout: 5
#   mutates: filesystem
#   cleanup: tempdir_teardown
#
# id: check_org_ratio_skips_vendored_skills
#   proves: org_ratio_skips_vendored_skills
#   call: self::test_ratio_metrics_skip_vendored_agents
#   requires: python3, posix_shell
#   timeout: 5
#   mutates: filesystem
#   cleanup: tempdir_teardown
#
# id: check_org_ratio_oddities_visible
#   proves: org_ratio_oddities_visible
#   call: self::test_ratio_report_lists_low_coverage_oddity
#   requires: python3, posix_shell
#   timeout: 5
#   mutates: filesystem
#   cleanup: tempdir_teardown
# === END CHECKS ===


class OrgRecommendationReportTests(unittest.TestCase):
    def test_aggregate_append_preserves_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "alpha"
            (repo / ".git").mkdir(parents=True)
            (repo / "rec.md").write_text(
                "## Shallow Audit - fixed\n\n"
                "### Recommendations\n"
                "- Keep the useful thing.\n\n"
                "### hmmm\n"
                "- Deferred proof.\n",
                encoding="utf-8",
            )
            out = root / "rec.md"
            out.write_text("seed\n", encoding="utf-8")

            report = recs.build_report(root, generated_at="2026-01-01T00:00:00Z")
            recs.append_report(out, report)

            text = out.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("seed\n"))
            self.assertIn("Org Recommendation Aggregation - 2026-01-01T00:00:00Z", text)
            self.assertIn("- Keep the useful thing.", text)

    def test_aggregate_lists_missing_rec_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "missing" / ".git").mkdir(parents=True)

            report = recs.build_report(root, generated_at="2026-01-01T00:00:00Z")

            self.assertIn("`missing`: `missing/rec.md` not present", report)
            self.assertIn("no `### Recommendations` or `### Remaining` section", report)

    def test_aggregate_uses_remaining_when_latest_block_has_no_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "alpha"
            (repo / ".git").mkdir(parents=True)
            (repo / "rec.md").write_text(
                "## Shallow Audit - fixed\n\n"
                "### Recommendations\n"
                "- Earlier routing.\n\n"
                "## Repair Pass - fixed\n\n"
                "### Applied\n"
                "- Fixed the thing.\n\n"
                "### Remaining\n"
                "- Finish the useful thing.\n\n"
                "### hmmm\n"
                "- Deferred proof.\n",
                encoding="utf-8",
            )

            report = recs.build_report(root, generated_at="2026-01-01T00:00:00Z")

            self.assertIn("- Finish the useful thing.", report)
            self.assertNotIn("- Earlier routing.", report)


class OrgRatioReportTests(unittest.TestCase):
    def test_ratio_metrics_skip_vendored_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "alpha"
            (repo / ".git").mkdir(parents=True)
            (repo / "pkg").mkdir()
            (repo / "pkg" / "module.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            (repo / "rec.md").write_text("generated report\n", encoding="utf-8")
            (repo / ".agents" / "skills" / "x").mkdir(parents=True)
            (repo / ".agents" / "skills" / "x" / "ignored.py").write_text(
                "def ignored():\n    return 2\n",
                encoding="utf-8",
            )

            metric = ratios.scan_repo(repo)

            self.assertEqual(metric.source_files, 1)
            self.assertEqual(metric.ratio_missing_files, 1)

    def test_ratio_dirty_status_ignores_report_files(self) -> None:
        status = "?? rec.md\n M docs.report\n M pkg/module.py\n"

        self.assertEqual(ratios.count_dirty_entries(status), 1)

    def test_ratio_report_lists_low_coverage_oddity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "alpha"
            (repo / ".git").mkdir(parents=True)
            (repo / "one.py").write_text("def one():\n    return 1\n", encoding="utf-8")

            metrics = ratios.collect_metrics(root)
            report = ratios.build_report(metrics, root=root, generated_at="2026-01-01T00:00:00Z")

            self.assertIn("ratio coverage is 0.0%", report)
            self.assertIn("Org Ratio Comparison - 2026-01-01T00:00:00Z", report)


if __name__ == "__main__":
    unittest.main()
# ratios: loc_comments=70:34 imports_exports=7:2 calls_definitions=40:7
