import asyncio

from ragplatform.generation.base import LLMProvider


class LocalHFLLM(LLMProvider):
    """transformers ile yerel üretim — demo/geliştirme içindir, üretim değil.

    Üretim hedefi vLLM'dir (openai_compat). Bu sağlayıcı, GPU'su olan birinin
    tüm hattı (retrieval → prompt → cevap → citation) tek makinede uçtan uca
    görebilmesi için var.

    VRAM notu: embedding ve reranker de yerelse aynı GPU'yu paylaşırlar.
    6GB'lık bir kartta ~1.7B'lik bir modeli fp16'da çalıştırmak (~3.4GB) sınırda
    ama mümkündür; embedding+reranker de yüklüyse `EMBEDDINGS_PROVIDER=fake`
    ile deneyin ya da daha küçük bir model seçin.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
        device: str = "auto",
        dtype: str = "auto",
        max_new_tokens: int = 512,
    ):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        from ragplatform.hardware import log_device, resolve_device_dtype

        dev, torch_dtype = resolve_device_dtype(device, dtype)
        self.name = model_name
        self._max_new = max_new_tokens
        self._tok = AutoTokenizer.from_pretrained(model_name)
        kwargs = {"torch_dtype": torch_dtype} if torch_dtype is not None else {}
        self._model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs).to(dev)
        self._model.eval()
        self._device = dev
        log_device("generation", model_name, dev, torch_dtype)

    async def complete(self, system: str, user: str, *, max_tokens: int = 512) -> str:
        # Üretim bloklayıcı ve ağır — event loop'u tıkamamak için thread'e alınır.
        return await asyncio.to_thread(self._generate, system, user, max_tokens)

    def _generate(self, system: str, user: str, max_tokens: int) -> str:
        import torch

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = self._tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tok(text, return_tensors="pt").to(self._device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=min(max_tokens, self._max_new),
                do_sample=False,  # deterministik: eval tekrar edilebilir olsun
                pad_token_id=self._tok.eos_token_id,
            )
        # Yalnız yeni üretilen kısmı çöz (prompt'u geri yazma)
        generated = out[0][inputs["input_ids"].shape[1]:]
        return self._tok.decode(generated, skip_special_tokens=True).strip()
