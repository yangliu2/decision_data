""" Config parameters in pydantic settings format """

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseSettings):

    # prompt path
    DAILY_SUMMAYR_PROMPT_PATH: str = "decision_data/prompts/daily_summary.txt"

    # Reddit setting
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = ""

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

    # DynamoDB Tables
    USERS_TABLE: str = "panzoto-users"
    AUDIO_FILES_TABLE: str = "panzoto-audio-files"

    # Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Stripe Payment Processing
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""  # Get this from Stripe Dashboard after creating webhook

    # Frontend URL for Stripe redirects
    FRONTEND_URL: str = "panzoto://payment"  # Android deep link

    # Email Configuration (AWS SES)
    EMAIL_SENDER: str = "support@panzoto.com"

    # Daily summary time
    DAILY_SUMMARY_HOUR: int = 17
    TIME_OFFSET_FROM_UTC: int = -6
    DAILY_RESET_HOUR: int = 2
    TRANSCRIBER_INTERVAL: int = 60

    # Transcription Safety Limits
    TRANSCRIPTION_MAX_FILE_SIZE_MB: float = 5.0  # 5MB max file size
    TRANSCRIPTION_TIMEOUT_MINUTES: int = 5  # 5 minute processing timeout
    TRANSCRIPTION_MAX_RETRIES: int = 3  # Maximum retry attempts per file
    TRANSCRIPTION_RETRY_BACKOFF_MINUTES: int = 10  # Minutes between retries
    TRANSCRIPTION_RATE_LIMIT_PER_MINUTE: int = 5  # API calls per minute per user
    TRANSCRIPTION_CHECK_INTERVAL_SECONDS: int = 60  # Background processor check interval
    TRANSCRIPTION_MAX_DURATION_SECONDS: int = 300  # 5 minutes max audio length
    TRANSCRIPTION_MIN_DURATION_SECONDS: int = 3  # 3 seconds min audio length

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


backend_config = BackendConfig()
