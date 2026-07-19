"""Klasördeki markdown dosyalarından korpus yükler (bring-your-own-docs).

Beklenen düzen:

    mydocs/
      permissions.json          # space/grup/izin yapısı
      ik/yillik-izin.md         # front-matter'lı markdown
      eng/vpn.md

`permissions.json`:

    {
      "spaces":        {"IK": "İnsan Kaynakları", "ENG": "Mühendislik"},
      "groups":        {"herkes": ["ayse", "mehmet"], "ik-yonetim": ["zeynep"]},
      "space_viewers": {"IK": ["herkes"], "ENG": ["eng"]}
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

Front-matter bilinçli olarak basit tutuldu (düz `anahtar: değer`): YAML
bağımlılığı eklemeden okunabilir kalır. İç içe yapı gerekmiyor.
"""

import json
import re
from pathlib import Path

from ragplatform.ingestion.corpus import Corpus, Page

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_KNOWN_KEYS = {"space", "title", "restricted_to", "url", "page_key"}


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

    md_files = sorted(p for p in root.rglob("*.md") if p.is_file())
    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        try:
            meta, body = parse_front_matter(raw)
        except FolderSourceError as e:
            raise FolderSourceError(f"{path}: {e}") from e
        if not meta:
            raise FolderSourceError(
                f"{path}: front-matter yok. En az 'space' ve 'title' gerekli "
                "(dosyanın başına --- blokları ekleyin)."
            )
        unknown = set(meta) - _KNOWN_KEYS
        if unknown:
            raise FolderSourceError(
                f"{path}: bilinmeyen front-matter anahtar(lar)ı: {sorted(unknown)}. "
                f"Geçerli: {sorted(_KNOWN_KEYS)}"
            )
        if "space" not in meta:
            raise FolderSourceError(f"{path}: front-matter'da 'space' zorunlu")
        corpus.pages.append(
            Page(
                page_key=meta.get("page_key") or _page_key_from_path(path, root),
                space=meta["space"],
                title=meta.get("title") or path.stem,
                content=body,
                restricted_to=meta.get("restricted_to") or None,
                url=meta.get("url") or None,
            )
        )

    if not corpus.pages:
        raise FolderSourceError(f"{root} altında .md dosyası bulunamadı")
    return corpus
