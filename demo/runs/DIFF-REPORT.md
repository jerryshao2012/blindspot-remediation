# X1 Campaign — File Diff Report

_Generated 2026-09-16 from 31 archived candidate patches (`demo/runs/v2-*-gate/candidate.patch`)._

Every one of the 31 live `claude -p` runs made the X1 change (swap the transliteration backend). This report shows **every distinct diff each file received**, and which runs produced it. Runs are identified by their UTC timestamp; verdict in brackets.

## Convergence at a glance

| File | Distinct diffs / 31 runs | Reading |
|---|---|---|
| `setup.py` | 1 | **identical in every run** — the dependency declaration |
| `slugify/slugify.py` | 1 | **identical in every run** — the behaviour-bearing code |
| `tox.ini` | 5 | config — minor variants |
| `CHANGELOG.md` | 7 | prose, and **unrequested** (trips scope-creep on the gate) |
| `README.md` | 16 | prose — improvised almost every run |

> The two files that change what the software *does* — `setup.py` and `slugify/slugify.py` — are **byte-for-byte identical across all 31 runs** (verified by git blob hash, shown below). All run-to-run variance is in prose and config.


---

## `setup.py` — 1 distinct diff(s)

### Variant 1 of 1 — 31 run(s) · result blob `8d2b7ae9438a`

_Runs:_ 20260903T190015 [NEEDS_HUMAN], 20260903T190441 [PASS], 20260903T190602 [FAIL], 20260903T190720 [PASS], 20260903T190837 [PASS], 20260903T191006 [PASS], 20260903T191138 [PASS], 20260903T191305 [PASS], 20260903T191426 [PASS], 20260903T191549 [PASS], 20260903T191723 [NEEDS_HUMAN], 20260903T191853 [PASS], 20260903T192020 [FAIL], 20260903T192127 [NEEDS_HUMAN], 20260903T192235 [PASS], 20260903T192354 [PASS], 20260903T192523 [NEEDS_HUMAN], 20260903T192649 [PASS], 20260903T192820 [PASS], 20260903T192935 [PASS], 20260903T193105 [PASS], 20260903T193224 [PASS], 20260903T193342 [PASS], 20260903T193522 [FAIL], 20260903T193642 [NEEDS_HUMAN], 20260903T193819 [PASS], 20260903T193948 [PASS], 20260903T194108 [NEEDS_HUMAN], 20260903T194249 [PASS], 20260903T194426 [PASS], 20260903T194551 [NEEDS_HUMAN]

```diff
diff --git a/setup.py b/setup.py
--- a/setup.py
+++ b/setup.py
@@ -11,8 +11,8 @@ package = 'slugify'
 python_requires = ">=3.10"
 here = os.path.abspath(os.path.dirname(__file__))
 
-install_requires = ['text-unidecode>=1.3']
-extras_requires = {'unidecode': ['Unidecode>=1.1.1']}
+install_requires = ['Unidecode>=1.1.1']
+extras_requires = {}
 
 about = {}
 with open(os.path.join(here, package, '__version__.py'), 'r', encoding='utf-8') as f:
```

---

## `slugify/slugify.py` — 1 distinct diff(s)

### Variant 1 of 1 — 31 run(s) · result blob `dbf1abdf2b0d`

_Runs:_ 20260903T190015 [NEEDS_HUMAN], 20260903T190441 [PASS], 20260903T190602 [FAIL], 20260903T190720 [PASS], 20260903T190837 [PASS], 20260903T191006 [PASS], 20260903T191138 [PASS], 20260903T191305 [PASS], 20260903T191426 [PASS], 20260903T191549 [PASS], 20260903T191723 [NEEDS_HUMAN], 20260903T191853 [PASS], 20260903T192020 [FAIL], 20260903T192127 [NEEDS_HUMAN], 20260903T192235 [PASS], 20260903T192354 [PASS], 20260903T192523 [NEEDS_HUMAN], 20260903T192649 [PASS], 20260903T192820 [PASS], 20260903T192935 [PASS], 20260903T193105 [PASS], 20260903T193224 [PASS], 20260903T193342 [PASS], 20260903T193522 [FAIL], 20260903T193642 [NEEDS_HUMAN], 20260903T193819 [PASS], 20260903T193948 [PASS], 20260903T194108 [NEEDS_HUMAN], 20260903T194249 [PASS], 20260903T194426 [PASS], 20260903T194551 [NEEDS_HUMAN]

```diff
diff --git a/slugify/slugify.py b/slugify/slugify.py
--- a/slugify/slugify.py
+++ b/slugify/slugify.py
@@ -5,10 +5,7 @@ import unicodedata
 from collections.abc import Iterable
 from html.entities import name2codepoint
 
-try:
-    import unidecode
-except ImportError:
-    import text_unidecode as unidecode  # type: ignore[import-untyped, no-redef]
+import unidecode
 
 __all__ = ['slugify', 'smart_truncate']
```

---

## `tox.ini` — 5 distinct diff(s)

### Variant 1 of 5 — 15 run(s) · result blob `3c7027fa33fd`

_Runs:_ 20260903T190015 [NEEDS_HUMAN], 20260903T190720 [PASS], 20260903T191138 [PASS], 20260903T191426 [PASS], 20260903T191549 [PASS], 20260903T191723 [NEEDS_HUMAN], 20260903T191853 [PASS], 20260903T192354 [PASS], 20260903T192649 [PASS], 20260903T192935 [PASS], 20260903T193342 [PASS], 20260903T193819 [PASS], 20260903T193948 [PASS], 20260903T194249 [PASS], 20260903T194551 [NEEDS_HUMAN]

```diff
diff --git a/tox.ini b/tox.ini
--- a/tox.ini
+++ b/tox.ini
@@ -1,8 +1,8 @@
 [tox]
 env_list =
     coverage-erase
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
     coverage-report
     coverage-html
     mypy
@@ -10,16 +10,12 @@ env_list =
 
 [testenv]
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}: coverage-erase
-    pypy{3.11}-{unidecode, text_unidecode}: coverage-erase
+    py{3.10, 3.11, 3.12, 3.13, 3.14}: coverage-erase
+    pypy{3.11}: coverage-erase
 deps =
     coverage[toml]
     pytest
-    unidecode: pip
-    unidecode: unidecode
-commands_pre:
-    # If testing unidecode, ensure text_unidecode is unavailable.
-    unidecode: pip uninstall --yes text_unidecode
+    unidecode
 commands =
     coverage run -m pytest test.py
 
@@ -35,8 +31,8 @@ commands =
 [testenv:coverage-report]
 base = coverage_base
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
 commands_pre =
     - coverage combine
 commands =
```
### Variant 2 of 5 — 9 run(s) · result blob `fb42870f4670`

_Runs:_ 20260903T190602 [FAIL], 20260903T190837 [PASS], 20260903T191006 [PASS], 20260903T192523 [NEEDS_HUMAN], 20260903T192820 [PASS], 20260903T193105 [PASS], 20260903T193224 [PASS], 20260903T193642 [NEEDS_HUMAN], 20260903T194426 [PASS]

```diff
diff --git a/tox.ini b/tox.ini
--- a/tox.ini
+++ b/tox.ini
@@ -1,8 +1,8 @@
 [tox]
 env_list =
     coverage-erase
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
     coverage-report
     coverage-html
     mypy
@@ -10,16 +10,11 @@ env_list =
 
 [testenv]
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}: coverage-erase
-    pypy{3.11}-{unidecode, text_unidecode}: coverage-erase
+    py{3.10, 3.11, 3.12, 3.13, 3.14}: coverage-erase
+    pypy{3.11}: coverage-erase
 deps =
     coverage[toml]
     pytest
-    unidecode: pip
-    unidecode: unidecode
-commands_pre:
-    # If testing unidecode, ensure text_unidecode is unavailable.
-    unidecode: pip uninstall --yes text_unidecode
 commands =
     coverage run -m pytest test.py
 
@@ -35,8 +30,8 @@ commands =
 [testenv:coverage-report]
 base = coverage_base
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
 commands_pre =
     - coverage combine
 commands =
```
### Variant 3 of 5 — 2 run(s) · result blob `3c7afdbb92c0`

_Runs:_ 20260903T192235 [PASS], 20260903T194108 [NEEDS_HUMAN]

```diff
diff --git a/tox.ini b/tox.ini
--- a/tox.ini
+++ b/tox.ini
@@ -1,8 +1,8 @@
 [tox]
 env_list =
     coverage-erase
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}-unidecode
+    pypy{3.11}-unidecode
     coverage-report
     coverage-html
     mypy
@@ -10,16 +10,12 @@ env_list =
 
 [testenv]
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}: coverage-erase
-    pypy{3.11}-{unidecode, text_unidecode}: coverage-erase
+    py{3.10, 3.11, 3.12, 3.13, 3.14}-unidecode: coverage-erase
+    pypy{3.11}-unidecode: coverage-erase
 deps =
     coverage[toml]
     pytest
-    unidecode: pip
-    unidecode: unidecode
-commands_pre:
-    # If testing unidecode, ensure text_unidecode is unavailable.
-    unidecode: pip uninstall --yes text_unidecode
+    unidecode
 commands =
     coverage run -m pytest test.py
 
@@ -35,8 +31,8 @@ commands =
 [testenv:coverage-report]
 base = coverage_base
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}-unidecode
+    pypy{3.11}-unidecode
 commands_pre =
     - coverage combine
 commands =
```
### Variant 4 of 5 — 1 run(s) · result blob `787d34fa69d9`

_Runs:_ 20260903T190441 [PASS]

```diff
diff --git a/tox.ini b/tox.ini
--- a/tox.ini
+++ b/tox.ini
@@ -1,8 +1,8 @@
 [tox]
 env_list =
     coverage-erase
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
     coverage-report
     coverage-html
     mypy
@@ -10,16 +10,10 @@ env_list =
 
 [testenv]
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}: coverage-erase
-    pypy{3.11}-{unidecode, text_unidecode}: coverage-erase
+    coverage-erase
 deps =
     coverage[toml]
     pytest
-    unidecode: pip
-    unidecode: unidecode
-commands_pre:
-    # If testing unidecode, ensure text_unidecode is unavailable.
-    unidecode: pip uninstall --yes text_unidecode
 commands =
     coverage run -m pytest test.py
 
@@ -35,8 +29,8 @@ commands =
 [testenv:coverage-report]
 base = coverage_base
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
 commands_pre =
     - coverage combine
 commands =
```
### Variant 5 of 5 — 1 run(s) · result blob `0adaa2d73d91`

_Runs:_ 20260903T191305 [PASS]

```diff
diff --git a/tox.ini b/tox.ini
--- a/tox.ini
+++ b/tox.ini
@@ -1,8 +1,8 @@
 [tox]
 env_list =
     coverage-erase
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
     coverage-report
     coverage-html
     mypy
@@ -10,16 +10,11 @@ env_list =
 
 [testenv]
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}: coverage-erase
-    pypy{3.11}-{unidecode, text_unidecode}: coverage-erase
+    py{3.10, 3.11, 3.12, 3.13, 3.14}: coverage-erase
+    pypy{3.11}: coverage-erase
 deps =
     coverage[toml]
     pytest
-    unidecode: pip
-    unidecode: unidecode
-commands_pre:
-    # If testing unidecode, ensure text_unidecode is unavailable.
-    unidecode: pip uninstall --yes text_unidecode
 commands =
     coverage run -m pytest test.py
 
@@ -35,8 +30,8 @@ commands =
 [testenv:coverage-report]
 base = coverage_base
 depends =
-    py{3.10, 3.11, 3.12, 3.13, 3.14}-{unidecode, text_unidecode}
-    pypy{3.11}-{unidecode, text_unidecode}
+    py{3.10, 3.11, 3.12, 3.13, 3.14}
+    pypy{3.11}
 commands_pre =
     - coverage combine
 commands =
@@ -52,7 +47,6 @@ commands =
 [testenv:mypy]
 deps =
     mypy
-    unidecode
 commands =
     mypy
```

---

## `CHANGELOG.md` — 7 distinct diff(s)

### Variant 1 of 7 — 1 run(s) · result blob `f354e2ad7c4c`

_Runs:_ 20260903T190015 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Make `Unidecode` the primary required backend and drop `text-unidecode`.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 2 of 7 — 1 run(s) · result blob `179e56c1c239`

_Runs:_ 20260903T191723 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Make Unidecode the primary required backend (drop text-unidecode).
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 3 of 7 — 1 run(s) · result blob `27c78fef6591`

_Runs:_ 20260903T192127 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Make `Unidecode` the primary backend and drop `text-unidecode`.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 4 of 7 — 1 run(s) · result blob `50ea7d0eea25`

_Runs:_ 20260903T192523 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Switch to `Unidecode` as the primary, required transliteration backend and remove `text-unidecode` dependency.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 5 of 7 — 1 run(s) · result blob `1afa61b7b064`

_Runs:_ 20260903T193642 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Make `Unidecode` the primary, required backend; drop `text-unidecode`.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 6 of 7 — 1 run(s) · result blob `30da92b7d944`

_Runs:_ 20260903T194108 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Make `Unidecode` the primary, required transliteration backend; drop `text-unidecode`.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```
### Variant 7 of 7 — 1 run(s) · result blob `378da94a50af`

_Runs:_ 20260903T194551 [NEEDS_HUMAN]

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -3,7 +3,7 @@
 - Support Python 3.14.
 - Drop support for Python 3.9 and lower.
 - Use tox for local test runs and in CI.
-- Test the project against both `unidecode` and `text_unidecode`.
+- Switch to `unidecode` as the primary and only transliteration backend.
 - Fix type annotation issues identified by mypy.
 - Run CI against pull requests.
 - Fix package build warnings.
```

---

## `README.md` — 16 distinct diff(s)

### Variant 1 of 16 — 8 run(s) · result blob `29f9b05d6ee5`

_Runs:_ 20260903T191305 [PASS], 20260903T191853 [PASS], 20260903T192354 [PASS], 20260903T192649 [PASS], 20260903T192820 [PASS], 20260903T193642 [NEEDS_HUMAN], 20260903T194426 [PASS], 20260903T194551 [NEEDS_HUMAN]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 2 of 16 — 7 run(s) · result blob `24014221e3f7`

_Runs:_ 20260903T190015 [NEEDS_HUMAN], 20260903T190441 [PASS], 20260903T191426 [PASS], 20260903T191723 [NEEDS_HUMAN], 20260903T192235 [PASS], 20260903T193522 [FAIL], 20260903T193948 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module, by default installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 3 of 16 — 2 run(s) · result blob `f07f8ca94659`

_Runs:_ 20260903T191549 [PASS], 20260903T192020 [FAIL]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 4 of 16 — 2 run(s) · result blob `a89830f312fa`

_Runs:_ 20260903T193224 [PASS], 20260903T193819 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -200,8 +198,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 5 of 16 — 1 run(s) · result blob `85a48646759c`

_Runs:_ 20260903T190602 [FAIL]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
```
### Variant 6 of 16 — 1 run(s) · result blob `c557a350653e`

_Runs:_ 20260903T190720 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -200,8 +198,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+The dependency is GPL licensed, but `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 7 of 16 — 1 run(s) · result blob `3590a77fece5`

_Runs:_ 20260903T190837 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module, by default installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the default dependency [Unidecode](https://github.com/avian2/unidecode) is GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 8 of 16 — 1 run(s) · result blob `cfd14793babd`

_Runs:_ 20260903T191006 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependency may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 9 of 16 — 1 run(s) · result blob `abd57e4a4d1f`

_Runs:_ 20260903T191138 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module, by default installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -201,7 +195,7 @@ Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
 Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Please note that the default dependency `Unidecode` is licensed under the GPL.
 
 # Version
```
### Variant 10 of 16 — 1 run(s) · result blob `3ee624019161`

_Runs:_ 20260903T192127 [NEEDS_HUMAN]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module, by default installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -200,8 +198,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 11 of 16 — 1 run(s) · result blob `1a30451a3799`

_Runs:_ 20260903T192523 [NEEDS_HUMAN]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its transliteration needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependency is GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 12 of 16 — 1 run(s) · result blob `61a3aa0897c4`

_Runs:_ 20260903T192935 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -201,7 +195,7 @@ Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
 Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+If you wish to avoid installation of any GPL licensed packages, please note that `Unidecode` is licensed under GPL.
 
 # Version
```
### Variant 13 of 16 — 1 run(s) · result blob `15d947d18efc`

_Runs:_ 20260903T193105 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -201,7 +199,7 @@ Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
 Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Note that the dependency `Unidecode` is GPL licensed.
 
 # Version
```
### Variant 14 of 16 — 1 run(s) · result blob `7518791ccf12`

_Runs:_ 20260903T193342 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its transliteration needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 15 of 16 — 1 run(s) · result blob `c58a2ab5c23e`

_Runs:_ 20260903T194108 [NEEDS_HUMAN]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module installs and uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for its decoding needs.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependency [Unidecode](https://github.com/avian2/unidecode) is GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
### Variant 16 of 16 — 1 run(s) · result blob `b649d33a28d4`

_Runs:_ 20260903T194249 [PASS]

```diff
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -12,9 +12,7 @@
 
 # Notice
 
-This module, by default installs and uses [text-unidecode](https://github.com/kmike/text-unidecode) _(GPL & Perl Artistic)_ for its decoding needs.
-
-However, there is an alternative decoding package called [Unidecode](https://github.com/avian2/unidecode) _(GPL)_. It can be installed as `python-slugify[unidecode]` for those who prefer it. `Unidecode` is believed to be more [advanced](https://github.com/un33k/python-slugify/wiki/Python-Slugify-Wiki#notes-on-unidecode).
+This module uses [Unidecode](https://github.com/avian2/unidecode) _(GPL)_ for transliterating non-ASCII text.
 
 ### `Official` Support Matrix
 
@@ -28,10 +26,6 @@ However, there is an alternative decoding package called [Unidecode](https://git
 
     pip install python-slugify
 
-    # OR
-
-    pip install python-slugify[unidecode]
-
 # Options
 
 ```python
@@ -200,8 +194,7 @@ Please read the ([wiki](https://github.com/un33k/python-slugify/wiki/Python-Slug
 Released under a ([MIT](LICENSE)) license.
 
 ### Notes on GPL dependencies
-Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.  
-If you wish to avoid installation of any GPL licensed packages, please note that the default dependency `text-unidecode` explicitly lets you choose to use the [Artistic License](https://opensource.org/license/artistic-perl-1-0-2/) instead. Use without concern.
+Though the dependencies may be GPL licensed, `python-slugify` itself is not considered a derivative work and will remain under the MIT license.
 
 # Version
```
