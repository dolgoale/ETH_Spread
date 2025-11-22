"""
Управление сессиями пользователей
"""
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from .config import settings
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Менеджер сессий пользователей"""
    
    def __init__(self):
        self.secret_key = settings.secret_key.encode('utf-8')
        self.cookie_name = settings.session_cookie_name
        self.expire_hours = settings.session_expire_hours
    
    def create_session(self, yandex_id: str, email: str, name: str, domain: str, login: str = "") -> str:
        """Создать сессию для пользователя"""
        session_data = {
            "yandex_id": yandex_id,
            "email": email,
            "name": name,
            "domain": domain,
            "login": login,  # Сохраняем login для проверки доступа
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=self.expire_hours)).isoformat()
        }
        
        # Кодируем данные в base64
        data_json = json.dumps(session_data)
        data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        
        # Создаем подпись
        signature = self._create_signature(data_encoded)
        
        # Объединяем данные и подпись
        session_token = f"{data_encoded}.{signature}"
        
        return session_token
    
    def verify_session(self, session_token: str) -> Optional[Dict]:
        """Проверить и декодировать сессию"""
        try:
            if '.' not in session_token:
                return None
            
            data_encoded, signature = session_token.rsplit('.', 1)
            
            # Проверяем подпись
            expected_signature = self._create_signature(data_encoded)
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Неверная подпись сессии")
                return None
            
            # Декодируем данные
            data_json = base64.b64decode(data_encoded.encode('utf-8')).decode('utf-8')
            session_data = json.loads(data_json)
            
            # Проверяем срок действия
            expires_at = datetime.fromisoformat(session_data.get("expires_at", ""))
            if datetime.now() > expires_at:
                logger.debug("Сессия истекла")
                return None
            
            return session_data
        except Exception as e:
            logger.error(f"Ошибка проверки сессии: {e}")
            return None
    
    def _create_signature(self, data: str) -> str:
        """Создать подпись для данных"""
        signature = hmac.new(
            self.secret_key,
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature


session_manager = SessionManager()

