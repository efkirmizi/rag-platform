"""OpenFGA store bootstrap: store + authorization model + izin tuple'ları.

Sentetik seed ve klasör ingest'i paylaşır. Model JSON'unu çağıran yükler
(dosya yolu repo düzenine ait, kütüphaneye değil).
"""

import json
from pathlib import Path

from ragplatform.acl.fga import FgaAdmin
from ragplatform.config import Settings


async def bootstrap_store(
    settings: Settings,
    model: dict,
    tuples: list[tuple[str, str, str]],
    *,
    store_name: str = "rag",
    quiet: bool = False,
) -> tuple[str, str]:
    """Yeni store + model oluşturur, tuple'ları yazar, state dosyasını günceller.

    State dosyası (`fga_state_file`) FgaClient.from_settings tarafından okunur;
    yol CWD'ye görelidir — script'ler repo kökünden çalıştırılır.
    Her çağrı YENİ store oluşturur (eskisi silinmez, kullanılmaz).
    """
    admin = FgaAdmin(settings.fga_api_url)
    try:
        store_id = await admin.create_store(store_name)
        model_id = await admin.write_model(store_id, model)

        state_path = Path(settings.fga_state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"store_id": store_id, "model_id": model_id}, indent=2),
            encoding="utf-8",
        )
        written = await admin.write_tuples(store_id, model_id, tuples)
        if not quiet:
            print(f"[fga] store={store_id} model={model_id} -> {state_path.name}")
            print(f"[fga] {written} tuple yazıldı")
    finally:
        await admin.close()
    return store_id, model_id
