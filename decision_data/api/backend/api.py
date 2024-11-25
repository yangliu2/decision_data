from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from decision_data.backend.data.reddit import RedditScraper
from decision_data.data_structure.models import Story
from decision_data.backend.data.save_reddit_posts import (
    save_reddit_story_to_mongo,
)

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
    """
    Retrieve stories from a specified data source.

    This endpoint fetches the latest stories from Reddit based on the provided
    subreddit and limit parameters. The stories are returned in JSON format.

    Args:
        source (str, optional): The data source to fetch stories from.
            Currently, only "reddit" is supported. Defaults to "reddit".
        limit (int, optional): The maximum number of stories to retrieve.
            Must be between 1 and 1000. Defaults to None.
        subreddit (str, optional): The name of the subreddit to fetch stories
            from. If not provided, defaults to "decision".

    Returns:
        List[Story]: A list of Story objects containing the fetched stories.

    Raises:
        HTTPException: If the provided source is not supported, a 400 error
            is raised with an appropriate message.

    Example:
        ```python
        import requests

        response = requests.get(
            "http://localhost:8000/api/stories",
            params={"source": "reddit", "limit": 5, "subreddit": "Python"}
        )
        stories = response.json()
        for story in stories:
            print(story['title'], story['url'])
        ```
    """
    if source == "reddit":
        if not subreddit:
            subreddit = "decision"
        scraper = RedditScraper()

        # Ensure 'limit' is an int. If 'limit' is None, use the default value
        # 10.
        actual_limit = limit if limit is not None else 10

        stories = scraper.fetch_stories(
            subreddit_name=subreddit,
            limit=actual_limit,
        )
        return stories
    else:
        raise HTTPException(status_code=400, detail="Source not supported")


@app.post("/api/save_stories")
async def save_stories_endpoint(
    background_tasks: BackgroundTasks,
    num_posts: int = Query(10, ge=1, le=1000),
):
    """
    Initiate background task to save Reddit stories to MongoDB.

    This endpoint triggers a background task that fetches a specified number
    of Reddit posts and saves them to a MongoDB database. The operation is
    performed asynchronously to ensure that the API remains responsive.

    Args:
        background_tasks (BackgroundTasks): A FastAPI BackgroundTasks instance
            used to manage background operations.
        num_posts (int, optional): The number of Reddit posts to fetch and
            save. Must be between 1 and 1000. Defaults to 10.

    Returns:
        dict: A confirmation message indicating that the saving process has
            been initiated.

    Example:
        ```python
        import requests

        response = requests.post(
            "http://127.0.0.1:8000/api/save_stories",
            params={"num_posts": 50}
        )
        print(response.json())  # Output: {"message": "Saving stories in the
        background."}
        ```
    """
    background_tasks.add_task(save_reddit_story_to_mongo, num_posts)
    return {"message": "Saving stories in the background."}
