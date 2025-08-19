"""
BiPay Configuration Settings - SIMPLIFIED
"""

from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Application Settings
    app_name: str = "BiPay"
    version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000

    # Security
    secret_key: str = "bipay-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Database - Using a public demo MongoDB (replace with your own)
    mongodb_url: str = "mongodb+srv://demo:demo123@cluster0.example.mongodb.net"
    database_name: str = "bipay_db"

    # Biometric Settings
    fingerprint_threshold: float = 80.0
    fingerprint_timeout: int = 30

    # Blockchain Settings
    mining_reward: float = 10.0
    blockchain_difficulty: int = 4

    # AI Settings
    anomaly_contamination: float = 0.1
    anomaly_threshold: float = 0.5

    # CORS Settings
    allowed_origins: List[str] = ["*"]  # Allow all origins for now
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
