"""
Конфигурация сервиса авторизации
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Настройки сервиса авторизации"""
    
    # Yandex OAuth Configuration
    yandex_client_id: str = os.getenv("YANDEX_CLIENT_ID", "")
    yandex_client_secret: str = os.getenv("YANDEX_CLIENT_SECRET", "")
    yandex_redirect_uri: str = os.getenv("YANDEX_REDIRECT_URI", "https://aadolgov.com/auth/callback")
    
    # Session Configuration
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "auth_session")
    session_cookie_httponly: bool = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    session_cookie_samesite: str = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
    session_expire_hours: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))
    
    # Server Configuration
    auth_server_host: str = os.getenv("AUTH_SERVER_HOST", "0.0.0.0")
    auth_server_port: int = int(os.getenv("AUTH_SERVER_PORT", "9000"))
    
    # Admin Configuration
    admin_yandex_id: str = os.getenv("ADMIN_YANDEX_ID", "")


settings = Settings()

