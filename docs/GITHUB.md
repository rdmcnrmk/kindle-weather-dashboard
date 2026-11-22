# Continue in Codex and work with GitHub

Repository: https://github.com/rdmcnrmk/kindle-home-dashboard

## Codex handoff

Open the **kindle-home-dashboard** folder as your Codex project. This folder
is self-contained; no files from the surrounding chat workspace are required.
AGENTS.md provides the working context and docs/DEVICE-VALIDATION.md records what
is actually known about the hardware.

A useful first task is:

> Read AGENTS.md and the device validation notes. Continue validating the
> scheduled-wake path on Paperwhite 3, preserve the English layout, and keep
> device logs and reader settings out of Git. Run the local tests before edits
> are packaged. Do not claim RTC or battery results without real device evidence.

## Repository setup

The prepared local folder uses `main` and has `origin` configured to the
repository above. Commit identity is configured locally, using Erdem Irmak and
the GitHub account's ID-based noreply address; global Git settings are unchanged.
To work on another computer, clone the repository:

```bash
git clone https://github.com/rdmcnrmk/kindle-home-dashboard.git
cd kindle-home-dashboard
```

A downloaded source ZIP excludes Git history. Prefer cloning the repository
when you want to commit changes. Configure your own name and commit email on
each computer before creating commits.

## Subsequent changes

```bash
git status
# Make changes, run the appropriate checks, and inspect the diff.
git add <CHANGED_FILES>
git commit -m "Describe the change"
git push -u origin main
```

Nothing in the local build/CI scripts creates a remote or publishes a release.
The included CI workflow tests and builds on pushes and pull requests. Inspect
the Actions tab after a push; local tests do not prove the remote run succeeded.

For later releases, update the version/changelog, run make test and make source,
commit the source/manifest, push, and attach the device ZIP and checksum to the
release you choose to publish. Keep the source available under the included AGPL.
