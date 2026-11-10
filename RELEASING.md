# Versioning and Releases

## Version numbers

MaaS-GUI uses [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`, e.g. `1.4.2`.

| Change | Bump | Example |
|---|---|---|
| Bug fix or small tweak; nothing new for the user to learn | **PATCH** | `1.0.0` → `1.0.1` |
| New feature, tab, or option; existing behaviour still works | **MINOR** (reset PATCH to 0) | `1.0.3` → `1.1.0` |
| Breaking change: old setups/files/servers no longer work, or a major redesign | **MAJOR** (reset MINOR and PATCH to 0) | `1.4.2` → `2.0.0` |

Rules of thumb:
- Each released version is published once and never changed. A fix after a release becomes a new version.
- If a release contains both fixes and a feature, bump for the biggest change (MINOR).
- Examples of MAJOR: needing a new MaaS backend API version, changing the saved `.npy` file format so older files cannot be read, or removing a measurement mode.

The version lives in one place: [`version.py`](version.py). It appears in the window title and in the exe's *Properties → Details*.

## Making a release

1. Update `__version__` in `version.py` (e.g. `"1.0.1"`) and merge that into `main`.
2. Tag the merged commit and push the tag (the tag is the version with a `v` in front):
   ```bash
   git checkout main
   git pull
   git tag v1.0.1
   git push origin v1.0.1
   ```
3. The **Release** GitHub Action (`.github/workflows/release.yml`) then:
   - checks the tag matches `version.py` (and stops if not),
   - runs the tests,
   - builds `MaaS-GUI.exe` on Windows,
   - publishes a GitHub Release with the exe attached and auto-generated notes listing the merged PRs.

Users download the newest version from:
https://github.com/ghm213-ku/MaaS-GUI/releases/latest

Progress and errors are shown on the repo's **Actions** tab. If a run fails, fix the problem, then delete the tag (`git tag -d v1.0.1` and `git push origin :v1.0.1`) and tag again. Only do this if the release was **not** published.
