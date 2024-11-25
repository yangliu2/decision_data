""" Using web scrapper to get decision stories from Reddit"""

from abc import ABC, abstractmethod
import praw
from typing import List
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


class RedditScraper:
    """
    A scraper for fetching stories from Reddit using the PRAW (Python Reddit
    API Wrapper).

    This class initializes a Reddit instance using credentials from the backend
    configuration and provides methods to fetch recent stories from a specified
    subreddit.
    """

    def __init__(self):
        """
        Initialize the RedditScraper instance by creating a Reddit client.

        The Reddit client is configured using the following credentials from
        the backend configuration:
            - client_id
            - client_secret
            - user_agent

        Raises:
            praw.exceptions.PRAWException: If there is an issue initializing
                the Reddit client.
        """
        self.reddit = praw.Reddit(
            client_id=backend_config.REDDIT_CLIENT_ID,
            client_secret=backend_config.REDDIT_CLIENT_SECRET,
            user_agent=backend_config.REDDIT_USER_AGENT,
        )

    def fetch_stories(
        self,
        subreddit_name: str = "DecisionMaking",
        limit: int = 10,
    ) -> List[Story]:
        """
        Fetch the latest stories from a specified subreddit.

        This method retrieves the most recent submissions from the given
        subreddit, excluding stickied posts. Each submission is converted
        into a `Story` object containing relevant details.

        Args:
            subreddit_name (str, optional): The name of the subreddit to
                fetch stories from. Defaults to "DecisionMaking".
            limit (int, optional): The maximum number of stories to fetch.
                Defaults to 10.

        Returns:
            List[Story]: A list of `Story` objects containing details of
                each fetched submission. Returns an empty list if an error
                occurs during fetching.

        Example:
            scraper = RedditScraper()
            stories = scraper.fetch_stories(subreddit_name="Python", limit=5)
            for story in stories:
                print(story.title, story.url)

        Raises:
            Exception: Catches any exception that occurs during the fetching
                process, prints an error message, and returns an empty list.
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        stories = []
        try:
            submissions = subreddit.new(limit=limit)
            for submission in submissions:
                author = submission.author.name if submission.author else None
                if not submission.stickied:
                    story = Story(
                        id=submission.id,
                        title=submission.title,
                        content=submission.selftext,
                        url=submission.url,
                        score=submission.score,
                        comments=submission.num_comments,
                        created_utc=submission.created_utc,
                        author=author,
                    )
                    stories.append(story)
            return stories
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
