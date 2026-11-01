#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
test_dir="$(mktemp -d "${TMPDIR:-/tmp}/autolycus-tv-tests.XXXXXX")"
javac_bin="${JAVA_HOME:+$JAVA_HOME/bin/}javac"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
"$javac_bin" -d "$test_dir" \
  "$project_dir/tools/NativeAudioCorrelationCheck.java" \
  "$project_dir/app/src/main/java/dev/quiet/autolycus/NativeAudioCorrelation.java"
"$java_bin" -cp "$test_dir" dev.quiet.autolycus.NativeAudioCorrelationCheck
"$javac_bin" -d "$test_dir" \
  "$project_dir/tools/WatchNextPolicyCheck.java" \
  "$project_dir/app/src/main/java/dev/quiet/autolycus/WatchNextPolicy.java"
"$java_bin" -cp "$test_dir" dev.quiet.autolycus.WatchNextPolicyCheck
