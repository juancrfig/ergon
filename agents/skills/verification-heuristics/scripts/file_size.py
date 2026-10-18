#!/usr/bin/env python3
"""Fail when an agent-authored file is too large for an agent to read whole.

Size is estimated as tokens = bytes / 4. The default limit is 5,000 tokens (about 20 KB, roughly 450 lines of code).
Why: agents re-open large files in short slices, many times per run; one worker re-opened a 20 KB file 26 times.
Smaller files are read once.

Runs as a gate step, on the working tree: every file git tracks or would track (untracked files that are not
ignored count, because the gate runs before the commit).

Ratchet: a project may list files that were already over the limit, with their current size, in its config
(`--config`, default `.file-size.json` at the root; a project may keep it in its verification guide next to gate.json). A listed file may stay over the limit but may not grow past its recorded size. New files
must be under the limit. Splitting a listed file is its own task; after it, `--update` lowers or removes its entry.

    {"limit": 5000,
     "exclude": ["fixtures/**", "src/components/ui/**"],
     "allow": {"src/cli.py": 19692}}

Files agents do not author are never checked: lockfiles, build output, vendored and generated code, minified files,
binaries, data, READMEs, and anything marked `linguist-generated` or `linguist-vendored` in `.gitattributes`.

Usage:
    file_size.py [--root DIR] [--config FILE] [--init [--headroom N] | --update]

Exit code: 0 green, 1 red. `--init` writes the config with every file currently over the limit at its current size
(run once, when the check is turned on; `--headroom N` adds N tokens to each entry so tasks already planned can
make small fixes in those files; `--update` later lowers entries back to real sizes). `--update` lowers entries to the current sizes of files that shrank and
removes files now under the limit; it never raises an entry and never adds a file.
"""
import argparse, fnmatch, json, subprocess, sys
from pathlib import Path

CONFIG = ".file-size.json"
DEFAULT_LIMIT = 5000
NOT_AUTHORED = [
    # Lockfiles and dependency manifests that tools write.
    "*.lock", "*-lock.json", "*-lock.yaml", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock",
    "poetry.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
    # Build output, dependencies, vendored and generated code.
    "dist/**", "build/**", "out/**", ".next/**", "coverage/**", "node_modules/**", "vendor/**", "third_party/**",
    "**/dist/**", "**/build/**", "**/node_modules/**", "**/vendor/**", "**/__generated__/**", "**/generated/**",
    "*.gen.*", "*_pb2.py", "*.pb.go", "*.min.js", "*.min.css", "*.map", "*.snap",
    # Data and binaries.
    "*.sqlite", "*.sqlite3", "*.db", "*.csv", "*.parquet", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
    "*.ico", "*.svg", "*.woff", "*.woff2", "*.ttf", "*.otf", "*.mp3", "*.mp4", "*.zip", "*.gz", "*.tar",
    # Human-facing documentation: read by people, not re-opened by agents while editing code.
    "README", "README.*",
    CONFIG,
]

SPLIT_HELP = """How to split a file that is too large:
  1. Find the seams: group the file's functions by the area or screen they serve (one module per business area,
     CLI command group, API section or UI section). A group that other groups import is the shared layer.
  2. Create one module per group next to the original (a package with the original name works well:
     cli.py -> cli/__init__.py + cli/sales.py + cli/tables.py ...). Put shared helpers in one common module.
  3. Move code without rewriting it. A section imports only the shared layer, never another section.
  4. Keep the public names working: re-export them from the original module or package, and keep entry points
     (scripts, routes, imports used by tests and deploy config) pointing at the same names.
  5. Each new file must be under the limit. Run the gate again.
A file that was already over the limit before this task may stay that size: do not grow it; add new code in a new
module instead. Splitting it belongs in its own task."""


def files(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    return sorted({f for f in out.split("\0") if f and (root / f).is_file()})


def marked_not_authored(root: Path, paths: list[str]) -> set[str]:
    if not paths:
        return set()
    proc = subprocess.run(["git", "check-attr", "-z", "linguist-generated", "linguist-vendored", "--stdin"],
                          cwd=root, input="\0".join(paths), capture_output=True, text=True)
    parts = proc.stdout.split("\0")
    return {parts[i] for i in range(0, len(parts) - 2, 3) if parts[i + 2] in ("set", "true")}


def matches(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) or
               (p.endswith("/**") and path.startswith(p[:-3] + "/")) for p in patterns)


def is_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\0" in handle.read(8192)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", help=f"config file (default: <root>/{CONFIG})")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--update", action="store_true")
    parser.add_argument("--headroom", type=int, default=0, help="with --init: tokens added to each entry")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    config_path = Path(args.config).resolve() if args.config else root / CONFIG
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    limit = int(config.get("limit", DEFAULT_LIMIT))
    allow: dict[str, int] = {k: int(v) for k, v in config.get("allow", {}).items()}
    exclude = NOT_AUTHORED + list(config.get("exclude", []))

    candidates = [f for f in files(root) if not matches(f, exclude)]
    skip = marked_not_authored(root, candidates)
    sizes = {f: (root / f).stat().st_size // 4 for f in candidates
             if f not in skip and not is_binary(root / f)}
    over = {f: t for f, t in sizes.items() if t > limit}

    if args.init or args.update:
        config["allow"] = ({f: t + args.headroom for f, t in sorted(over.items())} if args.init else
                           {f: min(allow[f], over[f]) for f in sorted(allow) if f in over})
        config.setdefault("limit", limit)
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        print(f"{config_path.name}: {len(config['allow'])} file(s) still over {limit} tokens")
        return 0

    errors = []
    for f, tokens in sorted(over.items()):
        if f not in allow:
            errors.append(f"error: {f} is {tokens} tokens (bytes/4); the limit is {limit}. Split it.")
        elif tokens > allow[f]:
            errors.append(f"error: {f} grew to {tokens} tokens; it was already over the limit ({limit}) and may not "
                          f"grow past {allow[f]}. Move the new code to a new module.")
    shrunk = [f for f in allow if f in over and over[f] < allow[f]] + [f for f in allow if f not in over]
    if errors:
        print("\n".join(errors))
        print()
        print(SPLIT_HELP)
        return 1
    print(f"file size: {len(sizes)} file(s) checked, limit {limit} tokens, {len(over)} allowed over the limit")
    if shrunk:
        print(f"note: {', '.join(sorted(shrunk))} shrank; run file_size.py --update to lower the allowance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
