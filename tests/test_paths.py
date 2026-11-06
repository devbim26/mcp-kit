"""RootPolicy: сервер читает файлы только из разрешённых корней."""
from __future__ import annotations

import os

import pytest

from mcp_kit.errors import ToolError
from mcp_kit.paths import RootPolicy


@pytest.fixture
def policy(tmp_path):
    root = tmp_path / "roots"
    root.mkdir()
    return RootPolicy(roots=[root]), root


def test_empty_roots_rejected():
    with pytest.raises(ValueError):
        RootPolicy(roots=[])


def test_path_inside_root_is_allowed(policy):
    pol, root = policy
    target = root / "комплект.pdf"
    target.write_bytes(b"%PDF-1.7")

    resolved = pol.resolve(str(target))

    assert resolved == os.path.realpath(str(target))
    assert resolved.startswith(os.path.realpath(str(root)))


def test_path_outside_root_is_rejected(policy, tmp_path):
    pol, _ = policy
    outside = tmp_path / "чужой.pdf"
    outside.write_bytes(b"%PDF-1.7")

    with pytest.raises(ToolError) as exc:
        pol.resolve(str(outside))

    assert exc.value.code == "path_not_allowed"
    assert "вне разрешённых корней" in str(exc.value)


def test_dotdot_escape_is_rejected(policy):
    pol, root = policy
    escape = str(root / ".." / "побег.pdf")

    with pytest.raises(ToolError) as exc:
        pol.resolve(escape)

    assert exc.value.code == "path_not_allowed"


def test_empty_path_is_rejected(policy):
    pol, _ = policy
    with pytest.raises(ToolError):
        pol.resolve("")


def test_codec_dir_inside_root_reused(policy):
    pol, root = policy
    pdf = root / "комплект.pdf"
    pdf.write_bytes(b"%PDF-1.7")

    codec = pol.codec_dir_for(str(pdf), fallback_root=str(root / "tmp"))

    assert codec == os.path.splitext(str(pdf))[0] + ".codec"


def test_codec_dir_outside_root_goes_to_fallback(policy, tmp_path):
    pol, _ = policy
    outside = tmp_path / "чужой.pdf"
    outside.write_bytes(b"%PDF-1.7")
    fallback = tmp_path / "tmp"

    codec = pol.codec_dir_for(str(outside), fallback_root=str(fallback))

    assert codec == str(fallback / "codec")


def test_symlink_escape_is_rejected(policy, tmp_path):
    pol, root = policy
    outside = tmp_path / "цель.pdf"
    outside.write_bytes(b"%PDF-1.7")
    link = root / "ссылка.pdf"
    try:
        os.symlink(str(outside), str(link))
    except OSError as exc:
        pytest.skip(f"symlink недоступен: {exc}")

    with pytest.raises(ToolError) as exc:
        pol.resolve(str(link))

    assert exc.value.code == "path_not_allowed"
