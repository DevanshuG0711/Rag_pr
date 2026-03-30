from pathlib import Path

from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile

from app.services.ingest import extract_text

router = APIRouter(prefix="/api")
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)) -> dict[str, str | int]:
	file_bytes = await file.read()

	if not file_bytes:
		raise HTTPException(status_code=400, detail="Empty file uploaded")

	file_name = file.filename or "uploaded_file"
	file_path = UPLOAD_DIR / file_name
	file_path.write_bytes(file_bytes)

	try:
		text = extract_text(file_name=file_name, file_bytes=file_bytes)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to parse document") from exc

	return {
		"filename": file_name,
		"characters": len(text),
		"text": text,
	}
