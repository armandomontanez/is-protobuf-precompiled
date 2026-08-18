# Is protoc precompiled?

This repo tracks whether or not [Protobuf's](https://protobuf.dev/) `protoc`
tool is available as a precompiled binary in [Bazel](https://bazel.build/)
projects.

## Status

| Language | Precompiled | First precompiled | Versions |
|----------|-------------|-------------------|----------|
| C++ | :x: | - | - |
| Java | :white_check_mark: | 2026-08-18 | protobuf 35.1, rules_java 9.3.0, Bazel 9.2.0 |
| Python | :x: | - | - |

_Last updated: 2026-08-18_

## How it works

This repository uses [Dependabot](https://docs.github.com/en/code-security/dependabot)
to automatically roll Bazel module dependencies (protobuf, rules_cc, rules_java,
rules_python) and the Bazel version itself. On every push to `main`, a CI
workflow runs `bazel cquery somepath(...)` to determine whether each language's
proto target has a dependency path to `@protobuf//src/google/protobuf` (the
source tree). If a path exists, protoc is being compiled from source. If no path
exists, a precompiled protoc binary is being used.
