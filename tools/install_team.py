"""Install the portable game-team skill, keeping three reviewers disabled."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "game-team"
CORE_ROLES = (
    "game-producer", "game-tech-lead", "game-developer", "game-verifier",
    "game-art-lead", "game-asset-artist", "game-ui-artist", "game-vfx-artist",
    "game-systems-designer", "game-balance-designer",
)
PANEL = "game-review-panel"
DISABLED_ROLES = (
    "douyin-male-player-reviewer", "douyin-female-player-reviewer",
    "independent-game-art-reviewer",
)
REVIEW_ROLES = (PANEL,)
ROLES = (*CORE_ROLES, *REVIEW_ROLES)
REQUIRED_SKILL_FILES = (
    Path("SKILL.md"), Path("agents/openai.yaml"),
    Path("references/WORKFLOW.md"), Path("references/ART_WORKFLOW.md"),
    Path("references/DESIGN_WORKFLOW.md"),
)
REFERENCE_FILES = (
    (Path("agents/COMPLETION_REVIEW.md"), Path("references/COMPLETION_REVIEW.md")),
    (Path("agents/independent-reviewers/RESEARCH.md"), Path("references/independent-reviewers/RESEARCH.md")),
    (Path("agents/independent-reviewers/README.md"), Path("references/independent-reviewers/README.md")),
)


def _frontmatter_value(lines, key):
    """Read the two required scalar fields without depending on a YAML package."""
    matches = [(index, match.group(1)) for index, line in enumerate(lines)
               if (match := re.fullmatch(rf"{key}:[ \t]*(.*)", line))]
    if len(matches) != 1:
        raise ValueError(f"SKILL.md frontmatter must contain one {key}")
    index, value = matches[0]
    if value in (">", ">-", ">+", "|", "|-", "|+"):
        continuation = []
        for line in lines[index + 1:]:
            if line and not line[0].isspace():
                break
            continuation.append(line.strip())
        value = " ".join(continuation).strip()
    elif value.startswith('"'):
        value = json.loads(value)
    elif value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError(f"SKILL.md has an invalid quoted {key}")
        value = value[1:-1].replace("''", "'")
    elif value.lower() in ("null", "~", "true", "false"):
        raise ValueError(f"SKILL.md {key} must be a string")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"SKILL.md {key} must be nonempty")
    return value.strip()


def validate_skill(content):
    lines = content.decode("utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError("SKILL.md frontmatter is not closed") from error
    frontmatter = lines[1:end]
    if _frontmatter_value(frontmatter, "name") != SKILL_NAME:
        raise ValueError(f"SKILL.md name must be {SKILL_NAME}")
    _frontmatter_value(frontmatter, "description")


def _read_source(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Required source must be a regular file: {path}")
    content = path.read_bytes()
    if not content.strip():
        raise ValueError(f"Required source is empty: {path}")
    if path.suffix.lower() in (".md", ".yaml", ".yml", ".toml", ".py"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Installed text must be UTF-8: {path}") from error
        if not text.lstrip("\ufeff").strip():
            raise ValueError(f"Required source is empty: {path}")
    return content


def _packaging_artifact(name):
    """Ignore local metadata, backups and common editor scratch files."""
    lower = name.lower()
    return (
        name.startswith(".") or lower == "__pycache__"
        or ".disabled" in lower
        or re.search(r"\.bak(?:\.\d+)?$", lower) is not None
        or lower.endswith((".pyc", ".pyo", ".swp", ".swo", ".swx", ".tmp", ".temp"))
        or name.endswith("~") or name.startswith("~$")
        or (name.startswith("#") and name.endswith("#"))
    )


def _skill_files(directory):
    for source in sorted(directory.iterdir()):
        if _packaging_artifact(source.name):
            continue
        if source.is_symlink():
            raise ValueError(f"Portable skill sources cannot be symlinks: {source}")
        if source.is_dir():
            yield from _skill_files(source)
        elif source.is_file():
            yield source


def validated_sources():
    """Return (source, CODEX_HOME-relative target, bytes), before any writes."""
    skill_root = ROOT / "skills" / SKILL_NAME
    if skill_root.is_symlink() or not skill_root.is_dir():
        raise ValueError(f"Missing regular skill directory: {skill_root}")
    skill_target = Path("skills") / SKILL_NAME
    sources = {}

    def add(source, target, content):
        if target in sources and sources[target][1] != content:
            raise ValueError(f"Conflicting source files for: {target}")
        sources[target] = (source, content)

    for relative in REQUIRED_SKILL_FILES:
        _read_source(skill_root / relative)
    for source in _skill_files(skill_root):
        relative = source.relative_to(skill_root)
        if source.name in {f"{name}.toml" for name in DISABLED_ROLES}:
            continue
        content = _read_source(source)
        if relative == Path("SKILL.md"):
            validate_skill(content)
        if source.suffix.lower() == ".py":
            compile(content, str(source), "exec")
        add(source, skill_target / relative, content)

    for name in ROLES:
        role_directory = ROOT / "agents"
        if name in REVIEW_ROLES:
            role_directory /= "independent-reviewers"
        source = role_directory / f"{name}.toml"
        content = _read_source(source)
        config = tomllib.loads(content.decode("utf-8"))
        if config.get("name") != name or config.get("model") != "gpt-6.1-sol":
            raise ValueError(f"Invalid agent name or model: {source}")
        for field in ("description", "developer_instructions"):
            if not isinstance(config.get(field), str) or not config[field].strip():
                raise ValueError(f"Missing nonempty {field}: {source}")
        add(source, Path("agents") / source.name, content)
        add(source, skill_target / "roles" / source.name, content)
        if name in REVIEW_ROLES:
            # Preserve the review protocol/README's local role-file links.
            add(source, skill_target / "references" / "independent-reviewers" / source.name, content)

    for relative_source, relative_target in REFERENCE_FILES:
        source = ROOT / relative_source
        add(source, skill_target / relative_target, _read_source(source))

    helper = ROOT / "tools" / "review_gate.py"
    content = _read_source(helper)
    compile(content, str(helper), "exec")
    add(helper, skill_target / "scripts" / helper.name, content)
    add(helper, Path("agents") / PANEL / helper.name, content)
    return [(source, target, content) for target, (source, content) in sources.items()]


def backup_path(target):
    candidate = target.with_name(f"{target.name}.bak")
    index = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.bak.{index}")
        index += 1
    return candidate


def disable_reviewers(destination):
    """Archive old native definitions and both portable fallback copies."""
    directories = (
        destination / "agents",
        destination / "skills" / SKILL_NAME / "roles",
        destination / "skills" / SKILL_NAME / "references" / "independent-reviewers",
    )
    for directory in directories:
        for name in DISABLED_ROLES:
            target = directory / f"{name}.toml"
            if not target.exists():
                continue
            archive = target.with_name(f"{target.name}.disabled")
            if archive.exists():
                archive = backup_path(archive)
            target.rename(archive)
            print(f"disabled: {target} -> {archive}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate every source without writing any destination files")
    parser.add_argument(
        "--destination", type=Path,
        help="CODEX_HOME root to install into (default CODEX_HOME or ~/.codex; not its agents subdirectory)",
    )
    args = parser.parse_args(argv)
    try:
        sources = validated_sources()
        if args.check:
            for source, target, _ in sources:
                print(f"valid: {source} -> {target}")
            return 0
        destination = (args.destination or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")).expanduser()
        disable_reviewers(destination)
        for source, relative_target, content in sources:
            target = destination / relative_target
            if target.exists() and target.read_bytes() == content:
                print(f"unchanged: {target}")
                continue
            if target.exists():
                backup = backup_path(target)
                shutil.copy2(target, backup)
                print(f"backup: {backup}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            print(f"installed: {target}")
        return 0
    except (OSError, ValueError, SyntaxError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
