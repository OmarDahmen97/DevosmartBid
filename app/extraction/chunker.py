

def split_raw_text_into_chunks(text: str, max_chars: int = 1500, overlap: int = 150) -> list:
    """
    Splits raw text (long general CV) into chunks of approximately `max_chars` characters.
    Keeps a safety `overlap` to avoid cutting an experience entry or important sentence in the middle.
    """
    if not text:
        return []
        
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        # Security: If a single paragraph is unusually large
        if len(paragraph) > max_chars:
            # Force it to be split
            chunks.append(paragraph[:max_chars])
            continue

        # If adding this paragraph exceeds the maximum chunk size
        if current_length + len(paragraph) > max_chars:
            # Assemble and save the current chunk
            chunks.append("\n".join(current_chunk))
            
            # Handle the overlap: retrieve the last 1 or 2 paragraphs
            # to preserve semantic context in the next chunk
            overlap_text = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk
            current_chunk = list(overlap_text) + [paragraph]
            current_length = sum(len(line) for line in current_chunk)
        else:
            current_chunk.append(paragraph)
            current_length += len(paragraph)

    
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks