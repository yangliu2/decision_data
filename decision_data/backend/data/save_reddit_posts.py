# decision_data/backend/data/save_reddit_posts.py

import sys
from decision_data.backend.data.reddit import RedditScraper
from decision_data.backend.data.mongodb_client import MongoDBClient
from loguru import logger


def save_reddit_story_to_mongo(num_posts: int = 10):
    # Initialize Reddit scraper
    scraper = RedditScraper()
    stories = scraper.fetch_stories(limit=num_posts)

    logger.info(f"Number of stories fetched: {len(stories)}")

    # Convert stories to dictionaries for MongoDB
    stories_dicts = [story.dict() for story in stories]

    # Initialize MongoDB client
    mongo_client = MongoDBClient()

    # Insert stories into MongoDB
    mongo_client.insert_stories(stories_dicts)

    # Close MongoDB connection
    mongo_client.close()


def main():
    save_reddit_story_to_mongo(num_posts)


if __name__ == "__main__":
    # Parameterize the number of posts
    if len(sys.argv) > 1:
        try:
            num_posts = int(sys.argv[1])
        except ValueError:
            print("Please provide a valid integer for the number of posts.")
            sys.exit(1)
    else:
        num_posts = 10  # Default value

    main()
