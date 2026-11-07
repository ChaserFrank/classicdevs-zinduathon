"""Read dependency names out of manifest files. Pure: text in, package names out.

Parsing is forgiving: a malformed manifest yields no dependencies rather than failing the analysis.
"""

import json
import re
import tomllib

# Python 3.12 links expat ≥ 2.4.1, which refuses entity-expansion ("billion laughs") attacks.
import xml.etree.ElementTree as ET

MANIFEST_FILES = {
    "package.json": "npm",
    "requirements.txt": "pypi",
    "pyproject.toml": "pypi",
    "go.mod": "go",
    "pom.xml": "maven",
}

_PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalise_package(ecosystem: str, name: str) -> str:
    name = (name or "").strip().lower()
    if ecosystem == "pypi":
        return re.sub(r"[-_.]+", "-", name)  # PEP 503
    return name


def _python_requirement(line: str) -> str | None:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "git+", "http")):
        return None
    match = _PEP508_NAME.match(line)
    return match.group(1) if match else None


def parse_package_json(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return set()
    if not isinstance(data, dict):
        return set()
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.update(section)
    return names


def parse_requirements(text: str) -> set[str]:
    return {name for line in text.splitlines() if (name := _python_requirement(line))}


def parse_pyproject(text: str) -> set[str]:
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError):
        return set()
    names: set[str] = set()
    project = data.get("project", {})
    for dep in project.get("dependencies", []) or []:
        if name := _python_requirement(str(dep)):
            names.add(name)
    for group in (project.get("optional-dependencies") or {}).values():
        for dep in group or []:
            if name := _python_requirement(str(dep)):
                names.add(name)
    for group in (data.get("dependency-groups") or {}).values():
        for dep in group or []:
            if isinstance(dep, str) and (name := _python_requirement(dep)):
                names.add(name)
    poetry = data.get("tool", {}).get("poetry", {})
    names.update(k for k in (poetry.get("dependencies") or {}) if k.lower() != "python")
    for group in (poetry.get("group") or {}).values():
        names.update((group or {}).get("dependencies", {}) or {})
    names.update(poetry.get("dev-dependencies") or {})
    return names


def parse_go_mod(text: str) -> set[str]:
    names: set[str] = set()
    in_block = False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line[len("require ") :].strip()
        elif not in_block:
            continue
        parts = line.split()
        if parts:
            names.add(parts[0])
    return names


def parse_pom(text: str) -> set[str]:
    try:
        root = ET.fromstring(text)  # noqa: S314 - see import note
    except ET.ParseError:
        return set()
    return {
        el.text.strip()
        for el in root.iter()
        if el.tag.rsplit("}", 1)[-1] == "artifactId" and el.text and el.text.strip()
    }


_PARSERS = {
    "package.json": parse_package_json,
    "requirements.txt": parse_requirements,
    "pyproject.toml": parse_pyproject,
    "go.mod": parse_go_mod,
    "pom.xml": parse_pom,
}


def dependencies(manifests: dict[str, str]) -> dict[str, set[str]]:
    """{"package.json": "..."} → {"npm": {"react", ...}} with normalised names."""
    out: dict[str, set[str]] = {}
    for filename, text in manifests.items():
        base = filename.rsplit("/", 1)[-1]
        parser = _PARSERS.get(base)
        if parser is None:
            continue
        ecosystem = MANIFEST_FILES[base]
        names = {normalise_package(ecosystem, n) for n in parser(text or "")}
        out.setdefault(ecosystem, set()).update(n for n in names if n)
    return out
