""" REST API route from backend """

from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from decision_data.backend.data.reddit import RedditScraper
from decision_data.data_structure.models import Story

app = FastAPI(title="Decision Stories API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stories", response_model=List[Story])
async def get_stories(
    source: str = Query("reddit", enum=["reddit"]),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    subreddit: Optional[str] = None,
):
    """API route for getting reddit data back in a json format"""

    if source == "reddit":
        if not subreddit:
            subreddit = "decision"
        scraper = RedditScraper()
        stories = scraper.fetch_stories(subreddit_name=subreddit, limit=limit)
        return stories
    else:
        raise HTTPException(status_code=400, detail="Source not supported")
