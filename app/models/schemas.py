from pydantic import BaseModel
from pydantic import Field


class QueryRequest(BaseModel):
	query: str = Field(min_length=1)
	top_k: int = Field(default=5, ge=1)


class RetrievedChunk(BaseModel):
	id: str
	score: float
	file_name: str | None = None
	chunk_index: int | None = None
	chunk_text: str | None = None


class QueryResponse(BaseModel):
	query: str
	answer: str
	retrieved_chunks: list[RetrievedChunk]
