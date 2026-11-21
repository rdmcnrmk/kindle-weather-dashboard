# Contributing

Use Python 3.11+ and the virtual environment described in README.md. Device code
runs under KOReader's Lua 5.1-compatible runtime; Python is tooling only.

Before a change, read docs/ARCHITECTURE.md and docs/DEVICE-VALIDATION.md. Keep
behavior changes focused and update the appropriate tests. For UI changes,
regenerate the local preview and inspect long labels and missing/stale data.

Before a commit:

```bash
make test
make preview
make build
make check
git diff --check
```

Commit source, documentation and manifest.json. Do not commit dist/, artifacts/,
.venv/, device-backups/, logs or reader settings. If the approved appearance changes,
copy the reviewed example preview into docs/images/preview.png.

For a release, update the version in pyproject.toml and CHANGELOG.md, update the
launcher banner and plugin metadata, then run make source. Keep GitHub publishing
separate from local builds. Report real device results with model, firmware,
KOReader version and the observed outcome; no account or Wi-Fi credentials.
