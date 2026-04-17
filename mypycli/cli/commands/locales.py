from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

_DUMP_KW: dict[str, Any] = {
    "allow_unicode": True,
    "sort_keys": False,
    "default_style": '"',
    "width": 2**30,
}


def _library_locales() -> dict[str, dict[str, Any]]:
    """Return {lang: parsed_yaml_root} from bundled mypycli/i18n/locales/."""
    root = files("mypycli.i18n").joinpath("locales")
    result: dict[str, dict[str, Any]] = {}
    for entry in root.iterdir():
        if entry.is_file() and entry.name.endswith(".yml"):
            lang = entry.name[:-4]
            parsed = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
            if isinstance(parsed, dict):
                result[lang] = parsed
    return result


def cmd_init() -> int:
    """Scaffold ./locales/<lang>.yml with bundled mypycli: defaults; skip existing."""
    target = Path.cwd() / "locales"
    target.mkdir(exist_ok=True)

    library = _library_locales()
    if not library:
        print("No bundled locales found in mypycli package.")
        return 1

    for lang, data in sorted(library.items()):
        out = target / f"{lang}.yml"
        if out.exists():
            print(f"skip  locales/{lang}.yml (exists)")
            continue
        mypycli_section: dict[str, Any] = {"mypycli": data.get("mypycli", {})}
        out.write_text(yaml.safe_dump(mypycli_section, **_DUMP_KW), encoding="utf-8")
        print(f"✓ locales/{lang}.yml created")
    return 0


def cmd_sync() -> int:
    """Update the mypycli: section of each ./locales/<lang>.yml; leave user keys intact."""
    target = Path.cwd() / "locales"
    if not target.is_dir():
        print("locales/ directory not found — run 'mypycli locales init' first")
        return 1

    library = _library_locales()
    for file in sorted(target.glob("*.yml")):
        lang = file.stem
        if lang not in library:
            print(f"skip  locales/{lang}.yml (no library counterpart)")
            continue
        current = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        if not isinstance(current, dict):
            current = {}
        current["mypycli"] = library[lang].get("mypycli", {})
        file.write_text(yaml.safe_dump(current, **_DUMP_KW), encoding="utf-8")
        print(f"✓ locales/{lang}.yml: mypycli section updated")
    return 0


def cmd_check() -> int:
    """Validate locales/ for consistency with library and between languages."""
    target = Path.cwd() / "locales"
    if not target.is_dir():
        print("locales/ directory not found")
        return 1

    library = _library_locales()
    user_files = sorted(target.glob("*.yml"))
    if not user_files:
        print("No locale files found in locales/")
        return 1

    has_error = False

    for file in user_files:
        lang = file.stem
        if lang not in library:
            print(f"info  locales/{lang}.yml: no library counterpart, skipping mypycli check")
            continue
        user_data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        if not isinstance(user_data, dict):
            user_data = {}
        user_mypy = _flat_keys(user_data.get("mypycli") or {})
        lib_mypy = _flat_keys(library[lang].get("mypycli") or {})
        if user_mypy != lib_mypy:
            missing = lib_mypy - user_mypy
            extra = user_mypy - lib_mypy
            print(f"✗ locales/{lang}.yml: mypycli section out of sync (run 'mypycli locales sync')")
            if missing:
                print(f"  missing: {sorted(missing)}")
            if extra:
                print(f"  extra:   {sorted(extra)}")
            has_error = True

    per_lang_user: dict[str, set[str]] = {}
    for file in user_files:
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
        user_only = {k: v for k, v in data.items() if k != "mypycli"}
        per_lang_user[file.stem] = _flat_keys(user_only)

    all_keys: set[str] = set().union(*per_lang_user.values()) if per_lang_user else set()
    for lang, keys in per_lang_user.items():
        missing = all_keys - keys
        if missing:
            print(f"✗ locales/{lang}.yml: missing user keys: {sorted(missing)}")
            has_error = True

    if not has_error:
        print("✓ locales consistent")
    return 1 if has_error else 0


def _flat_keys(data: dict[str, Any]) -> set[str]:
    """Return the set of leaf dotted keys present in a nested dict."""
    out: set[str] = set()
    _walk_keys(data, "", out)
    return out


def _walk_keys(node: Any, prefix: str, out: set[str]) -> None:
    if not isinstance(node, dict):
        return
    for k, v in node.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            _walk_keys(v, path, out)
        else:
            out.add(path)
