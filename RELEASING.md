# Releasing

Releases go to PyPI from GitHub Actions with trusted publishing (OIDC). No PyPI token is stored in this repository.

1. Bump `version` in `pyproject.toml` and add a `CHANGELOG.md` entry on a branch; merge after **CI** passes.
   CI builds the sdist and wheel, runs `twine check --strict`, installs the wheel into a fresh venv and runs
   `tests/test_roundtrip.py` (synthetic ACCDB → inspect → export → assess → load-sqlite → reconcile, plus a tampered
   landing copy that reconcile must reject).
2. Run **Release to PyPI** (`release-pypi.yml`) from `main` with the same version. It refuses a version that is
   already on PyPI, rebuilds and retests, then publishes from the `pypi` environment.

One-time owner setup on PyPI (https://pypi.org/manage/account/publishing/), before the first release:
add a pending trusted publisher with project `access-fieldkit`, owner `mhatipog`, repository
`access-migration-fieldkit`, workflow `release-pypi.yml`, environment `pypi`. Optionally require a reviewer on the
`pypi` environment in the repository settings.

Run the tests locally: `pip install . && cd tests && python -m unittest discover -s . -v` (needs a JDK; the first run
downloads the pinned Jackcess JAR, or set `ACCESS_FIELDKIT_JACKCESS_JAR`).
