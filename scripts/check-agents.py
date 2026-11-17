#!/usr/bin/env python3
"""Check that the two agent files are readable by VS Code and stay in their own lane.

VS Code reads `.github/agents/*.agent.md`, keeps the ones whose frontmatter parses, and silently
drops the rest: a broken key does not raise an error anywhere, the agent simply stops appearing in
the Agent dropdown. That is how this script earns its place - an unquoted `: ` inside a value is
enough (`argument-hint: intent.md [+ files: reports]` is invalid YAML).

It also enforces the separation Carlos asked for: one agent per document. The intent agent reviews
`intent.md` only and never reaches for the spec kit's scripts or ids; the spec agent reviews
`spec.md` only. Anything else means a feature was copied to the wrong file.

Usage:  python3 scripts/check-agents.py [--root DIR]
Exit 0 = both agents can be discovered and each one owns exactly one document.
"""

from __future__ import annotations

import sys
from pathlib import Path

# name prefix -> (document it reviews, markers that belong to the other kit)
LANES = {
    "intent": ("intent.md", ("spec-inputs.py", "selftest-spec-inputs.py", "spec-iteration.py", "SPEC-")),
    "spec": ("spec.md", ("intent-inputs.py", "selftest-inputs.py", "intent-iteration.py", "INT-")),
}
REQUIRED = ("name", "description", "argument-hint", "tools")


def frontmatter(text: str, path: Path) -> str:
    if not text.startswith("---\n"):
        raise SystemExit(f"{path.name}: does not start with a --- line, VS Code will not read it")
    end = text.find("\n---", 4)
    if end < 0:
        raise SystemExit(f"{path.name}: the frontmatter is never closed with ---")
    return text[4:end]


def parse(block: str, path: Path, fails: list[str]) -> dict[str, str]:
    """Parse the frontmatter, or say exactly which line YAML refuses.

    PyYAML is optional: the kit is stdlib only, so the fallback rule is the one that actually
    matters for these files - a plain (unquoted) value may not contain `: `.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    if yaml is not None:
        try:
            loaded = yaml.safe_load(block)
        except Exception as exc:  # noqa: BLE001 - the message is the whole point
            fails.append(f"{path.name}: frontmatter is not valid YAML - {exc}")
            return {}
        return {str(k): "" if v is None else str(v) for k, v in (loaded or {}).items()}

    values: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        quoted = value[:1] in ('"', "'")
        if not quoted and ": " in value:
            fails.append(
                f"{path.name}: `{key.strip()}` has an unquoted `: ` in its value - YAML reads it as a "
                f"nested key and VS Code drops the whole agent. Quote the value."
            )
        values[key.strip()] = value.strip("\"'")
    return values


def main() -> int:
    root = Path(sys.argv[sys.argv.index("--root") + 1]).resolve() if "--root" in sys.argv else Path.cwd()
    agents = sorted((root / ".github" / "agents").glob("*.agent.md"))
    fails: list[str] = []
    checks = 0

    if len(agents) < 2:
        fails.append(f"found {len(agents)} agent file(s) in .github/agents - there must be two")

    for path in agents:
        text = path.read_text(encoding="utf-8")
        data = parse(frontmatter(text, path), path, fails)
        checks += 1
        for key in REQUIRED:
            if not data.get(key):
                fails.append(f"{path.name}: `{key}` is missing or empty - VS Code needs it to list the agent")

        stem = path.name[: -len(".agent.md")]
        if data.get("name") and data["name"] != stem:
            fails.append(f"{path.name}: `name: {data['name']}` does not match the file name `{stem}`")

        prefix = stem.split("_")[0]
        if prefix not in LANES:
            fails.append(f"{path.name}: no lane declared for `{prefix}` - add it to LANES")
            continue
        doc, foreign = LANES[prefix]
        checks += 1
        if doc not in text:
            fails.append(f"{path.name}: never names {doc}, so it cannot be the agent that reviews it")
        for marker in foreign:
            if marker in text:
                fails.append(
                    f"{path.name}: reaches into the other kit with `{marker}` - an agent reviews one document"
                )

    for message in fails:
        print(f"FAIL {message}")
    print(f"{checks} lanes checked, {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
