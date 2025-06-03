import os
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv, dotenv_values
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
import logging

# Load environment variables
load_dotenv(dotenv_path=".env", override=False)

def get_env_keys(env_path: str = ".env") -> List[str]:
    values = dotenv_values(env_path)
    return list(values.keys())

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    ASSISTANT_ID: Optional[str] = Field(default=None, env="ASSISTANT_ID")
    WKHTMLTOPDF_PATH: Path = Field(..., env="WKHTMLTOPDF_PATH")
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATA_DIR: Path = Field(default=Path("./data"))
    ALLOWED_FILE_TYPES: List[str] = Field(default=[".pdf", ".docx", ".png", ".jpg", ".jpeg"])
    GPT_MODEL: str = Field(default="gpt-4-turbo", env="GPT_MODEL")  # Default to GPT-4 Turbo for better extraction capabilities
    
    # JWT settings
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30 * 24 * 60)  # 30 days
    
    # Optional assistant IDs for specific topics
    DEKLARATIONSANALYSE_ASSISTANT_ID: Optional[str] = Field(default=None, env="DEKLARATIONSANALYSE_ASSISTANT_ID")
    BODENUNTERSUCHUNG_ASSISTANT_ID: Optional[str] = Field(default=None, env="BODENUNTERSUCHUNG_ASSISTANT_ID")
    BAUGRUNDGUTACHTEN_ASSISTANT_ID: Optional[str] = Field(default=None, env="BAUGRUNDGUTACHTEN_ASSISTANT_ID")
    PLATTENDRUCKVERSUCH_ASSISTANT_ID: Optional[str] = Field(default=None, env="PLATTENDRUCKVERSUCH_ASSISTANT_ID")
    
    # Topic to assistant ID mapping (computed property)
    @property
    def TOPIC_ASSISTANTS(self) -> Dict[str, str]:
        fallback_id = self.ASSISTANT_ID
        if not fallback_id:
            fallback_id = next((aid for aid in [
                self.DEKLARATIONSANALYSE_ASSISTANT_ID,
                self.BODENUNTERSUCHUNG_ASSISTANT_ID,
                self.BAUGRUNDGUTACHTEN_ASSISTANT_ID,
                self.PLATTENDRUCKVERSUCH_ASSISTANT_ID
            ] if aid), None)
        
        # Debug logging
        logger = logging.getLogger("config")
        logger.info(f"Loading assistant IDs:")
        logger.info(f"Default ASSISTANT_ID: {self.ASSISTANT_ID}")
        logger.info(f"DEKLARATIONSANALYSE_ASSISTANT_ID: {self.DEKLARATIONSANALYSE_ASSISTANT_ID}")
        logger.info(f"BODENUNTERSUCHUNG_ASSISTANT_ID: {self.BODENUNTERSUCHUNG_ASSISTANT_ID}")
        logger.info(f"BAUGRUNDGUTACHTEN_ASSISTANT_ID: {self.BAUGRUNDGUTACHTEN_ASSISTANT_ID}")
        logger.info(f"PLATTENDRUCKVERSUCH_ASSISTANT_ID: {self.PLATTENDRUCKVERSUCH_ASSISTANT_ID}")
        logger.info(f"Using fallback_id: {fallback_id}")
        
        assistants = {
            "Deklarationsanalyse": self.DEKLARATIONSANALYSE_ASSISTANT_ID or fallback_id,
            "Bodenuntersuchung": self.BODENUNTERSUCHUNG_ASSISTANT_ID or fallback_id,
            "Baugrundgutachten": self.BAUGRUNDGUTACHTEN_ASSISTANT_ID or fallback_id,
            "Plattendruckversuch": self.PLATTENDRUCKVERSUCH_ASSISTANT_ID or fallback_id
        }
        
        # Log final mapping
        logger.info("Final assistant mapping:")
        for topic, aid in assistants.items():
            logger.info(f"{topic}: {aid}")
        
        return assistants

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("DATA_DIR", mode="before")
    def ensure_data_dir_exists(cls, v: Path) -> Path:
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

settings = Settings()