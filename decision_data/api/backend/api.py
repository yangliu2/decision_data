""" REST API route from backend """

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from decision_data.backend.data.reddit import RedditScraper
from decision_data.data_structure.models import Story
from decision_data.backend.data.save_reddit_posts import main

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


@app.post("/api/save_stories")
async def save_stories_endpoint(
    background_tasks: BackgroundTasks,
    num_posts: int = Query(10, ge=1, le=1000),
):
    background_tasks.add_task(save_stories_task, num_posts)
    return {"message": "Saving stories in the background."}


def save_stories_task(num_posts):
    main(num_posts)
