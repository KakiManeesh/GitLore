from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_groq import ChatGroq
from pydantic import BaseModel

from backend.agent.agent import AgenticRagSystem
from backend.config import config
from backend.ingestion.ingestion_manager import IngestionManager

app = FastAPI(title="GitLore API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ingestion_manager = IngestionManager()


class RepositoryIndexRequest(BaseModel):
    repository_url: str


class QueryRequest(BaseModel):
    repository_id: str
    query: str


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/repositories")
async def list_repositories():
    return {"repositories": ingestion_manager.list_indexed_repositories()}


@app.post("/repositories/index")
async def index_repository(req: RepositoryIndexRequest):
    try:
        return ingestion_manager.index_repository(req.repository_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query")
async def query_endpoint(req: QueryRequest):
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured.")

    model = ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=config.GROQ_MODEL,
        temperature=config.GROQ_TEMPERATURE,
    )

    try:
        return AgenticRagSystem(model, req.repository_id).query(req.query)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
