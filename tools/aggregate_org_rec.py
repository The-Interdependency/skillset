#!/usr/bin/env python3
# ratios: loc_comments=162:55 imports_exports=7:11 calls_definitions=66:12
"""Append repo-local recommendations into one org-level ``rec.md``.

Usage guidance:
    python3 tools/aggregate_org_rec.py --root .. --out ../rec.md
    python3 tools/aggregate_org_rec.py --root .. --out ../rec.md --append
    python3 tools/aggregate_org_rec.py --root .. --out ../rec.md --strict

The runner discovers immediate child git checkouts under ``--root``, reads each
repo's ``rec.md``, extracts its latest ``### Recommendations`` section, falls
back to the latest ``### Remaining`` section for repair-pass records, carries
``### hmmm`` forward when present, and emits one timestamped aggregation
section. With ``--append`` it opens the aggregate output in append mode only. It
never edits repo-local ``rec.md`` files and never truncates the aggregate.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# === MODULE_BUILD ===
# id: org_rec_aggregation_runner
#   module_name: aggregate_org_rec
#   module_kind: instrument
#   summary: append repo-local rec.md recommendations into an org-level rec.md section.
#   owner: Codex
#   public_surface: build_report, append_report, command line
#   internal_surface: discover_repos, extract_section, git_value
#   auth_boundary: none
#   storage_boundary: write
#   network_boundary: none
#   user_data_boundary: none
#   admin_only: false
#   tests: tests/test_org_reports.py
#   rollout: manual runner under tools
#   rollback: remove tool and README entry
# === END MODULE_BUILD ===

# === CONTRACTS ===
# id: org_rec_append_only
#   given: append_report is called for an existing aggregate file
#   then: existing bytes remain before the new report and the file is not truncated
#   class: filesystem
#
# id: org_rec_missing_repo_visible
#   given: a discovered git checkout has no rec.md
#   then: the aggregate includes the repository in a visible hmmm/missing list
#   class: evidence
#
# id: org_rec_remaining_fallback
#   given: a repo's latest rec.md block has Remaining but no Recommendations
#   then: the aggregate reports the Remaining bullets as follow-up recommendations
#   class: evidence
# === END CONTRACTS ===

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RepoRec:
    name: str
    path: Path
    branch: str
    commit: str
    rec_path: Path
    recommendations: list[str]
    hmmm: list[str]


def now_utc() -> str:
    """Return an ISO UTC timestamp for report sections."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def git_value(repo: Path, *args: str) -> str:
    """Read one git value; return ``hmmm`` when the checkout cannot answer."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip() or "hmmm"
    except (OSError, subprocess.CalledProcessError):
        return "hmmm"


def discover_repos(root: Path) -> list[Path]:
    """Discover immediate child git checkouts and worktrees under ``root``."""
    root = root.resolve()
    repos = [child for child in root.iterdir() if child.is_dir() and (child / ".git").exists()]
    return sorted(repos, key=lambda path: path.name.lower())


def latest_block(text: str) -> list[str]:
    """Return the last markdown ``##`` block, or all lines if no block exists."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not starts:
        return lines
    return lines[starts[-1] :]


def extract_section(block: Iterable[str], heading: str) -> list[str]:
    """Extract a ``### <heading>`` section from one markdown block."""
    target = f"### {heading}".lower()
    lines = list(block)
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == target:
            start = i + 1
    if start is None:
        return []
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("### "):
            break
        if line.strip():
            out.append(line.rstrip())
    return out


def extract_recommendations(block: Iterable[str]) -> list[str]:
    """Extract recommendations from the latest block, accepting repair-pass wording."""
    lines = list(block)
    return extract_section(lines, "Recommendations") or extract_section(lines, "Remaining")


def read_repo_rec(repo: Path) -> RepoRec:
    """Read one repo's recommendation file into the aggregate shape."""
    rec_path = repo / "rec.md"
    branch = git_value(repo, "rev-parse", "--abbrev-ref", "HEAD")
    commit = git_value(repo, "rev-parse", "HEAD")
    recommendations: list[str] = []
    hmmm: list[str] = []
    if rec_path.is_file():
        block = latest_block(rec_path.read_text(encoding="utf-8", errors="ignore"))
        recommendations = extract_recommendations(block)
        hmmm = extract_section(block, "hmmm")
    return RepoRec(
        name=repo.name,
        path=repo,
        branch=branch,
        commit=commit,
        rec_path=rec_path,
        recommendations=recommendations,
        hmmm=hmmm,
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def build_report(root: Path = DEFAULT_ROOT, generated_at: str | None = None) -> str:
    """Build one aggregate markdown section without writing it."""
    root = root.resolve()
    generated_at = generated_at or now_utc()
    repos = [read_repo_rec(repo) for repo in discover_repos(root)]
    missing = [repo for repo in repos if not repo.rec_path.is_file()]

    lines: list[str] = [
        f"## Org Recommendation Aggregation - {generated_at}",
        "",
        "Usage Guidance:",
        "- Dry run: `python3 tools/aggregate_org_rec.py --root .. --out ../rec.md` from `skill-lib`.",
        "- Append: `python3 tools/aggregate_org_rec.py --root .. --out ../rec.md --append`.",
        "- Repo-local `rec.md` files remain the source reports; this aggregate owns no repo canon.",
        "",
        "### Provenance",
        f"- root: `{root}`",
        f"- repos_discovered: {len(repos)}",
        "- append_policy: output file is opened in append mode only when `--append` is supplied",
        "",
        "### Recommendations By Repo",
    ]

    for repo in repos:
        short = repo.commit[:12] if repo.commit != "hmmm" else "hmmm"
        source = _relative(repo.rec_path, root)
        lines.extend(
            [
                "",
                f"#### {repo.name}",
                f"- source: [{source}]({source})",
                f"- identity: branch `{repo.branch}`, commit `{short}`",
            ]
        )
        if repo.recommendations:
            lines.extend(repo.recommendations)
        else:
            lines.append("- hmmm: no `### Recommendations` or `### Remaining` section was available to aggregate.")
        if repo.hmmm:
            lines.append("- hmmm carried forward:")
            lines.extend(f"  {item}" if item.startswith("- ") else f"  - {item}" for item in repo.hmmm)

    lines.extend(["", "### Missing rec.md"])
    if missing:
        lines.extend(f"- `{repo.name}`: `{_relative(repo.rec_path, root)}` not present" for repo in missing)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "### hmmm",
            "- This aggregate is a derived index. Repository owners retain authority for each local recommendation.",
            "- Deep audit findings require repo-local checks; shallow aggregation must not be mistaken for repair.",
            "",
        ]
    )
    return "\n".join(lines)


def append_report(out: Path, report: str) -> None:
    """Append one report section without truncating existing content."""
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = out.exists() and out.stat().st_size > 0
    with out.open("a", encoding="utf-8") as stream:
        if needs_separator:
            stream.write("\n\n")
        stream.write(report.rstrip())
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Directory containing repo checkouts.")
    parser.add_argument("--out", type=Path, default=None, help="Aggregate rec.md path, default: <root>/rec.md.")
    parser.add_argument("--append", action="store_true", help="Append to --out instead of printing.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any discovered repo lacks rec.md.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    out = args.out.resolve() if args.out else root / "rec.md"
    report = build_report(root)
    if args.append:
        append_report(out, report)
        print(f"appended {out}")
    else:
        print(report)

    missing = [repo for repo in discover_repos(root) if not (repo / "rec.md").is_file()]
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
# ratios: loc_comments=162:55 imports_exports=7:11 calls_definitions=66:12
