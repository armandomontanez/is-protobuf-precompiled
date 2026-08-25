# Is protobuf precompiled?

This repo tracks whether or not [Protobuf's](https://protobuf.dev/) `protoc`
tool is available as a precompiled binary in [Bazel](https://bazel.build/)
projects.

## Status

| Language | Precompiled | First precompiled | Versions |
|----------|-------------|-------------------|----------|
| C++ | :x: | - | - |
| Java | :white_check_mark: | 2026-03-19 | Bazel 9.0.0, `protobuf@34.1`, `rules_java@9.0.3` |
| Python | :x: | - | - |

_Last updated: 2026-08-25_

## How it works

This repository uses [Dependabot](https://docs.github.com/en/code-security/dependabot)
to automatically roll Bazel module dependencies (protobuf, rules_cc, rules_java,
rules_python) and the Bazel version itself. On every push to `main`, a CI
workflow runs `bazel cquery somepath(...)` to determine whether each language's
proto target has a dependency path to `@protobuf//src/google/protobuf` (the
source tree). If a path exists, protoc is being compiled from source. If no path
exists, a precompiled protoc binary is being used.

## Known issues

### 36.0, 36.0-rc1, 36.0-rc2

Prebuilt macOS release artifacts have mismatched digests, making the upstream protobuf
toolchains unusable in macOS builds.

* https://github.com/protocolbuffers/protobuf/issues/29313

### Python

There are fixes to `py_proto_library` that target the removal of the protobuf source
library from the protobuf critical path when using a precompiled toolchain. These
should be included in v36.0 (when that releases).

* https://github.com/protocolbuffers/protobuf/issues/28028
* https://github.com/protocolbuffers/protobuf/issues/25759

### C++

When using protobuf toolchain resolution, `cc_proto_library` runtime is not linked
properly when using dynamic linking. This can preclude projects from enabling the
precompiled protoc toolchain.

* https://github.com/protocolbuffers/protobuf/issues/25577
* https://github.com/bazelbuild/rules_cc/pull/588
