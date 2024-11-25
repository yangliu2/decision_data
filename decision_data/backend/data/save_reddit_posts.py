"""
This module provides functionality to fetch stories from Reddit and save them
to a MongoDB database. It utilizes the RedditScraper to retrieve stories and
the MongoDBClient to handle database operations. The script can be executed
directly to perform the save operation with a specified number of posts.
"""

import sys
from decision_data.backend.data.reddit import RedditScraper
from decision_data.backend.data.mongodb_client import MongoDBClient
from loguru import logger


def save_reddit_story_to_mongo(num_posts: int = 10) -> None:
    """
    Fetch stories from Reddit and save them to MongoDB.

    This function initializes the RedditScraper to fetch a specified number of
    stories from Reddit. It then converts these stories into dictionaries and
    uses the MongoDBClient to insert them into the MongoDB collection. After
    the insertion, it closes the MongoDB connection.

    Args:
        num_posts (int, optional): The number of Reddit posts to fetch and
        save.
            Must be a positive integer. Defaults to 10.

    Raises:
        ValueError: If num_posts is not a positive integer.

    Example:
        >>> save_reddit_story_to_mongo(20)
        INFO - Number of stories fetched: 20
        INFO - Inserted 20 stories into MongoDB.
    """
    if num_posts <= 0:
        raise ValueError("num_posts must be a positive integer.")

    # Initialize Reddit scraper
    scraper = RedditScraper()
    stories = scraper.fetch_stories(limit=num_posts)

    logger.info(f"Number of stories fetched: {len(stories)}")

    # Convert stories to dictionaries for MongoDB
    try:
        stories_dicts = [story.dict() for story in stories]
    except AttributeError as e:
        logger.error(f"Error converting stories to dictionaries: {e}")
        return

    # Initialize MongoDB client
    mongo_client = MongoDBClient()

    # Insert stories into MongoDB
    mongo_client.insert_stories(stories_dicts)

    # Close MongoDB connection
    mongo_client.close()


def main(num_posts: int) -> None:
    """
    Main function to execute the save operation.

    This function serves as the entry point for the script. It calls the
    save_reddit_story_to_mongo function with the provided number of posts.

    Args:
        num_posts (int): The number of Reddit posts to fetch and save.

    Example:
        >>> main(15)
    """
    try:
        save_reddit_story_to_mongo(num_posts)
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        sys.exit(1)


if __name__ == "__main__":
    """
    Execute the script to fetch and save Reddit stories.

    This block parses command-line arguments to determine the number of posts
    to fetch. If no argument is provided, it defaults to 10 posts. It then
    calls the main function with the specified number of posts.

    Usage:
        python script_name.py [num_posts]

    Examples:
        python script_name.py
        python script_name.py 25
    """
    # Parameterize the number of posts
    if len(sys.argv) > 1:
        try:
            num_posts = int(sys.argv[1])
            if num_posts <= 0:
                raise ValueError
        except ValueError:
            logger.info(
                "Please provide a valid positive integer for the number of posts."
            )
            sys.exit(1)
    else:
        num_posts = 10  # Default value

    main(num_posts)
