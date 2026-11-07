"""Export the API contract to ``contracts/openapi.yaml``, or check it is up to date.

The spec is generated from the FastAPI app (and so from the pydantic models) and written
deterministically: keys sorted, block style, UTF-8, LF line endings. The frontend team
builds against the committed file, so any change to it needs a ``contracts/CHANGELOG.md``
entry.

Usage (from ``backend/``)::

    uv run python scripts/export_openapi.py          # (re)write contracts/openapi.yaml
    uv run python scripts/export_openapi.py --check  # re-export to a temp file, diff, validate
"""

from __future__ import annotations

import argparse
import difflib
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from openapi_schema_validator import OAS31Validator
from openapi_spec_validator import validate

from haven.api.app import create_app

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
SPEC_PATH = CONTRACTS_DIR / "openapi.yaml"


def build_spec() -> dict[str, Any]:
    return create_app().openapi()


def render(spec: dict[str, Any]) -> str:
    return yaml.safe_dump(
        spec, sort_keys=True, allow_unicode=True, default_flow_style=False, width=100
    )


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _media_objects(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(location, media object) for every request/response body in the spec."""
    found: list[tuple[str, dict[str, Any]]] = []
    for path, item in spec.get("paths", {}).items():
        for method, op in item.items():
            where = f"{method.upper()} {path}"
            body = op.get("requestBody", {}).get("content", {})
            found += [(f"{where} request {mt}", media) for mt, media in body.items()]
            for code, response in op.get("responses", {}).items():
                content = response.get("content", {})
                found += [(f"{where} {code} {mt}", media) for mt, media in content.items()]
    return found


def example_errors(spec: dict[str, Any]) -> list[str]:
    """Every embedded example must validate against its media schema."""
    errors: list[str] = []
    components = spec.get("components", {})
    for where, media in _media_objects(spec):
        schema = media.get("schema")
        if schema is None:
            continue
        validator = OAS31Validator({**schema, "components": components})
        for name, example in media.get("examples", {}).items():
            for err in validator.iter_errors(example.get("value")):
                loc = "/".join(str(p) for p in err.absolute_path)
                errors.append(f"{where} example {name!r} at /{loc}: {err.message}")
    return errors


def check() -> int:
    if not SPEC_PATH.exists():
        print(f"missing {SPEC_PATH}; run scripts/export_openapi.py", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "openapi.yaml"
        write(fresh_path, render(build_spec()))
        fresh = fresh_path.read_text(encoding="utf-8")
    committed = SPEC_PATH.read_text(encoding="utf-8")
    if fresh != committed:
        diff = difflib.unified_diff(
            committed.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            fromfile="contracts/openapi.yaml (committed)",
            tofile="contracts/openapi.yaml (re-exported)",
        )
        sys.stderr.writelines(diff)
        print(
            "\ncontracts/openapi.yaml is stale: run `poe export-openapi` and add a "
            "contracts/CHANGELOG.md entry.",
            file=sys.stderr,
        )
        return 1

    spec = yaml.safe_load(committed)
    validate(spec)
    errors = example_errors(spec)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{SPEC_PATH.name} is up to date, valid OpenAPI {spec['openapi']}, examples valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail if the file is stale/invalid")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    spec = build_spec()
    validate(spec)
    write(SPEC_PATH, render(spec))
    print(f"wrote {SPEC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
