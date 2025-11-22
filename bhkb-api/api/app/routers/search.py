from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from app.db.session import get_pool # type: ignore
from app.services.search import keyword_search

router = APIRouter()

class SearchResponseItem(BaseModel):
    chunk_id: int
    text: str

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResponseItem] = Field(default_factory=list, description="List of search results")

@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=3, max_length=100, description="Search query string"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return"),
    pool=Depends(get_pool)
):
    """
    Perform a keyword search on document chunks using full-text search.

    Args:
        q (str): The search query string.
        limit (int, optional): The maximum number of results to return. Defaults to 10.
        pool (AsyncConnectionPool): The database connection pool, injected by FastAPI.

    Returns:
        SearchResponse: The search response containing the query and list of results.
    """
    results = await keyword_search(pool, q, limit)
    return SearchResponse(query=q, results=[SearchResponseItem(**r) for r in results])
