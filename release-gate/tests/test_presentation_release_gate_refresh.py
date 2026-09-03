from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def slide_count(source: str) -> int:
    return len(re.findall(r'<section\b[^>]*class="[^"]*\bslide\b[^"]*"', source))


def test_x1_deck_uses_september_no_oracle_release_gate_evidence() -> None:
    source = read("docs/x1-behind-the-scenes.html")

    assert slide_count(source) == 16
    assert "20260902T153230Z-0b1d3f349b56" in source
    assert "7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4" in source
    assert "a5d82da63b0a40d0de639ec1293e8d1d3c3e0307" in source
    assert "24fa968d82e846d71573f686a2c74e5c342869a0" in source
    assert "uv run --python 3.12 --no-project python demo.py setup" in source
    assert "OBSERVABILITY_PATH_UNSAFE" in source
    assert "No hidden oracle ran; semantic correctness is not proven." in source
    assert "September 1 automated verification" in source
    assert "20260827T143722Z-58368f55bad1" not in source
    assert "trace.json             <span class=\"dim\">12 events" not in source


def test_executive_and_architecture_distinguish_online_gate_from_offline_oracle() -> None:
    executive = read("release-gate/demo/release-gate-demo.html")
    architecture = read("docs/architecture.html")

    assert slide_count(executive) == 10
    assert "production ends with evidence review and a human release decision" in executive
    assert "offline known-answer qualification" in executive
    assert "2026-09-02 no-oracle PASS" in executive
    assert "tests-and-coverage PASS · task-consistency PASS · types PASS" in executive
    assert "assistant/control candidate → deterministic gate → evidence review → human release decision" in architecture
    assert "known-answer controls → gate → hidden oracle grading" in architecture
    assert "RUN-LOG-2026-09-02-no-oracle-pass.md" in architecture
    assert "RUN-LOG-2026-09-01-automated-verification.md" in architecture


def test_hub_reflects_refreshed_x1_duration_and_release_gate_positioning() -> None:
    source = read("docs/presentations.html")
    index = read("index.html")

    assert 'url=./docs/presentations.html' in index
    assert 'href="./docs/presentations.html"' in index
    assert "16 Slides · 25m" in source
    assert "production-style no-oracle gate run" in source
    assert "offline calibration" in source
    assert "production evidence review from benchmark-only oracle qualification" in source


def test_presentation_entrypoints_reference_existing_local_files() -> None:
    html_files = [
        ROOT / "index.html",
        *sorted((ROOT / "docs").glob("*.html")),
        ROOT / "release-gate/demo/release-gate-demo.html",
    ]
    missing: list[str] = []

    for path in html_files:
        source = path.read_text(encoding="utf-8")
        refs = re.findall(
            r"""(?:href|src)=["']([^"'#?]+)["']|url\(["']?([^)"'#?]+)["']?\)""",
            source,
        )
        for href, css_url in refs:
            ref = href or css_url
            parsed = urlsplit(ref)
            path_ref = unquote(parsed.path)
            if parsed.scheme or ref.startswith(("/", "#")) or path_ref.startswith("#") or ref.startswith(("data:", "mailto:", "javascript:")):
                continue
            target = (path.parent / path_ref).resolve()
            if not target.exists():
                missing.append(f"{path.relative_to(ROOT)} -> {ref}")

    assert missing == []
