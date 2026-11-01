# Maintaining this fork

The default maintained branch is `stig`. The fork retains upstream history and the
`aula` integration domain. The first fork release, v0.1.70, starts from upstream's
stable v0.1.69 plus the reviewed authentication and EasyIQ weekly-text changes.
The manifest also adopts upstream's compatible Beautiful Soup minimum and avoids
redeclaring requests, which Home Assistant already supplies.

## HACS installation

1. Keep the existing Aula config entry, account, entities and dashboards.
2. Keep a source backup before replacing the installed HACS download.
3. Remove the original **scaarup/aula** download from HACS only.
4. Add **StigCPH/aula** as a custom integration repository and install its release.
5. Restart Home Assistant. Confirm the existing account loads and the weekplan text
   remains available. Confirm HACS identifies **StigCPH/aula** as installed and the
   original repository as not installed.

Normal HACS update actions must target this fork. Do not reinstall the original
repository or install both repositories for the same domain. No direct changes to
Home Assistant's `.storage` are part of the migration.

## Bringing in upstream changes

Upstream does not automatically overwrite the maintained branch.

1. Fetch `https://github.com/scaarup/aula.git` as the `upstream` remote.
2. Create a review branch from `stig`; merge the selected upstream stable tag.
3. Resolve conflicts while retaining the fork's token persistence, bounded widget
   refresh and EasyIQ weekly-text behavior. Keep the manifest documentation and
   issue links pointed at this fork.
4. Run the complete test suite using Python 3.14:
   `python -m pip install -r requirements.txt -r requirements.test.txt`, then
   `python -m pytest -v`.
5. Review the diff and test with an authorized Home Assistant instance before
   merging to `stig`. Keep provider tokens and real school content out of Git.
6. Set a new version in the manifest and add release notes. This fork's release
   numbers are independent of upstream's; do not replace an existing tag.

## Publishing a release

The release workflow builds the tagged commit, not an unreviewed default-branch
checkout. It never rewrites source files or pushes a manifest update after testing.

1. Push the reviewed `stig` commit and wait for CI/code validation to pass.
2. Create and push a matching tag, e.g. `v0.1.70`.
3. Run the **Release maintained fork** workflow on `stig` with that tag.
   It tests the exact tag, checks the committed manifest version, and publishes
   `aula.zip` plus `SHA256SUMS`.
4. Refresh repository information in HACS and verify its offered repository/version.
5. Verify the installed source checksums, existing Aula entry and representative
   sensor/calendar data after installation.

The ZIP includes only integration source and assets. Test fixtures, local settings,
logs and runtime credentials are excluded. All newly added public fixtures are
fictitious; private diagnostic recordings stay outside this repository.

## Rollback

Before each installation keep the existing component source. For a release rollback,
select a previous **fork** release in HACS, then restart Home Assistant. This restores
code only and must not delete the Aula config entry or restore historical tokens.
Existing source backups on the original test installation are under
`/config/codex_backups/aula-auth-20261101/`.
