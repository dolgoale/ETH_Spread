"""
Интеграция с Yandex OAuth
"""
import httpx
import logging
import urllib.parse
from typing import Optional, Dict
from .config import settings

logger = logging.getLogger(__name__)


class YandexOAuth:
    """Класс для работы с Yandex OAuth"""
    
    OAUTH_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
    OAUTH_TOKEN_URL = "https://oauth.yandex.ru/token"
    USER_INFO_URL = "https://login.yandex.ru/info"
    
    def __init__(self):
        self.client_id = settings.yandex_client_id
        self.client_secret = settings.yandex_client_secret
        self.redirect_uri = settings.yandex_redirect_uri
    
    def get_authorize_url(self, state: str = "") -> str:
        """Получить URL для авторизации"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state
        
        # Правильное кодирование URL параметров
        query_string = urllib.parse.urlencode(params)
        return f"{self.OAUTH_AUTHORIZE_URL}?{query_string}"
    
    async def get_token(self, code: str) -> Optional[Dict]:
        """Получить токен доступа по коду авторизации"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.OAUTH_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Ошибка получения токена: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Исключение при получении токена: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Получить информацию о пользователе"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.USER_INFO_URL,
                    headers={"Authorization": f"OAuth {access_token}"}
                )
                
                if response.status_code == 200:
                    user_info = response.json()
                    # Yandex возвращает id как строку, но может быть и числом
                    # Также проверяем login (имя пользователя) как альтернативу
                    yandex_id = str(user_info.get("id", ""))
                    login = user_info.get("login", "")
                    user_info["yandex_id"] = yandex_id
                    user_info["login"] = login
                    logger.info(f"Получена информация от Yandex: id={yandex_id}, login={login}, email={user_info.get('default_email', '')}")
                    return user_info
                else:
                    logger.error(f"Ошибка получения информации о пользователе: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Исключение при получении информации о пользователе: {e}")
            return None


yandex_oauth = YandexOAuth()

