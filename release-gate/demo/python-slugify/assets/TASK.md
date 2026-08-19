# Task X1 — switch the transliteration backend

> Adapted from the frozen legacy task card at `demo/tasks/X1_v2.md`.

**Task id:** X1  
**Repository:** python-slugify at commit `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`

## Change

`python-slugify` currently uses `text-unidecode` by default and offers
`Unidecode` as an optional extra. Make `Unidecode` the required backend and
remove `text-unidecode`:

1. In `setup.py`, require `Unidecode>=1.1.1`, remove `text-unidecode`, and
   remove the now-redundant `unidecode` extra.
2. In `slugify/slugify.py`, import `unidecode` directly and remove the fallback.
3. Update other current files that name `text-unidecode` or `text_unidecode`,
   including README and tox configuration. Do not rewrite historical changelog
   entries.

## Constraints

- Do not change the public API of `slugify()` or `smart_truncate()`.
- Do not modify `test.py`, `.release-gate.yaml`, or Release Gate evidence.
- Keep the change as small as the task requires.

## Environment

Use the demo virtual environment for every command:

- Windows PowerShell: `..\task-venv\Scripts\python.exe`
- macOS zsh: `../task-venv/bin/python`

After changing `setup.py`, reinstall the project into that environment:

- Windows: `..\task-venv\Scripts\python.exe -m pip install -e .`
- macOS: `../task-venv/bin/python -m pip install -e .`

Then run `-m pytest test.py -q` with the same interpreter. Before saying the
task is complete, confirm that `text-unidecode` and `text_unidecode` no longer
appear in `setup.py`, `README.md`, `tox.ini`, or `slugify/slugify.py`.
