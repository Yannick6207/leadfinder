import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'leadfinder.db').as_posix()}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BUSINESS_PROVIDER = os.getenv("BUSINESS_PROVIDER", "mock")
    DEFAULT_PROVINCE = os.getenv("DEFAULT_PROVINCE", "Gelderland")
    DEFAULT_RESULTS_LIMIT = int(os.getenv("DEFAULT_RESULTS_LIMIT", "10"))
    WEBSITE_TIMEOUT = float(os.getenv("WEBSITE_TIMEOUT", "5"))
    GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
    PLACES_TIMEOUT = float(os.getenv("PLACES_TIMEOUT", "10"))
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    BUSINESS_PROVIDER = "mock"
    GOOGLE_PLACES_API_KEY = ""
