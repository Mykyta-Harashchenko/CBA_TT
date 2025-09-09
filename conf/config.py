import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    DB_URL: str = os.environ.get("DB_URL")
    DB_TEST_URL: Optional[str] = os.environ.get("DB_TEST_URL")
    SECRET_KEY_JWT: str = os.environ.get("SECRET_KEY_JWT")
    ALGORITHM: str = os.environ.get('ALGORITHM')



    class Config:
        env_file = "Test_Task_CBA-1/.env"
        env_file_encoding = "utf-8"



config = Settings()
