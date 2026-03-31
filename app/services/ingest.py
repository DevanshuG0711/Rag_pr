from io import BytesIO

from ast_chunking import extract_python_ast_chunks
from app.services.call_graph import extract_call_graph
from pypdf import PdfReader


def extract_text_from_txt(file_bytes: bytes) -> str:
	try:
		return file_bytes.decode("utf-8")
	except UnicodeDecodeError:
		return file_bytes.decode("latin-1")


def extract_text_from_pdf(file_bytes: bytes) -> str:
	reader = PdfReader(BytesIO(file_bytes))
	pages: list[str] = []

	for page in reader.pages:
		pages.append(page.extract_text() or "")

	return "\n".join(pages)


def extract_text(file_name: str, file_bytes: bytes) -> str:
	lowered = file_name.lower()

	if lowered.endswith(".txt"):
		return extract_text_from_txt(file_bytes)
	if lowered.endswith(".py"):
		return extract_text_from_txt(file_bytes)
	if lowered.endswith(".pdf"):
		return extract_text_from_pdf(file_bytes)

	raise ValueError("Unsupported file type. Use .txt, .py, or .pdf")


def extract_python_chunks_and_graph(code: str, file_name: str) -> tuple[list[str], list[dict[str, object]], dict[str, list[str]]]:
	ast_chunks = extract_python_ast_chunks(file_path=file_name, file_content=code)
	call_graph = extract_call_graph(code)

	chunks = [chunk["chunk_text"] for chunk in ast_chunks]
	chunk_metadata = [
		{
			"name": chunk["name"],
			"type": chunk["type"],
			"file_name": chunk["file_name"],
			"start_line": chunk["start_line"],
			"end_line": chunk["end_line"],
			"called_functions": call_graph.get(chunk["name"], []),
		}
		for chunk in ast_chunks
	]

	return chunks, chunk_metadata, call_graph
