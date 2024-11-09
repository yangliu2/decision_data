""" Using web scrapper to get decision stories from Reddit"""

from abc import ABC, abstractmethod
import praw
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import Story


class DecisionScraper(ABC):
    """Abstraction class for web scrapper that can be used for typing

    :param ABC: base class type
    :type ABC: abstract class
    """

    @abstractmethod
    def fetch_stories(self):
        pass


class RedditScraper(DecisionScraper):
    """Reddit scrapper to get data from a sub reddit

    :param DecisionScraper: base abstraction class
    :type DecisionScraper: base class for typing
    """

    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=backend_config.REDDIT_CLIENT_ID,
            client_secret=backend_config.REDDIT_CLIENT_SECRET,
            user_agent=backend_config.REDDIT_USER_AGENT,
        )

    def fetch_stories(self, subreddit_name="decision", limit=None):
        subreddit = self.reddit.subreddit(subreddit_name)
        stories = []
        try:
            # Use subreddit.new() to get the newest posts
            submissions = subreddit.new(
                limit=limit
            )  # limit=None fetches as many as possible (up to 1,000)
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
