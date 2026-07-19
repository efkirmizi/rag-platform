# -*- coding: utf-8 -*-
"""Klasör connector'ı (bring-your-own-docs): front-matter, yükleme, doğrulama.

Kullanıcı kendi korpusunu getirdiğinde sessizce yanlış davranmak yerine
anlaşılır hata vermeli — testlerin çoğu hata yollarını sabitler.
"""

import json
from pathlib import Path

import pytest

from ragplatform.ingestion.corpus import Corpus, Page, build_tuples
from ragplatform.ingestion.folder_source import (
    FolderSourceError,
    load_folder,
    match_path_rule,
    parse_front_matter,
)

REPO_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "docs"


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _perms(root: Path, **over) -> None:
    data = {
        "spaces": {"IK": "Insan Kaynaklari"},
        "groups": {"herkes": ["ayse", "mehmet"], "yonetim": ["ayse"]},
        "space_viewers": {"IK": ["herkes"]},
    }
    data.update(over)
    _write(root, "permissions.json", json.dumps(data))


# --- front-matter ---


def test_parse_front_matter_basic():
    meta, body = parse_front_matter("---\nspace: IK\ntitle: Bir\n---\ngovde")
    assert meta == {"space": "IK", "title": "Bir"}
    assert body.strip() == "govde"


def test_parse_front_matter_absent():
    meta, body = parse_front_matter("# sadece govde")
    assert meta == {}
    assert body == "# sadece govde"


def test_parse_front_matter_strips_quotes():
    meta, _ = parse_front_matter('---\ntitle: "Tirnakli Baslik"\n---\nx')
    assert meta["title"] == "Tirnakli Baslik"


def test_parse_front_matter_value_with_colon():
    meta, _ = parse_front_matter("---\nurl: https://x.local/a?b=1\n---\nx")
    assert meta["url"] == "https://x.local/a?b=1"


def test_parse_front_matter_bad_line_raises():
    with pytest.raises(FolderSourceError):
        parse_front_matter("---\nbozuk satir\n---\nx")


# --- yükleme ---


def test_load_folder_builds_corpus(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "ik/izin.md", "---\nspace: IK\ntitle: Izin\n---\niceriktir")
    c = load_folder(tmp_path)
    assert len(c.pages) == 1
    assert c.pages[0].page_key == "ik-izin"  # yoldan üretilir
    assert c.pages[0].title == "Izin"
    assert c.validate() == []


def test_load_folder_explicit_page_key_and_restriction(tmp_path):
    _perms(tmp_path)
    _write(
        tmp_path,
        "ik/gizli.md",
        "---\nspace: IK\ntitle: Gizli\npage_key: ozel-key\nrestricted_to: yonetim\n---\nicerik",
    )
    c = load_folder(tmp_path)
    p = c.pages[0]
    assert p.page_key == "ozel-key"
    assert p.restricted_to == "yonetim"
    assert p.is_restricted


def test_load_folder_missing_permissions_raises(tmp_path):
    _write(tmp_path, "a.md", "---\nspace: IK\ntitle: A\n---\nx")
    with pytest.raises(FolderSourceError, match="permissions.json"):
        load_folder(tmp_path)


def test_load_folder_missing_front_matter_raises(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "a.md", "front-matter yok")
    with pytest.raises(FolderSourceError, match="front-matter"):
        load_folder(tmp_path)


def test_load_folder_unknown_key_raises(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "a.md", "---\nspace: IK\ntitle: A\nbilinmeyen: x\n---\nicerik")
    with pytest.raises(FolderSourceError, match="bilinmeyen"):
        load_folder(tmp_path)


def test_load_folder_missing_space_raises(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "a.md", "---\ntitle: A\n---\nicerik")
    with pytest.raises(FolderSourceError, match="space"):
        load_folder(tmp_path)


def test_load_folder_no_markdown_raises(tmp_path):
    _perms(tmp_path)
    with pytest.raises(FolderSourceError, match="bulunamadı"):
        load_folder(tmp_path)


def test_load_folder_bad_json_raises(tmp_path):
    _write(tmp_path, "permissions.json", "{bozuk")
    _write(tmp_path, "a.md", "---\nspace: IK\ntitle: A\n---\nx")
    with pytest.raises(FolderSourceError, match="JSON"):
        load_folder(tmp_path)


# --- doğrulama ---


def test_validate_catches_unknown_space(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "a.md", "---\nspace: YOK\ntitle: A\n---\nicerik")
    assert any("tanımsız space" in e for e in load_folder(tmp_path).validate())


def test_validate_catches_unknown_restriction_group(tmp_path):
    _perms(tmp_path)
    _write(tmp_path, "a.md", "---\nspace: IK\ntitle: A\nrestricted_to: yokgrup\n---\nicerik")
    assert any("tanımsız grup" in e for e in load_folder(tmp_path).validate())


def test_validate_catches_space_with_no_viewers(tmp_path):
    _perms(tmp_path, spaces={"IK": "IK", "BOS": "Kimsesiz"})
    _write(tmp_path, "a.md", "---\nspace: IK\ntitle: A\n---\nicerik")
    assert any("hiçbir grup viewer" in e for e in load_folder(tmp_path).validate())


def test_validate_catches_duplicate_page_key():
    c = Corpus(
        spaces={"S": "S"},
        groups={"g": ["u"]},
        space_viewers={"S": ["g"]},
        pages=[Page("dup", "S", "A", "x"), Page("dup", "S", "B", "y")],
    )
    assert any("tekrar" in e for e in c.validate())


# --- izin hesabı + tuple üretimi ---


def test_allowed_pages_respects_restriction():
    c = Corpus(
        spaces={"IK": "IK"},
        groups={"herkes": ["ayse", "mehmet"], "yonetim": ["ayse"]},
        space_viewers={"IK": ["herkes"]},
        pages=[
            Page("acik", "IK", "Acik", "x"),
            Page("gizli", "IK", "Gizli", "y", restricted_to="yonetim"),
        ],
    )
    assert c.allowed_pages("ayse") == {"acik", "gizli"}
    assert c.allowed_pages("mehmet") == {"acik"}  # space'i görür, kısıtlıyı görmez
    assert c.allowed_spaces("mehmet") == {"IK"}


def test_build_tuples_shape():
    c = Corpus(
        spaces={"IK": "IK"},
        groups={"yonetim": ["ayse"]},
        space_viewers={"IK": ["yonetim"]},
        pages=[Page("gizli", "IK", "G", "x", restricted_to="yonetim")],
    )
    t = build_tuples(c)
    assert ("user:ayse", "member", "group:yonetim") in t
    assert ("group:yonetim#member", "viewer", "space:IK") in t
    assert ("space:IK", "parent", "page:gizli") in t
    assert ("group:yonetim#member", "restricted_viewer", "page:gizli") in t


# --- path_rules (PDF/DOCX front-matter taşıyamaz) ---


def test_match_path_rule_longest_prefix_wins():
    rules = [
        {"prefix": "ik/", "space": "IK"},
        {"prefix": "ik/gizli/", "space": "IK", "restricted_to": "yonetim"},
    ]
    assert match_path_rule("ik/izin.md", rules)["space"] == "IK"
    assert match_path_rule("ik/gizli/maas.pdf", rules)["restricted_to"] == "yonetim"
    assert match_path_rule("baska/x.md", rules) == {}


def test_markdown_without_front_matter_uses_path_rule(tmp_path):
    _perms(tmp_path, path_rules=[{"prefix": "ik/", "space": "IK"}])
    _write(tmp_path, "ik/izin.md", "front-matter yok ama kural var")
    c = load_folder(tmp_path)
    assert c.validate() == []
    assert c.pages[0].space == "IK"
    assert c.pages[0].title == "izin"  # dosya adına düşer


def test_path_rule_can_restrict(tmp_path):
    _perms(
        tmp_path,
        path_rules=[
            {"prefix": "ik/", "space": "IK"},
            {"prefix": "ik/gizli/", "space": "IK", "restricted_to": "yonetim"},
        ],
    )
    _write(tmp_path, "ik/acik.md", "acik icerik")
    _write(tmp_path, "ik/gizli/maas.md", "gizli icerik")
    c = load_folder(tmp_path)
    by_key = {p.page_key: p for p in c.pages}
    assert by_key["ik-acik"].restricted_to is None
    assert by_key["ik-gizli-maas"].restricted_to == "yonetim"
    assert "ik-gizli-maas" not in c.allowed_pages("mehmet")


def test_front_matter_overrides_path_rule(tmp_path):
    _perms(tmp_path, path_rules=[{"prefix": "ik/", "space": "IK", "title": "Kural"}])
    _write(tmp_path, "ik/x.md", "---\ntitle: Front-matter\n---\nicerik")
    assert load_folder(tmp_path).pages[0].title == "Front-matter"


def test_no_space_anywhere_gives_actionable_error(tmp_path):
    _perms(tmp_path)  # path_rules yok
    _write(tmp_path, "ik/x.md", "front-matter yok")
    with pytest.raises(FolderSourceError, match="path_rules"):
        load_folder(tmp_path)


def test_unsupported_extension_ignored(tmp_path):
    _perms(tmp_path, path_rules=[{"prefix": "", "space": "IK"}])
    _write(tmp_path, "notlar.txt", "desteklenmeyen")
    _write(tmp_path, "gecerli.md", "icerik")
    keys = [p.page_key for p in load_folder(tmp_path).pages]
    assert keys == ["gecerli"]


def test_docling_missing_gives_actionable_error(tmp_path):
    """Docling kurulu değilken PDF net bir kurulum mesajı vermeli."""
    pytest.importorskip  # noqa: B018 - açıklık için
    try:
        import docling  # noqa: F401

        pytest.skip("docling kurulu — bu test kurulu olmadığı durumu doğrular")
    except ImportError:
        pass
    _perms(tmp_path, path_rules=[{"prefix": "", "space": "IK"}])
    (tmp_path / "rapor.pdf").write_bytes(b"%PDF-1.4 sahte")
    with pytest.raises(FolderSourceError, match="docs"):
        load_folder(tmp_path)


# --- repodaki örnek klasör ---


def test_bundled_example_folder_is_valid():
    c = load_folder(REPO_EXAMPLE)
    assert c.validate() == []
    assert c.allowed_pages("alice") >= {"handbook-onboarding", "handbook-compensation"}
    # bob HANDBOOK'u görür ama kısıtlı ücret sayfasını görmez
    assert "handbook-compensation" not in c.allowed_pages("bob")
    assert "eng-deployment" in c.allowed_pages("bob")
