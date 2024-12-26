import pytest
from unittest.mock import patch, MagicMock
from decision_data.backend.data.reddit import RedditScraper
from decision_data.backend.config.config import backend_config


@pytest.fixture
def mock_reddit_client():
    with patch("praw.Reddit") as mock:
        yield mock


def test_reddit_scraper_initialization(mock_reddit_client):
    # Arrange
    mock_reddit_instance = MagicMock()
    mock_reddit_client.return_value = mock_reddit_instance

    # Act
    scraper = RedditScraper()

    # Assert
    mock_reddit_client.assert_called_once_with(
        client_id=backend_config.REDDIT_CLIENT_ID,
        client_secret=backend_config.REDDIT_CLIENT_SECRET,
        user_agent=backend_config.REDDIT_USER_AGENT,
    )
    assert scraper.reddit == mock_reddit_instance
