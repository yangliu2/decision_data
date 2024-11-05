""" Config parameters in pydantic settings format """

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseSettings):

    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


backend_config = BackendConfig()
