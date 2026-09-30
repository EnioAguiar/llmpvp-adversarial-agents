#!/usr/bin/env python3
"""Verify the arbiter/clock ports still match LLMPvP's originals.

Usage: python scripts/check_port_parity.py /path/to/llmpvpproject

Compares each ported module against `app/<same name>` in the private repo:
both sides are parsed with `ast`, docstrings are stripped (the ports are
translated to English on purpose), and every top-level function, class and
assignment is compared by name via `ast.dump`. Only the deliberate
`go_arbiter.py` differences (optional pyspiel import, `PYSPIEL_AVAILABLE`,
`_require_pyspiel` and its call from `_load_game`) are allowed; anything
else that differs, or exists on only one side, fails the check.

Exit code 0 = in sync, 1 = drift (or a missing/unparsable file).
"""
import ast
import sys
from pathlib import Path

PORT_DIR = Path(__file__).resolve().parent.parent / "src" / "llmpvp_adversarial"
PORTED_MODULES = ["chess_arbiter.py", "clock.py", "go_arbiter.py"]

# Intentional divergences, keyed by module -> top-level names exempted from
# comparison. `_load_game` is exempt because the port inserts the
# `_require_pyspiel()` guard call; everything else in go_arbiter must match.
ALLOWED_DIFFS = {
    "go_arbiter.py": {"PYSPIEL_AVAILABLE", "_require_pyspiel", "_load_game"},
}
# Module-level import statements are compared only for modules absent here.
ALLOW_IMPORT_DIFF = {"go_arbiter.py"}


def _strip_docstrings(module: ast.Module) -> ast.Module:
    for sub in ast.walk(module):
        if not isinstance(
            sub, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = sub.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            sub.body = body[1:] or [ast.Pass()]
    return module


def _top_level(path: Path) -> tuple[dict[str, str], list[str]]:
    """Returns ({name: ast.dump(node)}, [dumped import statements])."""
    tree = _strip_docstrings(ast.parse(path.read_text(encoding="utf-8")))
    named: dict[str, str] = {}
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.dump(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            named[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    named[target.id] = ast.dump(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            named[node.target.id] = ast.dump(node)
        elif isinstance(node, ast.Try):
            # Optional-import guard: record the names it binds so the
            # allowlist can exempt them explicitly.
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    imports.append(ast.dump(sub))
                elif isinstance(sub, ast.Assign):
                    for target in sub.targets:
                        if isinstance(target, ast.Name):
                            named[target.id] = ast.dump(sub)
    return named, imports


def check_module(module: str, original_dir: Path) -> list[str]:
    port_path = PORT_DIR / module
    orig_path = original_dir / "app" / module
    for path in (port_path, orig_path):
        if not path.is_file():
            return [f"{module}: missing file {path}"]

    port_named, port_imports = _top_level(port_path)
    orig_named, orig_imports = _top_level(orig_path)
    allowed = ALLOWED_DIFFS.get(module, set())
    problems = []

    for name in sorted(set(port_named) - set(orig_named) - allowed):
        problems.append(f"{module}: `{name}` exists only in the port")
    for name in sorted(set(orig_named) - set(port_named) - allowed):
        problems.append(f"{module}: `{name}` exists only in the original")
    for name in sorted(set(port_named) & set(orig_named) - allowed):
        if port_named[name] != orig_named[name]:
            problems.append(f"{module}: `{name}` differs between port and original")

    if module not in ALLOW_IMPORT_DIFF and sorted(port_imports) != sorted(orig_imports):
        problems.append(f"{module}: module-level imports differ")

    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} /path/to/llmpvpproject", file=sys.stderr)
        return 1
    original_dir = Path(argv[1]).expanduser().resolve()
    if not (original_dir / "app").is_dir():
        print(f"not an llmpvpproject checkout (no app/): {original_dir}", file=sys.stderr)
        return 1

    problems = []
    for module in PORTED_MODULES:
        problems.extend(check_module(module, original_dir))

    if problems:
        print(f"PORT PARITY FAILED ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        print("\nSync the port with the original, or extend ALLOWED_DIFFS if the")
        print("divergence is intentional and documented in the README.")
        return 1

    print(f"OK: {', '.join(PORTED_MODULES)} match {original_dir}/app (modulo docstrings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
