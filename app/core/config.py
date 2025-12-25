from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoOps Agent"
    SUPABASE_URL: str
    SUPABASE_KEY: str
    OPENAI_API_KEY: str  # <--- We added this line!

    class Config:
        env_file = ".env"
        # This tells Pydantic: "If you find other variables in .env that I didn't ask for, just ignore them, don't crash."
        extra = "ignore" 

settings = Settings()