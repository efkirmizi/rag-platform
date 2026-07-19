# Retrieval servisi + seed/ingest script'leri için tek imaj.
# Yerel model (torch/sentence-transformers) BİLİNÇLİ olarak dahil değil:
# imaj küçük kalsın diye. Demo `fake` embedding ile çalışır; gerçek model için
# EMBEDDINGS_PROVIDER=openai ile vLLM endpoint'i verilir (üretim hedefi).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bağımlılık katmanı önce: kaynak değişince pip install tekrar çalışmasın.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Çalışma zamanında gereken veri/script'ler
COPY scripts/ ./scripts/
COPY infra/ ./infra/
COPY eval/ ./eval/
COPY examples/ ./examples/

EXPOSE 8000

# Konteyner içinden servis adlarına bağlan (compose ağı)
ENV DATABASE_URL=postgresql://rag:ragpass@postgres:5432/rag \
    FGA_API_URL=http://openfga:8080

CMD ["uvicorn", "ragplatform.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
