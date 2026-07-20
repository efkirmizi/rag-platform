"""Klasördeki dokümanlardan korpus yükler (bring-your-own-docs).

Markdown doğrudan okunur; PDF/DOCX/HTML/PPTX **Docling** ile markdown'a
çevrilir (plan Faz 1: "Docling ile parse; tablo ve başlık yapısı korunur").
Görseller (PNG/JPG/TIFF…) da Docling'e verilir ve **OCR** edilir — taranmış
belge ve ekran görüntüleri aranabilir olur; kalite/hız uyarıları için
`_IMAGE_EXT` yorumuna bakın. Docling opsiyonel bir ekstradır ve yalnız
gerektiğinde import edilir: `pip install -e ".[docs]"`.

Beklenen düzen:

    mydocs/
      permissions.json          # space/grup/izin yapısı (+ opsiyonel path_rules)
      ik/yillik-izin.md         # front-matter'lı markdown
      ik/yonetmelik.pdf         # front-matter taşıyamaz → path_rules'tan alır
      eng/vpn.docx

`permissions.json`:

    {
      "spaces":        {"IK": "İnsan Kaynakları", "ENG": "Mühendislik"},
      "groups":        {"herkes": ["ayse"], "ik-yonetim": ["zeynep"]},
      "space_viewers": {"IK": ["herkes"], "ENG": ["eng"]},

      "path_rules": [
        {"prefix": "ik/",       "space": "IK"},
        {"prefix": "ik/gizli/", "space": "IK", "restricted_to": "ik-yonetim"}
      ]
    }

Markdown front-matter (`---` blokları arasında, `anahtar: değer` satırları):

    ---
    space: IK
    title: Yıllık izin politikası
    restricted_to: ik-yonetim      # opsiyonel — sayfayı bu gruba kısıtlar
    url: https://intranet/...      # opsiyonel — citation'da kullanılır
    page_key: ik-yillik-izin       # opsiyonel — varsayılan: dosya yolundan üretilir
    ---
    ## Başlık
    içerik...

Metadata çözüm sırası: front-matter → eşleşen path_rule (en uzun önek kazanır).
Front-matter bilinçli olarak basit tutuldu (düz `anahtar: değer`): YAML
bağımlılığı eklemeden okunabilir kalır.
"""

import json
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

from ragplatform.ingestion.corpus import Corpus, Page

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_KNOWN_KEYS = {"space", "title", "restricted_to", "url", "page_key"}

# İçerik olmayan, klasörlerde sık bulunan dosyalar. Bunlar indexlenmeye
# çalışılırsa (front-matter'ları olmadığı için) yükleme komple hata verir —
# oysa kullanıcının docs klasöründe bir README bulunması son derece olağan.
# permissions.json'daki "ignore" ile değiştirilebilir (fnmatch kalıpları).
_DEFAULT_IGNORE = [
    "README.md", "readme.md", "README.markdown",
    "ATTRIBUTION.md", "LICENSE.md", "LICENCE.md", "NOTICE.md", "CHANGELOG.md",
    ".*",  # nokta ile başlayan gizli dosyalar
]

_MARKDOWN_EXT = {".md", ".markdown"}
# Docling'in yapısal parse ettiği formatlar (tablo/başlık hiyerarşisi korunur)
_DOCLING_EXT = {".pdf", ".docx", ".html", ".htm", ".pptx", ".xlsx"}
# Görseller: Docling bunlarda OCR çalıştırır (taranmış belge, ekran görüntüsü).
# İki uyarı — README'de de yazılı:
#  1) OCR kayıplıdır. Ölçüldü: "YILLIK IZIN" → "YILLIKIZIN". Kaybolan boşluk FTS
#     token'ını tamamen bozar; embedding daha aftedici ama yine de zayıflar.
#     Taranmış içerikte retrieval kalitesi doğal metne göre ölçülebilir düşüktür.
#  2) OCR yavaştır (sayfa başına layout modeli). Görsel ağırlıklı bir klasörde
#     ingest süresi ciddi artar; istenmiyorsa permissions.json "ignore" ile
#     dışlanabilir (ör. "*.png").
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_SUPPORTED_EXT = _MARKDOWN_EXT | _DOCLING_EXT | _IMAGE_EXT


class FolderSourceError(Exception):
    """Kullanıcıya gösterilecek, düzeltilebilir yükleme hatası."""


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """(front-matter sözlüğü, gövde) döner. Front-matter yoksa ({}, metin)."""
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise FolderSourceError(f"front-matter satırı 'anahtar: değer' değil: {line!r}")
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[m.end():]


def _page_key_from_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    slug = "-".join(rel.parts).lower()
    return re.sub(r"[^a-z0-9._-]+", "-", slug).strip("-")


def match_path_rule(rel_posix: str, rules: list[dict]) -> dict:
    """Yola uyan kuralı döner; birden çok eşleşirse EN UZUN önek kazanır.

    Böylece `ik/` genel kuralının üstüne `ik/gizli/` istisnası yazılabilir.
    """
    best: dict = {}
    best_len = -1
    for rule in rules:
        prefix = rule.get("prefix", "")
        if rel_posix.startswith(prefix) and len(prefix) > best_len:
            best, best_len = rule, len(prefix)
    return best


class _DoclingConverter:
    """Docling'i tembel yükler ve tek örnek üzerinden yeniden kullanır.

    DocumentConverter kurulumu model yüklediği için pahalıdır; klasör başına
    bir kez oluşturulup tüm dosyalar için kullanılır.

    OCR dili varsayılan olarak `en` — Docling'in varsayılanı `chinese` ve bu
    LATİN yazıda kelimeleri BİTİŞİK üretiyor (Çince kelime arası boşluk
    kullanmaz). Ölçüldü, aynı taranmış sayfa:
        chinese : "Kidemi1-5yilarasicalisanlar14isgunuizinkullanir."   (0/10 kelime)
        en      : "Kidemi 1-5 yilarasi calisanlar 14 isgunu izin kullanir."  (8/10)
    Boşluksuz metin FTS'te tek dev token olur ve hiçbir sorguyla eşleşmez;
    yani varsayılan bırakılırsa taranmış Türkçe içerik aranamaz hale gelir.
    permissions.json'daki "ocr_lang" ile değiştirilebilir (ör. ["cyrillic"]).
    """

    def __init__(self, ocr_lang: list[str] | None = None):
        self._conv = None
        self._lang = ocr_lang or ["en"]

    def _build(self, path: Path):
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
                RapidOcrOptions,
            )
            from docling.document_converter import (
                DocumentConverter,
                ImageFormatOption,
                PdfFormatOption,
            )
        except ImportError as e:
            raise FolderSourceError(
                f"{path.name}: Docling kurulu değil. Markdown dışı dosyalar "
                'için: pip install -e ".[docs]"  (ya da bu dosyayı çıkarın)'
            ) from e

        opts = PdfPipelineOptions()
        opts.do_ocr = True
        opts.ocr_options = RapidOcrOptions(lang=self._lang)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=opts),
            }
        )

    def to_markdown(self, path: Path) -> str:
        if self._conv is None:
            self._conv = self._build(path)
        try:
            return self._conv.convert(str(path)).document.export_to_markdown()
        except Exception as e:  # bozuk/şifreli dosya vb.
            raise FolderSourceError(f"{path}: Docling ayrıştıramadı: {e}") from e


def load_folder(root: str | Path) -> Corpus:
    """Klasörü Corpus'a yükler. Yapısal hatalarda FolderSourceError yükseltir."""
    root = Path(root)
    if not root.is_dir():
        raise FolderSourceError(f"klasör yok: {root}")

    perm_path = root / "permissions.json"
    if not perm_path.exists():
        raise FolderSourceError(
            f"{perm_path} yok. spaces/groups/space_viewers tanımlayan bir "
            "permissions.json gerekli (örnek: examples/docs/permissions.json)."
        )
    try:
        perms = json.loads(perm_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FolderSourceError(f"{perm_path} geçerli JSON değil: {e}") from e

    corpus = Corpus(
        spaces=perms.get("spaces", {}),
        groups=perms.get("groups", {}),
        space_viewers=perms.get("space_viewers", {}),
    )
    rules = perms.get("path_rules", [])
    ignore = perms.get("ignore", _DEFAULT_IGNORE)
    converter = _DoclingConverter(perms.get("ocr_lang"))

    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _SUPPORTED_EXT
        and not any(fnmatch(p.name, pat) for pat in ignore)
    )
    for path in files:
        rel_posix = path.relative_to(root).as_posix()
        rule = match_path_rule(rel_posix, rules)
        is_markdown = path.suffix.lower() in _MARKDOWN_EXT

        if is_markdown:
            try:
                meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
            except FolderSourceError as e:
                raise FolderSourceError(f"{path}: {e}") from e
            unknown = set(meta) - _KNOWN_KEYS
            if unknown:
                raise FolderSourceError(
                    f"{path}: bilinmeyen front-matter anahtar(lar)ı: {sorted(unknown)}. "
                    f"Geçerli: {sorted(_KNOWN_KEYS)}"
                )
        else:
            meta, body = {}, converter.to_markdown(path)
            if not body.strip():
                # Metin çıkmayan dosya (logo, fotoğraf, boş PDF) sayfa olarak
                # eklenirse korpus doğrulaması "içerik boş" diye TÜM yüklemeyi
                # düşürür. Klasörde metinsiz görsel bulunması olağan → atla,
                # ama sessizce değil.
                print(f"[atla] {rel_posix}: metin çıkarılamadı (boş)", file=sys.stderr)
                continue

        space = meta.get("space") or rule.get("space")
        if not space:
            hint = (
                "front-matter'da 'space' verin ya da permissions.json'a bu yolu "
                "kapsayan bir path_rules girdisi ekleyin"
            )
            raise FolderSourceError(f"{path}: space belirlenemedi — {hint}")

        corpus.pages.append(
            Page(
                page_key=meta.get("page_key") or _page_key_from_path(path, root),
                space=space,
                title=meta.get("title") or rule.get("title") or path.stem,
                content=body,
                restricted_to=meta.get("restricted_to") or rule.get("restricted_to") or None,
                url=meta.get("url") or None,
            )
        )

    if not corpus.pages:
        raise FolderSourceError(
            f"{root} altında desteklenen dosya bulunamadı "
            f"(desteklenen: {', '.join(sorted(_SUPPORTED_EXT))})"
        )
    return corpus
