"""Kaynak-bağımsız korpus modeli: içerik + izin yapısı.

Sentetik senaryo, klasör connector'ı ve (Faz 1'de) Confluence connector'ı aynı
`Corpus` yapısını üretir; FGA tuple üretimi ve index'leme tek yoldan çalışır.

İzin semantiği (Confluence'ı taklit eder):
- Kullanıcı bir space'i, o space'e viewer olan bir gruba üyeyse görür.
- Kısıtlı sayfa erişimi DARALTIR: sayfayı görmek için hem space erişimi hem
  açık `restricted_to` grubu üyeliği gerekir.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Page:
    page_key: str
    space: str
    title: str
    content: str
    restricted_to: str | None = None
    url: str | None = None

    @property
    def is_restricted(self) -> bool:
        return self.restricted_to is not None


@dataclass
class Corpus:
    spaces: dict[str, str] = field(default_factory=dict)  # key -> görünen ad
    groups: dict[str, list[str]] = field(default_factory=dict)  # grup -> kullanıcılar
    space_viewers: dict[str, list[str]] = field(default_factory=dict)  # space -> gruplar
    pages: list[Page] = field(default_factory=list)

    # --- izin hesabı ---
    # Not: sentetik senaryonun kendi `expected_allowed_*` fonksiyonları
    # (scripts/synthetic_corpus.py) bilinçli olarak ayrı tutulur — leak testinin
    # "beklenen" tarafı bağımsız bir uygulama olsun ki iki taraf birbirinin
    # hatasını yakalayabilsin.

    def user_groups(self, user: str) -> set[str]:
        return {g for g, members in self.groups.items() if user in members}

    def allowed_spaces(self, user: str) -> set[str]:
        ug = self.user_groups(user)
        return {s for s, viewers in self.space_viewers.items() if ug & set(viewers)}

    def allowed_pages(self, user: str) -> set[str]:
        ug = self.user_groups(user)
        spaces = self.allowed_spaces(user)
        return {
            p.page_key
            for p in self.pages
            if p.space in spaces and (p.restricted_to is None or p.restricted_to in ug)
        }

    def users(self) -> set[str]:
        return {u for members in self.groups.values() for u in members}

    def validate(self) -> list[str]:
        """Referans bütünlüğü hatalarını döner (boş liste = sağlam).

        Kullanıcı kendi korpusunu getirdiğinde sessiz yanlış davranış yerine
        anlaşılır hata almalı: tanımsız space'e bağlı sayfa, var olmayan gruba
        kısıtlanmış sayfa, tekrar eden page_key vb.
        """
        errs: list[str] = []
        seen: set[str] = set()
        for p in self.pages:
            if p.page_key in seen:
                errs.append(f"page_key tekrar ediyor: {p.page_key}")
            seen.add(p.page_key)
            if p.space not in self.spaces:
                errs.append(f"{p.page_key}: tanımsız space '{p.space}'")
            if p.restricted_to and p.restricted_to not in self.groups:
                errs.append(f"{p.page_key}: tanımsız grup '{p.restricted_to}' (restricted_to)")
            if not p.title.strip():
                errs.append(f"{p.page_key}: title boş")
            if not p.content.strip():
                errs.append(f"{p.page_key}: içerik boş")
        for space, viewers in self.space_viewers.items():
            if space not in self.spaces:
                errs.append(f"space_viewers: tanımsız space '{space}'")
            for g in viewers:
                if g not in self.groups:
                    errs.append(f"space_viewers[{space}]: tanımsız grup '{g}'")
        for space in self.spaces:
            if space not in self.space_viewers:
                errs.append(f"'{space}' space'ine hiçbir grup viewer değil — kimse göremez")
        return errs


def build_tuples(corpus: Corpus) -> list[tuple[str, str, str]]:
    """OpenFGA (user, relation, object) üçlüleri üretir."""
    tuples: list[tuple[str, str, str]] = []
    for group, members in corpus.groups.items():
        for user in members:
            tuples.append((f"user:{user}", "member", f"group:{group}"))
    for space, viewer_groups in corpus.space_viewers.items():
        for group in viewer_groups:
            tuples.append((f"group:{group}#member", "viewer", f"space:{space}"))
    for page in corpus.pages:
        tuples.append((f"space:{page.space}", "parent", f"page:{page.page_key}"))
        if page.restricted_to:
            tuples.append(
                (f"group:{page.restricted_to}#member", "restricted_viewer", f"page:{page.page_key}")
            )
    return tuples


async def index_corpus(
    pool,
    embedder,
    corpus: Corpus,
    *,
    quiet: bool = False,
    max_chars: int = 800,
    overlap: int = 150,
) -> int:
    """Korpusu chunk'layıp embed'leyerek indexler; toplam chunk sayısını döner.

    index_page upsert + chunk replace olduğu için idempotenttir: aynı korpusu
    farklı bir embedding modeliyle yeniden indexlemek vektörleri değiştirir,
    FGA tuple'larına dokunmaz.
    """
    # Döngüsel import olmasın diye burada: indexer bu modülü kullanmıyor ama
    # çağrı yönü net kalsın.
    from ragplatform.ingestion.indexer import index_page, upsert_space

    for key, name in corpus.spaces.items():
        await upsert_space(pool, key, name)
    total = 0
    for page in corpus.pages:
        n = await index_page(
            pool,
            embedder,
            page_key=page.page_key,
            space_key=page.space,
            title=page.title,
            content_md=page.content,
            url=page.url,
            is_restricted=page.is_restricted,
            max_chars=max_chars,
            overlap=overlap,
        )
        total += n
        if not quiet:
            flag = " [KISITLI]" if page.is_restricted else ""
            print(f"[db] {page.space:>5} / {page.page_key:<24} {n} chunk{flag}")
    return total
