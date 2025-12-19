from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv, find_dotenv

# Force reload of environment variables
load_dotenv(override=True)


class Settings(BaseSettings):
    APP_NAME: str = "CMR Bot"
    SETTING_VERSION: str = "0.0.1"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database settings
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_NAME: str = os.getenv("DB_NAME")

    # Authentication settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # API settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY")
    GOOGLE_SEARCH_ENGINE_ID: str = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    GOOGLE_SEARCH_NUM_RESULTS: int = 10
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    
    # SerpAPI settings
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY")

    # NCBI API Key (optional - increases rate limits from 3/sec to 10/sec)
    NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
    
    # Search Provider Limits
    GOOGLE_SCHOLAR_MAX_RESULTS_PER_CALL: int = int(os.getenv("GOOGLE_SCHOLAR_MAX_RESULTS_PER_CALL", "20"))
    PUBMED_MAX_RESULTS_PER_CALL: int = int(os.getenv("PUBMED_MAX_RESULTS_PER_CALL", "10000"))
    
    # Smart Search Filtering Limits
    MAX_ARTICLES_TO_FILTER: int = int(os.getenv("MAX_ARTICLES_TO_FILTER", "500"))

    # Email/SMTP settings
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")

    # Google OAuth2 settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    
    # CORS settings
    CORS_ORIGINS: list[str] = ["*"]  # In production, specify exact origins
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*", "Authorization"]
    CORS_EXPOSE_HEADERS: list[str] = ["Authorization", "X-Request-ID"]

    # Logging settings
    # LOG_LEVEL: str = "DEBUG"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_FILENAME_PREFIX: str = "app"
    LOG_BACKUP_COUNT: int = 10
    LOG_FORMAT: str = "standard"  # Options: "standard" or "json"
    LOG_REQUEST_BODY: bool = False  # Whether to log request bodies
    LOG_RESPONSE_BODY: bool = False  # Whether to log response bodies
    LOG_SENSITIVE_FIELDS: list[str] = ["password", "token", "secret", "key", "authorization"]
    LOG_PERFORMANCE_THRESHOLD_MS: int = 500  # Log slow operations above this threshold


    # Tool Stubbing Settings
    TOOL_STUBBING_ENABLED: bool = os.getenv("TOOL_STUBBING_ENABLED", "false").lower() == "true"
    TOOL_STUBBING_MODE: str = os.getenv("TOOL_STUBBING_MODE", "all")  # Options: "all", "external_only", "none"
    TOOL_STUBBING_DELAY_MS: int = int(os.getenv("TOOL_STUBBING_DELAY_MS", "500"))  # Simulate realistic delays
    TOOL_STUBBING_FAILURE_RATE: float = float(os.getenv("TOOL_STUBBING_FAILURE_RATE", "0.0"))  # 0.0-1.0 for testing error handling

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def anthropic_model(self) -> str:
        """Get the default Anthropic model"""
        return "claude-3-sonnet-20240229"

    @property
    def anthropic_api_key(self) -> str:
        """Get the Anthropic API key"""
        return self.ANTHROPIC_API_KEY

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure API keys are set
        if not self.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not found in environment variables")
        if not self.GOOGLE_SEARCH_API_KEY:
            raise ValueError(
                "GOOGLE_SEARCH_API_KEY not found in environment variables")
        if not self.GOOGLE_SEARCH_ENGINE_ID:
            raise ValueError(
                "GOOGLE_SEARCH_ENGINE_ID not found in environment variables")

        # Validate Google OAuth2 settings
        if not self.GOOGLE_CLIENT_ID:
            raise ValueError("GOOGLE_CLIENT_ID not found in environment variables")
        if not self.GOOGLE_CLIENT_SECRET:
            raise ValueError("GOOGLE_CLIENT_SECRET not found in environment variables")
        if not self.GOOGLE_REDIRECT_URI:
            raise ValueError("GOOGLE_REDIRECT_URI not found in environment variables")
        if not self.FRONTEND_URL:
            raise ValueError("FRONTEND_URL not found in environment variables")

        # Set environment variables
        os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY
        os.environ["GOOGLE_API_KEY"] = self.GOOGLE_SEARCH_API_KEY
        os.environ["GOOGLE_CSE_ID"] = self.GOOGLE_SEARCH_ENGINE_ID



settings = Settings()

# Debug print to verify API keys are loaded
if __name__ == "__main__":
    print(f"OpenAI API Key loaded: {bool(settings.OPENAI_API_KEY)}")
    print(f"Google API Key loaded: {bool(settings.GOOGLE_SEARCH_API_KEY)}")
    print(f"Google CSE ID loaded: {bool(settings.GOOGLE_SEARCH_ENGINE_ID)}")
    print(f"Google OAuth2 Client ID loaded: {bool(settings.GOOGLE_CLIENT_ID)}")
    print(
        f"First few chars of OpenAI key: {settings.OPENAI_API_KEY[:10] if settings.OPENAI_API_KEY else 'No key found'}")
    print(
        f"First few chars of Google key: {settings.GOOGLE_SEARCH_API_KEY[:10] if settings.GOOGLE_SEARCH_API_KEY else 'No key found'}")
