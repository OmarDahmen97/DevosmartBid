import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from app.translator.text_chunker import split_text_for_translation


class NLLBTranslator:

    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1

        self.tokenizer = AutoTokenizer.from_pretrained(
            "facebook/nllb-200-distilled-600M"
        )
        self.tokenizer.src_lang = "fra_Latn"

        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            "facebook/nllb-200-distilled-600M",
            torch_dtype=torch.float16 if self.device == 0 else torch.float32
        )

        if self.device == 0:
            self.model = self.model.cuda()

        print(
            "Loading NLLB translator on",
            "GPU" if self.device == 0 else "CPU"
        )
        print("NLLB ready")

    def translate(self, text):
        if not text.strip():
            return ""

        chunks = split_text_for_translation(text)
        translated_chunks = []

        for index, chunk in enumerate(chunks):
            print(f"Translating chunk {index+1}/{len(chunks)}")

            inputs = self.tokenizer(
                chunk,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )

            if self.device == 0:
                inputs = {k: v.cuda() for k, v in inputs.items()}

            generated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.lang_code_to_id["eng_Latn"],
                max_length=512
            )

            translated = self.tokenizer.batch_decode(
                generated_tokens,
                skip_special_tokens=True
            )[0]
            translated_chunks.append(translated)

        return "\n".join(translated_chunks)