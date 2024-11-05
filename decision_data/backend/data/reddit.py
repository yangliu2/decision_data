""" Using web scrapper to get decision stories from Reddit"""

from abc import ABC, abstractmethod
from typing import List
import praw
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import Story


class DecisionScraper(ABC):
    @abstractmethod
    def fetch_stories(self):
        pass


class RedditScraper(DecisionScraper):
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=backend_config.REDDIT_CLIENT_ID,
            client_secret=backend_config.REDDIT_CLIENT_SECRET,
            user_agent=backend_config.REDDIT_USER_AGENT,
        )

    def fetch_stories(
        self,
        subreddit_name="decisions",
        limit=10,
        after=None,
    ) -> List[Story]:
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            stories = []
            submissions = subreddit.top(limit=limit, params={"after": after})
            for submission in submissions:
                if not submission.stickied:
                    story = Story(
                        title=submission.title,
                        content=submission.selftext,
                        url=submission.url,
                        score=submission.score,
                        comments=submission.num_comments,
                    )
                    stories.append(story)
            return stories
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
