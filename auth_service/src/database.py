"""
База данных для хранения списков пользователей по доменам
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Optional
import logging

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DB_FILE = Path("/app/data/users_db.json")
DB_LOCK_FILE = Path("/app/data/users_db.lock")


class UserDatabase:
    """База данных пользователей по доменам"""
    
    def __init__(self, db_file: Path = DB_FILE):
        self.db_file = db_file
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_database()
    
    def _load_database(self) -> Dict:
        """Загрузить базу данных из файла"""
        if not self.db_file.exists():
            # Создаем структуру по умолчанию
            default_db = {
                "domains": {
                    "aadolgov.com": {
                        "users": [],
                        "description": "Основной домен"
                    },
                    "www.aadolgov.com": {
                        "users": [],
                        "description": "WWW версия основного домена"
                    },
                    "bbspreads.aadolgov.com": {
                        "users": [],
                        "description": "Поддомен для BBSpreads"
                    },
                    "BBSpreads.aadolgov.com": {
                        "users": [],
                        "description": "Поддомен для BBSpreads (с заглавными)"
                    }
                }
            }
            self._save_database(default_db)
            return default_db
        
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка загрузки базы данных: {e}")
            return {"domains": {}}
    
    def _save_database(self, data: Dict):
        """Сохранить базу данных в файл"""
        try:
            # Создаем временный файл для атомарной записи
            temp_file = self.db_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Атомарно заменяем файл
            temp_file.replace(self.db_file)
            logger.debug(f"База данных сохранена: {self.db_file}")
        except IOError as e:
            logger.error(f"Ошибка сохранения базы данных: {e}")
            raise
    
    def get_all_domains(self) -> Dict:
        """Получить все домены и их пользователей"""
        db = self._load_database()
        return db.get("domains", {})
    
    def get_domain_users(self, domain: str) -> List[str]:
        """Получить список пользователей для домена"""
        db = self._load_database()
        domain_data = db.get("domains", {}).get(domain, {})
        return domain_data.get("users", [])
    
    def is_user_allowed(self, domain: str, user_identifier: str) -> bool:
        """Проверить, разрешен ли доступ пользователя к домену"""
        if not user_identifier:
            return False
        users = self.get_domain_users(domain)
        logger.debug(f"Проверка доступа для домена {domain}: user_identifier={user_identifier}, users={users}")
        # Проверяем точное совпадение (регистронезависимо)
        user_identifier_lower = user_identifier.lower()
        result = any(user.lower() == user_identifier_lower for user in users)
        logger.debug(f"Результат проверки доступа: {result}")
        return result
    
    def add_user_to_domain(self, domain: str, yandex_id: str) -> bool:
        """Добавить пользователя к домену"""
        db = self._load_database()
        
        if "domains" not in db:
            db["domains"] = {}
        
        if domain not in db["domains"]:
            db["domains"][domain] = {"users": [], "description": f"Домен {domain}"}
        
        if yandex_id not in db["domains"][domain]["users"]:
            db["domains"][domain]["users"].append(yandex_id)
            self._save_database(db)
            logger.info(f"Пользователь {yandex_id} добавлен к домену {domain}")
            return True
        
        return False
    
    def remove_user_from_domain(self, domain: str, yandex_id: str) -> bool:
        """Удалить пользователя из домена"""
        db = self._load_database()
        
        if domain in db.get("domains", {}):
            if yandex_id in db["domains"][domain]["users"]:
                db["domains"][domain]["users"].remove(yandex_id)
                self._save_database(db)
                logger.info(f"Пользователь {yandex_id} удален из домена {domain}")
                return True
        
        return False
    
    def add_domain(self, domain: str, description: str = "") -> bool:
        """Добавить новый домен"""
        db = self._load_database()
        
        if "domains" not in db:
            db["domains"] = {}
        
        if domain not in db["domains"]:
            db["domains"][domain] = {
                "users": [],
                "description": description or f"Домен {domain}"
            }
            self._save_database(db)
            logger.info(f"Домен {domain} добавлен")
            return True
        
        return False
    
    def remove_domain(self, domain: str) -> bool:
        """Удалить домен"""
        db = self._load_database()
        
        if domain in db.get("domains", {}):
            del db["domains"][domain]
            self._save_database(db)
            logger.info(f"Домен {domain} удален")
            return True
        
        return False


# Глобальный экземпляр базы данных
db = UserDatabase()

