# -*- coding: utf-8 -*-
"""Türkçe token verimliliği ölçümü (G-2).

Her aday embedding modelinin tokenizer'ıyla sentetik korpusu tokenize edip
tokens/kelime ve tokens/karakter oranını raporlar. Türkçe'nin eklemeli yapısı
tokenizer'a göre farklı parçalanır; bu oran bağlam bütçesini ve API/GPU
maliyetini doğrudan etkiler (daha çok token = daha çok hesap + daha küçük
etkin bağlam). Yalnız tokenizer indirilir (model ağırlığı gerekmez → hızlı).

Çalıştırma: python scripts/token_efficiency.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import synthetic_corpus as corpus

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODELS = ["BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"]


def corpus_texts() -> list[str]:
    # Başlık + gövde: indexer'ın gömdüğü bağlam başlığına yakın gerçekçi girdi.
    return [f"{p['title']}\n{p['content']}" for p in corpus.PAGES]


def measure(models: list[str], texts: list[str]) -> dict:
    from transformers import AutoTokenizer

    joined = "\n".join(texts)
    words = len(joined.split())
    chars = len(joined)
    out: dict = {"words": words, "chars": chars, "models": {}}
    for name in models:
        tok = AutoTokenizer.from_pretrained(name)
        n_tokens = sum(len(tok.encode(t, add_special_tokens=False)) for t in texts)
        out["models"][name] = {
            "tokens": n_tokens,
            "tokens_per_word": round(n_tokens / words, 3),
            "tokens_per_char": round(n_tokens / chars, 4),
            "vocab_size": getattr(tok, "vocab_size", None),
        }
    return out


def main() -> int:
    res = measure(MODELS, corpus_texts())
    print(f"Korpus: {len(corpus.PAGES)} sayfa, {res['words']} kelime, {res['chars']} karakter\n")
    print(f"{'Model':<32} {'tokens':>8} {'tok/kelime':>11} {'tok/karakter':>13} {'vocab':>8}")
    for name, m in res["models"].items():
        print(
            f"{name:<32} {m['tokens']:>8} {m['tokens_per_word']:>11} "
            f"{m['tokens_per_char']:>13} {str(m['vocab_size']):>8}"
        )
    print(
        "\nNot: düşük tok/kelime = Türkçe'yi daha verimli parçalar = aynı bağlamda "
        "daha çok içerik, daha düşük maliyet."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
