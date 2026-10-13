# Contributing to dat

dat is a personal toolkit and public portfolio, built in the open. Outside contributions
are welcome but are not the project's goal, so the process below is deliberately light —
and one requirement is deliberately firm.

## Contributor License Agreement (required)

Every outside contribution — code, docs, data, anything — is accepted only under an
individual Contributor License Agreement (CLA). The CLA is modeled on the
[Apache Individual CLA](https://www.apache.org/licenses/icla.pdf) with one added clause:
you grant the project owner the right to sublicense your contribution under other terms.

Why: this repository is and stays Apache-2.0 (see ADR-012 in `docs/decisions/`). If paid
add-ons ever exist, they will live in a separate repository under a separate license, and a
standard Apache-2.0 contribution does not let your work be reused there. The CLA keeps that
option open; it never changes the license of anything in *this* repository.

How: when you open your first pull request, you'll be asked to sign the CLA before review.
There is no tooling for this yet — it is set up on the first outside PR, not before. You
sign once; it covers all future contributions.

The project owner's own commits need no CLA.

## Before you open a pull request

- **Open an issue first** for anything bigger than a typo or a one-line fix. The roadmap
  and decision log in `docs/` say what is in scope; a PR that contradicts an accepted ADR
  will be asked to propose a superseding ADR instead.
- **Run the checks** — they are the same ones CI runs:

  ```bash
  uv sync --all-packages
  uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
  ```

  Installing the pre-commit hooks once (`uv run pre-commit install`) runs ruff on every
  commit so CI never sees a formatting failure.
- **No secrets, no real employer data, anywhere** — not in code, tests, fixtures, examples,
  screenshots, or git history. Test data comes from `datbox-fake`.
- **Every module stands alone**: a change must keep each `packages/datbox-*` installable
  by itself and runnable by a stranger against fake data with no credentials.

## The merge rule

Nothing merges that the maintainer hasn't personally run as the target user — an analyst
on day one at a new job, inside a locked-down environment. Expect a PR to sit until that
has happened; it is not a judgment on the code.

## License

By contributing you agree that your contribution is licensed under
[Apache-2.0](LICENSE), subject to the CLA above.
