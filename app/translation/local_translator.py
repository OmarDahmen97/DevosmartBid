# file: app/translation/local_translator.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "xiaomi-research/MiLMMT-46-4B-v1.0"

_model = None
_tokenizer = None

LANGUAGE_NAMES = {
    "fr": "French",
    "en": "English",
    "es": "Spanish",
    "de": "German",
}


def _load_model():
    global _model, _tokenizer
    if _model is None:
        print(f"[local_translator] Loading {MODEL_ID}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
        if not torch.cuda.is_available():
            _model = _model.to("cpu")
        print("[local_translator] Model loaded.")
    return _model, _tokenizer


def translate_text(text: str, source_lang: str, target_lang: str, max_new_tokens: int = 4096) -> str:
    if not text or not text.strip():
        return text

    src_name = LANGUAGE_NAMES.get(source_lang)
    tgt_name = LANGUAGE_NAMES.get(target_lang)
    if not src_name or not tgt_name:
        raise ValueError(
            f"Unsupported language code(s): source={source_lang!r}, target={target_lang!r}. "
            f"Supported: {list(LANGUAGE_NAMES.keys())}"
        )

    model, tokenizer = _load_model()

    prompt = f"Translate this from {src_name} to {tgt_name}:\n{src_name}: {text}\n{tgt_name}:"
    inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )

    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    marker = f"{tgt_name}:"
    if marker in full_output:
        return full_output.split(marker, 1)[-1].strip()
    return full_output.strip()