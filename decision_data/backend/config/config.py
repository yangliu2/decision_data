""" Config parameters in pydantic settings format """

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseSettings):

    backend_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


backend_config = BackendConfig()
