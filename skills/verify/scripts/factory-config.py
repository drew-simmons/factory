#!/usr/bin/env python3
"""Print factory.toml values as KEY=value lines for shell scripts.

Usage: python3 -I factory-config.py [path/to/factory.toml]

Missing file or missing keys print the defaults. Values are shell-quoted
with single quotes so `eval` is safe for any value a TOML string can hold.
A file that cannot be read (Python older than 3.11, or invalid TOML) exits 2
with a message on stderr and prints nothing, so a caller never evals a
half-read configuration.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    tomllib = None

DEFAULTS = {
    "FACTORY_SPEC_DIR": "docs/specs",
    "FACTORY_BASE": "origin/main",
    "VERIFY_THRESHOLD": "5",
    "VERIFY_COVERAGE": "",
    "VERIFY_LLM": "0",
    "VERIFY_MAX_REQUESTS": "50",
    "VERIFY_MAX_ITERATIONS": "5",
    "VERIFY_EXCLUDE": "",
    "VERIFY_CMD_TYPECHECK": "",
    "VERIFY_CMD_LINT": "",
    "VERIFY_CMD_FORMAT": "",
    "VERIFY_CMD_TEST": "",
}

KEYS = {
    "FACTORY_SPEC_DIR": ("factory", "spec_dir"),
    "FACTORY_BASE": ("factory", "base"),
    "VERIFY_THRESHOLD": ("verify", "crap_threshold"),
    "VERIFY_COVERAGE": ("verify", "coverage"),
    "VERIFY_LLM": ("verify", "llm"),
    "VERIFY_MAX_REQUESTS": ("verify", "max_requests"),
    "VERIFY_MAX_ITERATIONS": ("verify", "max_iterations"),
    "VERIFY_EXCLUDE": ("verify", "exclude"),
    "VERIFY_CMD_TYPECHECK": ("verify", "commands", "typecheck"),
    "VERIFY_CMD_LINT": ("verify", "commands", "lint"),
    "VERIFY_CMD_FORMAT": ("verify", "commands", "format"),
    "VERIFY_CMD_TEST": ("verify", "commands", "test"),
}


def lookup(data: dict, path: tuple[str, ...]):
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def render(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


class ConfigError(Exception):
    """The file exists but cannot be read."""


def load(path: Path) -> dict:
    if not path.is_file():
        return {}
    if tomllib is None:
        raise ConfigError(f"{path} needs Python 3.11 or newer to be read (tomllib)")
    with path.open("rb") as handle:
        try:
            return tomllib.load(handle)
        except tomllib.TOMLDecodeError as err:
            raise ConfigError(f"{path} is not valid TOML: {err}") from err


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("factory.toml")
    try:
        data = load(path)
    except ConfigError as err:
        print(f"factory-config: {err}", file=sys.stderr)
        return 2
    for name, default in DEFAULTS.items():
        value = lookup(data, KEYS[name])
        text = default if value is None or value == "" else render(value)
        print(f"{name}={shlex.quote(text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
