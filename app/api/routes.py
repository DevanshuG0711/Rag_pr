from pathlib import Path

from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile

from app.services.chunking import chunk_text
from app.services.ingest import extract_text

router = APIRouter(prefix="/api")
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/ingest")
async def ingest_document(
	file: UploadFile = File(...),
	chunk_size: int = Query(default=500, ge=1),
	overlap: int = Query(default=50, ge=0),
) -> dict[str, object]:
	file_bytes = await file.read()

	if not file_bytes:
		raise HTTPException(status_code=400, detail="Empty file uploaded")

	file_name = file.filename or "uploaded_file"
	file_path = UPLOAD_DIR / file_name
	file_path.write_bytes(file_bytes)

	try:
		text = extract_text(file_name=file_name, file_bytes=file_bytes)
		chunks = chunk_text(text=text, chunk_size=chunk_size, overlap=overlap)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to parse document") from exc

	return {
		"filename": file_name,
		"characters": len(text),
		"chunk_size": chunk_size,
		"overlap": overlap,
		"chunk_count": len(chunks),
		"chunks": chunks,
		"text": text,
	}
