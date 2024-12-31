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
    MONGODB_REDDIT_COLLECTION_NAME: str = ""
    MONGODB_TRANSCRIPTS_COLLECTION_NAME: str = ""

    # openai
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    REGION_NAME: str = ""

    # AWS Dynamo DB keys
    AWS_S3_BUCKET_NAME: str = "panzoto"
    AWS_S3_AUDIO_FOLDER: str = "audio_upload"
    AWS_S3_TRANSCRIPT_FOLDER: str = "transcripts"

    # Google voice
    GOOGLE_APP_PASSWORD: str = ""
    PHONE_NUMBER: str = ""
    GMAIL_ACCOUNT: str = ""

    # Daily summary time
    DAILY_SUMMARY_HOUR: int = 17
    TIME_OFFSET: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


backend_config = BackendConfig()
