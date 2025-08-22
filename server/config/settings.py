import os
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Keys
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
    
    # App Configuration
    app_name: str = "Floorplan Extractor"
    app_version: str = "5.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS Configuration
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://yourdomain.com"
    ]
    
    # File Upload Configuration
    max_file_size_mb: int = 10
    allowed_file_types: List[str] = [".pdf"]
    
    # Image Processing Configuration
    default_dpi: int = 400
    high_res_dpi: int = 400
    normal_dpi: int = 300
    max_image_dimension: int = 2048
    
    # Gemini Configuration
    gemini_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.1
    
    # Processing Configuration
    overlap_pixels: int = 50
    poor_results_threshold: int = 10
    
    class Config:
        env_file = ".env"

# Global settings instance
settings = Settings()