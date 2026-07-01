# Contributing

Thank you for considering a contribution to this repository. It is
maintained as an educational and research workflow (see
[README.md § Overview](README.md#overview)), so contributions that improve
transparency, reproducibility, or documentation accuracy are as welcome as
code changes.

## Before you start

- Read [README.md](README.md), in particular
  [Limitations](README.md#limitations) and
  [Scientific Integrity](README.md#scientific-integrity), so that any change
  you propose is consistent with the project's stated scope (an educational
  workflow, not a bankable feasibility study).
- For changes to the energy production or economic assessment, also read
  [`economics/README.md`](economics/README.md).
- Check [`CHANGELOG.md`](CHANGELOG.md) for recent changes before starting
  work, to avoid duplicating effort.

## Development setup

Follow [Installation](README.md#installation) in the README to set up the
Python environment and, if needed, FEFLOW 8.1 itself. Stages that require a
FEFLOW licence are listed in
[Running the Workflow](README.md#running-the-workflow); the post-processing
stage and the full test suite run without one.

## Making a change

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-description
   ```
2. Write or update tests for any new functionality under `tests/`. All
   existing tests must continue to pass:
   ```bash
   pytest tests/ -v
   ```
3. Follow [PEP 8](https://peps.python.org/pep-0008/). Use variable names
   consistent with the existing codebase (e.g., `K_mday`, `heat_flux_bc`).
   Every push and pull request is checked automatically by
   `.github/workflows/python-app.yml` (flake8 + pytest).
4. Do not commit FEFLOW binaries or generated caches — `.fem`, `.dac`,
   `.smhx`, `.cache`, and `.bak` files, and the contents of `outputs/`
   (other than the tracked CSVs), are covered by `.gitignore`. If your
   change legitimately needs to add a new generated artifact to version
   control, make that explicit in the pull request description.
5. If your change affects a number, figure, or conclusion described in
   `README.md`, `economics/README.md`, or the [Key Results](README.md#key-results)
   table, update the corresponding documentation in the same pull request —
   do not let code and documentation drift apart.
6. Add an entry to [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`
   describing the change.
7. Open a pull request with a clear description of the change and its
   motivation.

## Reporting issues

When opening an issue, please include:

- FEFLOW version and operating system (if relevant to the issue).
- Python version and `pip freeze` output.
- A minimal reproducer or the full error traceback.

## Scope of contributions

This repository intentionally keeps its economic and reservoir models
simple (see [Engineering Assumptions](README.md#engineering-assumptions) and
[Limitations](README.md#limitations)). Contributions that add optional,
clearly documented extensions (for example, items listed under
[Future Work](README.md#future-work)) are welcome; contributions that
silently remove or obscure an existing assumption, or that overstate the
accuracy of the economic assessment, will not be merged without a
corresponding update to the Assumptions/Limitations documentation.
