# Security Policy

## Educational context

This project is developed for educational purposes only. It does not guarantee any level of production security hardening. Users are responsible for their own operational security when running this application.

## Supported versions

Only the latest published release is considered supported for security-related fixes.

## Reporting a vulnerability

Please **do not** open public issues for suspected security problems.

Instead:

1. Contact the maintainer privately (open a private GitHub Security Advisory or email).
2. Include steps to reproduce, affected version, and potential impact.
3. Allow reasonable time for triage before public disclosure.

## What counts as a security issue

- Arbitrary file write outside intended download/config directories
- Unsafe shell command execution
- Sensitive local data exposure (credentials, tokens)
- Malicious dependency or packaging issues

## What usually does not count

- Normal download failures from upstream service changes
- Unsupported YouTube URL types or temporary extractor breakage
- UI bugs without security impact
- Failures caused by running on an unsupported Python version
