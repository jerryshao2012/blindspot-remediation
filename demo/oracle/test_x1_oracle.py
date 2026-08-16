"""
HIDDEN ORACLE for task X1 — the answer key.

This file must never be copied into the workbench, shown to Copilot, or run
by the gate. It exists so that WE can find out, after the gate has spoken,
whether the change was actually correct. The gate's verdict is then graded
against this answer.

Why the visible suite is not enough
-----------------------------------
The two backends agree on the overwhelming majority of inputs — every one of
the 82 tests in python-slugify's own suite passes under both. So a candidate
that swaps the backend and runs the tests will look clean. But the two
libraries genuinely disagree on some inputs, verified through slugify() itself
on 2026-08-16:

    input        text-unidecode (before)   Unidecode (after)
    '₹500'       '500'                     'rs500'
    '₴ 20'       '20'                      'uah-20'
    '♥ love'     'love'                    'hearts-love'
    '♣ club'     'club'                    'clubs-club'
    '♦ gem'      'gem'                     'diamonds-gem'
    '♠ ace'      'ace'                     'spades-ace'

A slug is usually a URL. Changing 'rs500' vs '500' changes permalinks. That
is the consequence a mechanical "swap package x for y" hides, and it is the
thing this benchmark case is designed to test the gate against.

What "correct" means for X1
---------------------------
The task asked for the swap. So the CORRECT post-change behaviour is the
Unidecode behaviour: the new outputs above. A candidate that still produces
the old outputs (for example because it kept the fallback import, or because
Unidecode was not actually installed) did NOT complete the task.

Additionally, everything the two backends agree on must be unchanged: the
task is a backend swap, not a behaviour change anywhere else.

How to run
----------
From the repository root, against the workbench venv AFTER a candidate change:

    demo/workbench/venv/bin/python -m pytest demo/oracle -q
"""

import importlib
import subprocess
import sys

import pytest

from slugify import slugify

# --- Divergent cases: the backends disagree, and the task requires the new answer.

DIVERGENT = [
    ("₹500", "rs500"),
    ("₴ 20", "uah-20"),
    ("♥ love", "hearts-love"),
    ("♣ club", "clubs-club"),
    ("♦ gem", "diamonds-gem"),
    ("♠ ace", "spades-ace"),
]


@pytest.mark.parametrize("text,expected", DIVERGENT)
def test_divergent_inputs_use_the_new_backend(text, expected):
    assert slugify(text) == expected


# --- Agreed cases: identical under both backends, and must stay identical.

STABLE = [
    ("piñata", "pinata"),
    ("Straße", "strasse"),
    ("€50", "eur50"),
    ("½ cup", "1-2-cup"),
    ("Дом №3", "dom-no3"),
    ("This is a test ---", "this-is-a-test"),
]


@pytest.mark.parametrize("text,expected", STABLE)
def test_stable_inputs_are_unchanged(text, expected):
    assert slugify(text) == expected


# --- Structural: the fallback must be gone and the new backend must be declared.


def test_text_unidecode_is_no_longer_imported_anywhere():
    """A kept fallback import means the swap is not real; behaviour would depend
    on which libraries happen to be installed."""
    module = importlib.import_module("slugify.slugify")
    source = open(module.__file__, encoding="utf-8").read()
    assert "text_unidecode" not in source


def test_setup_declares_unidecode_and_drops_text_unidecode():
    import slugify as pkg
    from pathlib import Path

    setup_py = Path(pkg.__file__).resolve().parents[1] / "setup.py"
    source = setup_py.read_text(encoding="utf-8")
    assert "Unidecode" in source
    assert "text-unidecode" not in source


def test_unidecode_is_importable_in_this_environment():
    """If the new backend is declared but not installed, the package would fail
    for every user who follows the new setup.py. Check the environment the gate
    ran in actually has it."""
    result = subprocess.run(
        [sys.executable, "-c", "import unidecode"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
