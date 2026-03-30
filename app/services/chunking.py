def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
	if chunk_size <= 0:
		raise ValueError("chunk_size must be greater than 0")
	if overlap < 0:
		raise ValueError("overlap must be 0 or greater")
	if overlap >= chunk_size:
		raise ValueError("overlap must be smaller than chunk_size")

	normalized = text.strip()
	if not normalized:
		return []

	chunks: list[str] = []
	start = 0
	step = chunk_size - overlap

	while start < len(normalized):
		end = start + chunk_size
		chunk = normalized[start:end].strip()
		if chunk:
			chunks.append(chunk)
		start += step

	return chunks
