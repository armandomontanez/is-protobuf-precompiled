#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from datetime import timezone, datetime
from pathlib import Path

LANGUAGES = {
    "cc": {"display": "C++", "rules_dep": "rules_cc"},
    "java": {"display": "Java", "rules_dep": "rules_java"},
    "python": {"display": "Python", "rules_dep": "rules_python"},
}


def get_versions(repo_root):
    module_content = (repo_root / "MODULE.bazel").read_text()
    versions = {}
    for match in re.finditer(
        r'bazel_dep\(name\s*=\s*"([^"]+)",\s*version\s*=\s*"([^"]+)"\)', module_content
    ):
        versions[match.group(1)] = match.group(2)
    versions["bazel"] = (repo_root / ".bazelversion").read_text().strip()
    return versions


def check_language(repo_root, lang):
    target = f"//{lang}:hello_proto"
    source_target = "@protobuf//src/google/protobuf"
    query = f'somepath("{target}", "{source_target}")'

    result = subprocess.run(
        ["bazel", "cquery", query],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    if result.returncode != 0:
        return "precompiled"

    stdout = result.stdout.strip()
    if not stdout:
        return "precompiled"

    if "//" in stdout or "@" in stdout:
        return "source"

    return "precompiled"


def load_status(repo_root):
    status_file = repo_root / "status.json"
    if status_file.exists():
        return json.loads(status_file.read_text())
    return {"languages": {}}


def update_status(status, results, versions):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for lang, result in results.items():
        if lang not in status["languages"]:
            status["languages"][lang] = {
                "current_status": None,
                "first_precompiled_date": None,
                "first_precompiled_versions": None,
                "regression_date": None,
                "regression_versions": None,
            }

        entry = status["languages"][lang]
        prev_status = entry["current_status"]
        entry["current_status"] = result

        if result == "precompiled" and prev_status != "precompiled":
            entry["first_precompiled_date"] = today
            entry["first_precompiled_versions"] = versions.copy()
            entry["regression_date"] = None
            entry["regression_versions"] = None
        elif result == "source" and prev_status == "precompiled":
            entry["regression_date"] = today
            entry["regression_versions"] = versions.copy()

    status["last_updated"] = today
    status["current_versions"] = versions
    return status


def update_readme(repo_root, status):
    readme_file = repo_root / "README.md"
    lines = []
    lines.append("| Language | Precompiled | First precompiled | Versions |")
    lines.append("|----------|-------------|-------------------|----------|")

    for lang, info in LANGUAGES.items():
        entry = status["languages"].get(lang, {})
        current = entry.get("current_status", "unknown")

        if current == "precompiled":
            status_str = ":white_check_mark:"
        else:
            status_str = ":x:"

        first_date = entry.get("first_precompiled_date") or "-"
        versions = entry.get("first_precompiled_versions")
        if versions:
            parts = [
                f"protobuf {versions.get('protobuf', '?')}",
                f"{info['rules_dep']} {versions.get(info['rules_dep'], '?')}",
                f"Bazel {versions.get('bazel', '?')}",
            ]
            ver_str = ", ".join(parts)
        else:
            ver_str = "-"

        lines.append(f"| {info['display']} | {status_str} | {first_date} | {ver_str} |")

    table = "\n".join(lines)
    new_section = f"## Status\n\n{table}\n\n_Last updated: {status['last_updated']}_\n"

    readme = readme_file.read_text()
    readme = re.sub(r"## Status.*?(?=\n## |\Z)", new_section, readme, flags=re.DOTALL)
    readme_file.write_text(readme)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default=".",
        help="path to the repository root (default: cwd)",
    )
    args = parser.parse_args()
    repo_root = Path(args.project_root).resolve()

    versions = get_versions(repo_root)
    print(f"Versions: {versions}")

    results = {}
    for lang in LANGUAGES:
        print(f"Checking {lang}...", end=" ")
        results[lang] = check_language(repo_root, lang)
        print(results[lang])

    status = load_status(repo_root)
    status = update_status(status, results, versions)

    status_file = repo_root / "status.json"
    status_file.write_text(json.dumps(status, indent=2) + "\n")
    print(f"Updated {status_file}")

    update_readme(repo_root, status)
    print(f"Updated {repo_root / 'README.md'}")


if __name__ == "__main__":
    main()
