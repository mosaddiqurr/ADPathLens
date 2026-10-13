# Contributing to AuthZDiff

AuthZDiff is maintained in [mosaddiqurr/ADPathLens](https://github.com/mosaddiqurr/ADPathLens).
Use [GitHub issues](https://github.com/mosaddiqurr/ADPathLens/issues) for bug reports and proposed
improvements. Include reproduction steps, expected behavior, and synthetic examples where useful.
Remove credentials, personal data, and private request/response content before posting.

## Development setup

Fork and clone the repository, then follow the [README setup](README.md#run-locally).
Development requires Python 3.12+ and Node.js 22.13+ (22.x) or 24+.
Install `backend/requirements-dev.lock` into `.venv` and run `npm ci` in `frontend`.

The backend lives in `backend/app`; the React application lives in `frontend/src`.
Use the fictional datasets in `examples/` when reproducing comparison behavior.
The [architecture](docs/ARCHITECTURE.md) and [input contracts](docs/INPUTS.md) describe the
current design and supported formats.

## Making changes

1. Create a branch for a focused change.
2. Update the relevant documentation when behavior, input contracts, or deployment settings change.
3. Add regression coverage for changes to comparison rules, parsing, redaction, or exports.
4. Run the applicable [README validation commands](README.md#testing-and-production-build).
   Build the frontend before running the Playwright browser suite.
5. Run `python scripts/verify-publication.py` from the repository root before opening a pull request.

Keep datasets synthetic and dependencies reproducible. If dependencies change, update the
corresponding lock file. Generated dependencies, reports, runtime files, and local environment
values are excluded by `.gitignore`.

## Pull requests

Explain the problem, resulting behavior, and validation performed. For interface changes,
include a screenshot using synthetic data. For comparison changes, include a small Before/After
example and its expected result. Describe any remaining limitations so reviewers can assess them.

Contributions are distributed under the repository's [MIT license](LICENSE).
