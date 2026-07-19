"""Yerel model (sentence-transformers / CrossEncoder) için device + dtype çözümü.

torch yalnız `local` extra ile kurulu olduğundan import lazy tutulur: paket,
torch olmadan da (fake/openai sağlayıcılarla) çalışabilmeli. Bu modül hem
embedding hem reranker tarafından paylaşılır — device/dtype mantığı tek yerde.
"""

import sys


def resolve_device_dtype(device: str = "auto", dtype: str = "auto"):
    """(device_str, torch_dtype | None) döndürür.

    device auto: cuda varsa "cuda", yoksa "cpu".
    dtype auto: cuda'da float16 (bu ~0.6B modeller 6GB VRAM'e birlikte sığsın),
                cpu'da None (float32 varsayılanı).
    Açık dtype ("float16"/"float32"/"bfloat16") verilirse torch.<dtype> kullanılır.
    """
    import torch

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if dtype == "auto":
        torch_dtype = torch.float16 if device == "cuda" else None
    else:
        torch_dtype = getattr(torch, dtype)  # "float16" -> torch.float16 (yanlışsa erken hata)

    return device, torch_dtype


def log_device(component: str, model_name: str, device: str, torch_dtype) -> None:
    """Seçilen device'i stderr'e yazar — GPU/CPU kısıtı bir daha görünmez olmasın."""
    dt = str(torch_dtype).replace("torch.", "") if torch_dtype is not None else "default"
    print(f"[{component}] {model_name} -> device={device} dtype={dt}", file=sys.stderr)
