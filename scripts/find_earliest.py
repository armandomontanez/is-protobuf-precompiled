#!/usr/bin/env python3
"""Find the earliest version combination where a language's proto target is precompiled.

Strategy: set all deps to lowest version, then iterate in a triple nested loop
(bazel -> protobuf -> rules_<lang>) from lowest to highest, stopping at the first
combination where the cquery finds no dependency path to protobuf source.
"""

import argparse
import json
import subprocess
import os
import re
import sys
from pathlib import Path

LANGUAGES = {
    "cc": "rules_cc",
    "java": "rules_java",
    "python": "rules_python",
}

BAZEL_VERSIONS = ["9.0.0", "9.1.0", "9.2.0"]


def load_bcr_versions(bcr_path, module_name):
    metadata_file = bcr_path / "modules" / module_name / "metadata.json"
    metadata = json.loads(metadata_file.read_text())
    yanked = set(metadata.get("yanked_versions", {}).keys())
    versions = [v for v in metadata["versions"] if v not in yanked]
    return versions


def filter_prereleases(versions):
    """Remove pre-release (rc) and bcr-patched versions."""
    return [v for v in versions if "rc" not in v and "bcr" not in v]


def set_versions(module_file, bazelversion_file, protobuf_ver, rules_dep, rules_ver, bazel_ver):
    module = f'''module(name = "is-protobuf-precompiled", version = "0.1.0")

bazel_dep(name = "protobuf", version = "{protobuf_ver}")
bazel_dep(name = "{rules_dep}", version = "{rules_ver}")
'''
    module_file.write_text(module)
    bazelversion_file.write_text(bazel_ver + "\n")


def run_cquery(repo_root, lang):
    target = f"//{lang}:hello_proto"
    source_target = "@protobuf//src/google/protobuf"
    query = f'somepath("{target}", "{source_target}")'

    result = subprocess.run(
        ["bazelisk", "cquery", query, "--check_direct_dependencies=error"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=300,
    )
    return result


def check_precompiled(repo_root, lang):
    result = run_cquery(repo_root, lang)
    if result.returncode != 0:
        return "error"

    stdout = result.stdout.strip()
    if not stdout:
        return "precompiled"
    if "//" in stdout or "@" in stdout:
        return "source"
    return "precompiled"


import re

_DEP_CHECK_RE = re.compile(
    r"requires module version (\S+)@(\S+), but got \S+@(\S+)"
)


def probe_minimum_versions(repo_root, lang, protobuf_versions, rules_dep, rules_versions):
    """Run a probe with the lowest versions and parse the minimum resolved versions.

    Returns a (protobuf_version, rules_version) tuple of the minimums that Bazel
    will accept, or None if the probe didn't produce dependency check errors.
    """
    result = run_cquery(repo_root, lang)
    assert result.returncode != 0, "Can't probe minimum version; the build passed unexpectedly"

    stderr = result.stderr
    minimums = {}
    for match in _DEP_CHECK_RE.finditer(stderr):
        module_name = match.group(1)
        resolved_ver = match.group(3)
        minimums[module_name] = resolved_ver

    assert minimums, "Failed to parse minimum versions from Bazel output"

    min_protobuf = minimums.get("protobuf", protobuf_versions[0])
    min_rules = minimums.get(rules_dep, rules_versions[0])
    return (min_protobuf, min_rules)


def main():
    if "BUILD_WORKING_DIRECTORY" in os.environ:
        os.chdir(os.environ["BUILD_WORKING_DIRECTORY"])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=LANGUAGES.keys(),
                        help="language to check (cc, java, python)")
    parser.add_argument("--bcr", required=True, type=Path,
                        help="path to local bazel-central-registry checkout")
    parser.add_argument("--project-root", default=".", type=Path,
                        help="path to the repository root (default: cwd)")
    parser.add_argument("--no-restore", action="store_true",
                        help="don't restore MODULE.bazel after finishing")
    parser.add_argument("--allow-prereleases", action="store_true",
                        help="allow prereleases when checking versions")
    args = parser.parse_args()

    repo_root = args.project_root.resolve()
    bcr_path = args.bcr.resolve()
    lang = args.language
    rules_dep = LANGUAGES[lang]

    module_file = repo_root / "MODULE.bazel"
    bazelversion_file = repo_root / ".bazelversion"
    module_lockfile = repo_root / "MODULE.bazel.lock"
    original_module = module_file.read_text()
    original_modulelock = module_lockfile.read_text()
    original_bazelversion = bazelversion_file.read_text()

    def restore():
        module_file.write_text(original_module)
        module_lockfile.write_text(original_modulelock)
        bazelversion_file.write_text(original_bazelversion)

    protobuf_versions = load_bcr_versions(bcr_path, "protobuf")
    rules_versions = load_bcr_versions(bcr_path, rules_dep)
    if not args.allow_prereleases:
        protobuf_versions = filter_prereleases(protobuf_versions)
        rules_versions = filter_prereleases(rules_versions)

    print(f"Searching for first (bazel, protobuf, {rules_dep}) where {lang} is precompiled...")
    print(f"  Bazel versions: {len(BAZEL_VERSIONS)}")
    print(f"  protobuf versions: {len(protobuf_versions)}")
    print(f"  {rules_dep} versions: {len(rules_versions)}")
    print()

    found = None
    try:
        for bv in BAZEL_VERSIONS:
            # Probe with the lowest versions to find minimums Bazel will accept.
            set_versions(module_file, bazelversion_file,
                         protobuf_versions[0], rules_dep, rules_versions[0], bv)
            min_pb, min_rules = probe_minimum_versions(
                repo_root, lang, protobuf_versions, rules_dep, rules_versions)

            protobuf_versions = protobuf_versions[protobuf_versions.index(min_pb):]
            rules_versions = rules_versions[rules_versions.index(min_rules):]
            print(f"  [>] bazel={bv}: skipping to protobuf={min_pb} {rules_dep}={min_rules}")

            for pv in protobuf_versions:
                for rv in rules_versions:
                    set_versions(module_file, bazelversion_file, pv, rules_dep, rv, bv)
                    status = check_precompiled(repo_root, lang)
                    marker = {"precompiled": "✓", "source": "✗", "error": "!"}[status]
                    print(f"  [{marker}] bazel={bv} protobuf={pv} {rules_dep}={rv}: {status}")
                    sys.stdout.flush()
                    if status == "precompiled":
                        found = (bv, pv, rv)
                        raise StopIteration()
    except StopIteration:
        pass
    except KeyboardInterrupt:
        restore()
        print("\nInterrupted, restored original files.")
        return

    if found:
        print(f"\n=== First precompiled combination ===")
        print(f"  Bazel: {found[0]}")
        print(f"  protobuf: {found[1]}")
        print(f"  {rules_dep}: {found[2]}")
    else:
        print("\nNo precompiled combination found in the search space.")

    if not args.no_restore:
        restore()
        print("\nRestored original MODULE.bazel and .bazelversion")


if __name__ == "__main__":
    main()
