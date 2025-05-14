import os
from pathlib import Path
from typing import List, Dict, Optional
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
    ASSISTANT_ID: str = Field(..., env="ASSISTANT_ID")  # Default assistant ID
    WKHTMLTOPDF_PATH: Path = Field(..., env="WKHTMLTOPDF_PATH")
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATA_DIR: Path = Field(default=Path("./data"))
    ALLOWED_FILE_TYPES: List[str] = Field(default=[".pdf", ".docx", ".png", ".jpg", ".jpeg"])
    
    # Optional assistant IDs for specific topics
    DEKLARATIONSANALYSE_ASSISTANT_ID: Optional[str] = Field(default=None, env="DEKLARATIONSANALYSE_ASSISTANT_ID")
    BODENUNTERSUCHUNG_ASSISTANT_ID: Optional[str] = Field(default=None, env="BODENUNTERSUCHUNG_ASSISTANT_ID")
    BAUGRUNDGUTACHTEN_ASSISTANT_ID: Optional[str] = Field(default=None, env="BAUGRUNDGUTACHTEN_ASSISTANT_ID")
    PLATTENDRUCKVERSUCH_ASSISTANT_ID: Optional[str] = Field(default=None, env="PLATTENDRUCKVERSUCH_ASSISTANT_ID")
    
    # Topic to assistant ID mapping (computed property)
    @property
    def TOPIC_ASSISTANTS(self) -> Dict[str, str]:
        return {
            "Deklarationsanalyse": self.DEKLARATIONSANALYSE_ASSISTANT_ID or self.ASSISTANT_ID,
            "Bodenuntersuchung": self.BODENUNTERSUCHUNG_ASSISTANT_ID or self.ASSISTANT_ID,
            "Baugrundgutachten": self.BAUGRUNDGUTACHTEN_ASSISTANT_ID or self.ASSISTANT_ID,
            "Plattendruckversuch": self.PLATTENDRUCKVERSUCH_ASSISTANT_ID or self.ASSISTANT_ID
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("DATA_DIR", mode="before")
    def ensure_data_dir_exists(cls, v: Path) -> Path:
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

settings = Settings()