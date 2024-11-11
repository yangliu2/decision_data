""" Config parameters in pydantic settings format """

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseSettings):

    # Reddit setting
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = ""

    # MongoDB settings
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = ""
    MONGODB_COLLECTION_NAME: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


backend_config = BackendConfig()
