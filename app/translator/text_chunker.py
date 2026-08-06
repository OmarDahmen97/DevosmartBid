def split_text_for_translation(text: str, max_chars: int = 1500):
    """
    Split text for translation without overlap.
    """

    if not text:
        return []

    chunks = []
    current_chunk = []
    current_length = 0

    for paragraph in text.split("\n"):

        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if current_length + len(paragraph) > max_chars:

            if current_chunk:
                chunks.append(
                    "\n".join(current_chunk)
                )

            current_chunk = [paragraph]
            current_length = len(paragraph)

        else:
            current_chunk.append(paragraph)
            current_length += len(paragraph)

    if current_chunk:
        chunks.append(
            "\n".join(current_chunk)
        )

    return chunks