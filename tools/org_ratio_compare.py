#!/usr/bin/env python3
# ratios: loc_comments=328:51 imports_exports=10:12 calls_definitions=109:14
"""Collect shallow repo scalars/vectors and append ``docs.report`` oddities.

Usage guidance:
    python3 tools/org_ratio_compare.py --root ..
    python3 tools/org_ratio_compare.py --root .. --out ../docs.report --append
    python3 tools/org_ratio_compare.py --root .. --json

The runner walks immediate child git checkouts under ``--root`` and reports
composition metrics useful for deciding where to scan deeply next. It skips
vendored agent skills, dependency folders, build outputs, and caches by default.
Large text files are counted by bytes but not fully line-counted beyond the
configured byte ceiling; those become visible ``hmmm`` oddities rather than
quietly consuming unbounded local resources.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

# === MODULE_BUILD ===
# id: org_ratio_comparison_runner
#   module_name: org_ratio_compare
#   module_kind: instrument
#   summary: collect org-wide scalar and vector repo metrics and append docs.report oddities.
#   owner: Codex
#   public_surface: collect_metrics, build_report, append_report, command line
#   internal_surface: scan_repo, oddities, line_count
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
# id: org_ratio_skips_vendored_skills
#   given: a repo contains product source and .agents/skills source
#   then: scalar/vector metrics exclude the vendored .agents tree
#   class: evidence
#
# id: org_ratio_oddities_visible
#   given: a repo has low ratio coverage or dirty state
#   then: build_report lists a human-readable oddity for that repo
#   class: evidence
# === END CONTRACTS ===

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh", ".rs", ".go"}
DOC_EXTS = {".md", ".rst", ".txt"}
SKIP_DIRS = {
    ".git",
    ".agents",
    ".cache",
    ".mypy_cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".turbo",
    ".venv",
    "__pycache__",
    "attached_assets",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "target",
    "venv",
}
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock")
COMPACT_RATIO_RE = re.compile(r"^(#|//)\s*\d+:\d+\s+\d+:\d+\s+\d+:\d+\s*$")
REPORT_NAMES = {"rec.md", "docs.report"}


@dataclass
class RepoMetrics:
    repo: str
    path: str
    branch: str
    commit: str
    remote: str
    dirty_entries: int
    file_count: int
    bytes_total: int
    source_files: int
    source_lines_counted: int
    doc_lines_counted: int
    large_text_skipped: int
    unread_source_files: int
    ratio_portable_files: int
    ratio_compact_files: int
    ratio_missing_files: int
    skill_count: int
    workflow_count: int
    has_agents: bool
    has_claude: bool
    has_llms: bool
    has_collection: bool
    has_tests: bool
    has_pyproject: bool
    has_package: bool
    has_lock: bool
    top_ext: list[tuple[str, int]]

    @property
    def ratio_coverage(self) -> float | None:
        if self.source_files == 0:
            return None
        return round((self.ratio_portable_files + self.ratio_compact_files) / self.source_files, 3)

    @property
    def doc_to_source(self) -> float | None:
        if self.source_lines_counted == 0:
            return None
        return round(self.doc_lines_counted / self.source_lines_counted, 3)


def now_utc() -> str:
    """Return an ISO UTC timestamp for report sections."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def git_value(repo: Path, *args: str) -> str:
    """Read one git value; return ``hmmm`` when unavailable."""
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


def line_count(path: Path, max_text_bytes: int) -> tuple[int, bool]:
    """Count lines for reasonably sized text files; report large-file skips."""
    try:
        if path.stat().st_size > max_text_bytes:
            return 0, True
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines()), False
    except OSError:
        return 0, True


def scan_repo(repo: Path, max_text_bytes: int = 5_000_000) -> RepoMetrics:
    """Collect shallow scalar/vector metrics for one repo checkout."""
    files: list[Path] = []
    ext_counts: dict[str, int] = {}
    bytes_total = 0
    source_files = 0
    source_lines = 0
    doc_lines = 0
    large_text_skipped = 0
    unread_source_files = 0
    ratio_portable = 0
    ratio_compact = 0
    ratio_missing = 0

    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.relative_to(repo).as_posix() in REPORT_NAMES:
                continue
            files.append(path)
            ext = path.suffix.lower() or "<none>"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            try:
                bytes_total += path.stat().st_size
            except OSError:
                pass

            if path.suffix.lower() in SOURCE_EXTS:
                source_files += 1
                count, skipped = line_count(path, max_text_bytes)
                source_lines += count
                unread_source_files += int(skipped)
                if skipped:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                lines = text.splitlines()
                first = lines[0].strip() if lines else ""
                last = next((line.strip() for line in reversed(lines) if line.strip()), "")
                has_portable = "ratios:" in first and "ratios:" in last
                has_compact = bool(COMPACT_RATIO_RE.match(first)) and bool(COMPACT_RATIO_RE.match(last))
                ratio_portable += int(has_portable)
                ratio_compact += int(has_compact)
                ratio_missing += int(not (has_portable or has_compact))
            elif path.suffix.lower() in DOC_EXTS:
                count, skipped = line_count(path, max_text_bytes)
                doc_lines += count
                large_text_skipped += int(skipped)

    status = git_value(repo, "status", "--porcelain=v1")
    skills_dir = repo / ".agents" / "skills"
    skill_count = 0
    if skills_dir.is_dir():
        skill_count = sum(1 for child in skills_dir.iterdir() if child.is_dir() and (child / "SKILL.md").is_file())
    workflows = repo / ".github" / "workflows"
    workflow_count = 0
    if workflows.is_dir():
        workflow_count = len(list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml")))

    return RepoMetrics(
        repo=repo.name,
        path=str(repo),
        branch=git_value(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        commit=git_value(repo, "rev-parse", "HEAD"),
        remote=git_value(repo, "remote", "get-url", "origin"),
        dirty_entries=count_dirty_entries(status),
        file_count=len(files),
        bytes_total=bytes_total,
        source_files=source_files,
        source_lines_counted=source_lines,
        doc_lines_counted=doc_lines,
        large_text_skipped=large_text_skipped,
        unread_source_files=unread_source_files,
        ratio_portable_files=ratio_portable,
        ratio_compact_files=ratio_compact,
        ratio_missing_files=ratio_missing,
        skill_count=skill_count,
        workflow_count=workflow_count,
        has_agents=(repo / "AGENTS.md").is_file(),
        has_claude=(repo / "CLAUDE.md").is_file(),
        has_llms=(repo / "llms.txt").is_file(),
        has_collection=any(repo.glob("*_msdmd.ts")),
        has_tests=(repo / "tests").exists() or (repo / "test").exists(),
        has_pyproject=(repo / "pyproject.toml").is_file(),
        has_package=(repo / "package.json").is_file(),
        has_lock=any((repo / name).is_file() for name in LOCKFILES),
        top_ext=sorted(ext_counts.items(), key=lambda item: item[1], reverse=True)[:8],
    )


def count_dirty_entries(status: str) -> int:
    """Count dirty status entries while ignoring generated report files."""
    if status == "hmmm":
        return 0
    count = 0
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in REPORT_NAMES:
            count += 1
    return count


def collect_metrics(root: Path = DEFAULT_ROOT, max_text_bytes: int = 5_000_000) -> list[RepoMetrics]:
    """Collect metrics for every immediate child git checkout under ``root``."""
    return [scan_repo(repo, max_text_bytes=max_text_bytes) for repo in discover_repos(root)]


def oddities(metrics: list[RepoMetrics]) -> list[str]:
    """Generate visible oddities from scalar/vector comparisons."""
    out: list[str] = []
    byte_median = median([item.bytes_total for item in metrics]) if metrics else 0
    remote_groups: dict[str, list[str]] = {}
    for item in metrics:
        if item.remote != "hmmm":
            remote_groups.setdefault(item.remote, []).append(item.repo)

    for remote, repos in sorted(remote_groups.items()):
        if len(repos) > 1:
            out.append(f"`{', '.join(sorted(repos))}` share remote `{remote}`; preserve branch/commit identity before merging conclusions.")

    for item in metrics:
        coverage = item.ratio_coverage
        if item.dirty_entries:
            out.append(f"`{item.repo}` has {item.dirty_entries} dirty git status entries.")
        if coverage is not None and coverage < 0.5 and item.source_files:
            out.append(f"`{item.repo}` ratio coverage is {coverage:.1%} ({item.ratio_missing_files}/{item.source_files} source files missing a seal).")
        if not item.has_collection:
            out.append(f"`{item.repo}` has no root `*_msdmd.ts` collection point.")
        if item.source_files > 20 and not item.has_tests:
            out.append(f"`{item.repo}` has {item.source_files} source files and no top-level `tests/` or `test/` directory.")
        if item.source_files > 50 and not (item.has_pyproject or item.has_package):
            out.append(f"`{item.repo}` has {item.source_files} source files but no root `pyproject.toml` or `package.json`.")
        if item.has_lock and not (item.has_pyproject or item.has_package):
            out.append(f"`{item.repo}` has a lockfile but no root package manifest detected.")
        if byte_median and item.bytes_total > byte_median * 5:
            out.append(f"`{item.repo}` is more than 5x median checkout bytes; artifact-aware scan exclusions matter.")
        if item.large_text_skipped or item.unread_source_files:
            out.append(f"`{item.repo}` skipped {item.large_text_skipped} large docs and {item.unread_source_files} large source files for line counting.")
    return out


def build_report(metrics: list[RepoMetrics], root: Path = DEFAULT_ROOT, generated_at: str | None = None) -> str:
    """Build one markdown docs.report section without writing it."""
    generated_at = generated_at or now_utc()
    root = root.resolve()
    lines: list[str] = [
        f"## Org Ratio Comparison - {generated_at}",
        "",
        "Usage Guidance:",
        "- Dry run: `python3 tools/org_ratio_compare.py --root ..` from `skill-lib`.",
        "- Append: `python3 tools/org_ratio_compare.py --root .. --out ../docs.report --append`.",
        "- Treat oddities as routing signals for the next audit pass, not as proof of defects.",
        "",
        "### Provenance",
        f"- root: `{root}`",
        f"- repos_discovered: {len(metrics)}",
        "- scan_depth: immediate git checkouts; vendored `.agents` and generated/dependency directories skipped",
        "",
        "### Scalars",
        "| repo | src files | src lines | doc lines | doc/src | ratio coverage | missing seals | skills | workflows | dirty |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in metrics:
        coverage = "hmmm" if item.ratio_coverage is None else f"{item.ratio_coverage:.1%}"
        doc_source = "hmmm" if item.doc_to_source is None else f"{item.doc_to_source:.3f}"
        lines.append(
            f"| `{item.repo}` | {item.source_files} | {item.source_lines_counted} | "
            f"{item.doc_lines_counted} | {doc_source} | {coverage} | "
            f"{item.ratio_missing_files} | {item.skill_count} | {item.workflow_count} | {item.dirty_entries} |"
        )

    lines.extend(
        [
            "",
            "### Vectors",
            "| repo | branch@commit | ratio forms | top extensions | surfaces |",
            "|---|---|---|---|---|",
        ]
    )
    for item in metrics:
        short = item.commit[:12] if item.commit != "hmmm" else "hmmm"
        ratio_forms = f"portable={item.ratio_portable_files}; compact={item.ratio_compact_files}; missing={item.ratio_missing_files}"
        top_ext = ", ".join(f"{ext}:{count}" for ext, count in item.top_ext) or "hmmm"
        surfaces = ", ".join(
            name
            for name, present in (
                ("AGENTS", item.has_agents),
                ("CLAUDE", item.has_claude),
                ("llms", item.has_llms),
                ("collection", item.has_collection),
                ("tests", item.has_tests),
                ("pyproject", item.has_pyproject),
                ("package", item.has_package),
            )
            if present
        ) or "hmmm"
        lines.append(
            f"| `{item.repo}` | `{item.branch}@{short}` | {ratio_forms} | {top_ext} | {surfaces} |"
        )

    lines.extend(["", "### Oddities"])
    found = oddities(metrics)
    lines.extend(f"- {item}" for item in found) if found else lines.append("- none")
    lines.extend(
        [
            "",
            "### hmmm",
            "- Ratio coverage excludes vendored `.agents` by design; canonical skill drift is checked separately.",
            "- Lexical deprecated/superseded hits require targeted semantic review before removal, because snapshots, tests, and lockfiles may preserve history intentionally.",
            "- This runner selects the next deep scan; it does not certify release, deployment, accessibility, security, or theorem status.",
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
    parser.add_argument("--out", type=Path, default=None, help="docs.report path, default: <root>/docs.report.")
    parser.add_argument("--max-text-bytes", type=int, default=5_000_000, help="Per-file line-count byte ceiling.")
    parser.add_argument("--append", action="store_true", help="Append to --out instead of printing.")
    parser.add_argument("--json", action="store_true", help="Emit collected metrics as JSON.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    metrics = collect_metrics(root, max_text_bytes=args.max_text_bytes)
    if args.json:
        print(json.dumps([asdict(item) | {"ratio_coverage": item.ratio_coverage, "doc_to_source": item.doc_to_source} for item in metrics], indent=2, sort_keys=True))
        return 0

    report = build_report(metrics, root=root)
    if args.append:
        out = args.out.resolve() if args.out else root / "docs.report"
        append_report(out, report)
        print(f"appended {out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ratios: loc_comments=328:51 imports_exports=10:12 calls_definitions=109:14
