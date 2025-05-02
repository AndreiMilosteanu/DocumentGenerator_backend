import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv, dotenv_values
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv(dotenv_path=".env", override=False)

def get_env_keys(env_path: str = ".env") -> List[str]:
    values = dotenv_values(env_path)
    return list(values.keys())

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    ASSISTANT_ID: str = Field(..., env="ASSISTANT_ID")
    WKHTMLTOPDF_PATH: Path = Field(..., env="WKHTMLTOPDF_PATH")
    DATA_DIR: Path = Field(default=Path("./data"))
    ALLOWED_FILE_TYPES: List[str] = Field(default=[".pdf", ".docx", ".png", ".jpg", ".jpeg"])
    CHAPTERS: List[str] = Field(default=[
        "deklarationsanalyse",
        "bodenuntersuchung",
        "baugrundgutachten",
        "plattendruckversuch"
    ])

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("DATA_DIR", mode="before")
    def ensure_data_dir_exists(cls, v: Path) -> Path:
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

settings = Settings()