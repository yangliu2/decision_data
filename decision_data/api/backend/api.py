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
    limit: int = Query(10, ge=1, le=100),
    after: Optional[str] = None,
    subreddit: Optional[str] = None,
):
    """API route for getting reddit data back in a json format

    :param source: Query object determine the data source, defaults to
    Query("reddit", enum=["reddit"])
    :type source: str, optional
    :param limit: Query object that indicate parameters, defaults to
    Query(10, ge=1, le=100)
    :type limit: int, optional
    :param after: how many post to get, defaults to None
    :type after: Optional[str], optional
    :param subreddit: which subreddit board to go, defaults to None
    :type subreddit: Optional[str], optional
    :raises HTTPException: when failed raise http exception
    :return: _description_
    :rtype: List[Story], json format
    """
    if source == "reddit":
        if not subreddit:
            subreddit = "decisions"
        scraper = RedditScraper()
        stories = scraper.fetch_stories(
            subreddit_name=subreddit, limit=limit, after=after
        )
        return stories
    else:
        raise HTTPException(status_code=400, detail="Source not supported")
