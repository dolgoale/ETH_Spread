"""
Конфигурация приложения с поддержкой динамического изменения
"""
import os
import json
import threading
import shutil
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Путь к файлу динамической конфигурации
CONFIG_FILE = Path("config.json")
_config_lock = threading.Lock()


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # ByBit API (только чтение, не изменяются через веб-интерфейс)
    bybit_api_key: str = os.getenv("BYBIT_API_KEY", "")
    bybit_api_secret: str = os.getenv("BYBIT_API_SECRET", "")
    bybit_testnet: bool = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    
    # Telegram Bot (только чтение, не изменяются через веб-интерфейс)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Monitoring (изменяемые через веб-интерфейс)
    spread_threshold_percent: float = float(os.getenv("SPREAD_THRESHOLD_PERCENT", "0.5"))
    funding_rate_history_days: int = int(os.getenv("FUNDING_RATE_HISTORY_DAYS", "7"))
    monitoring_interval_seconds: int = int(os.getenv("MONITORING_INTERVAL_SECONDS", "5"))
    return_on_capital_threshold: float = float(os.getenv("RETURN_ON_CAPITAL_THRESHOLD", "50.0"))
    capital_usdt: float = float(os.getenv("CAPITAL_USDT", "50000"))
    leverage: int = int(os.getenv("LEVERAGE", "20"))
    
    # Web Server
    web_server_host: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    web_server_port: int = int(os.getenv("WEB_SERVER_PORT", "8000"))
    
    # Symbols (изменяемые через веб-интерфейс)
    perpetual_symbol: str = os.getenv("PERPETUAL_SYMBOL", "ETHUSDT")
    # Символы срочных фьючерсов теперь получаются динамически через get_available_futures
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь для API"""
        return {
            "spread_threshold_percent": self.spread_threshold_percent,
            "funding_rate_history_days": self.funding_rate_history_days,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "return_on_capital_threshold": self.return_on_capital_threshold,
            "capital_usdt": self.capital_usdt,
            "leverage": self.leverage,
            "perpetual_symbol": self.perpetual_symbol,
            "web_server_host": self.web_server_host,
            "web_server_port": self.web_server_port,
        }
    
    def update_from_dict(self, data: Dict) -> bool:
        """
        Обновить настройки из словаря
        
        Args:
            data: Словарь с новыми значениями
            
        Returns:
            True если обновление успешно
        """
        try:
            if "spread_threshold_percent" in data:
                self.spread_threshold_percent = float(data["spread_threshold_percent"])
            
            if "funding_rate_history_days" in data:
                self.funding_rate_history_days = int(data["funding_rate_history_days"])
            
            if "monitoring_interval_seconds" in data:
                self.monitoring_interval_seconds = int(data["monitoring_interval_seconds"])
            
            if "return_on_capital_threshold" in data:
                self.return_on_capital_threshold = float(data["return_on_capital_threshold"])
            
            if "capital_usdt" in data:
                self.capital_usdt = float(data["capital_usdt"])
            
            if "leverage" in data:
                self.leverage = int(data["leverage"])
            
            if "perpetual_symbol" in data:
                self.perpetual_symbol = str(data["perpetual_symbol"]).strip()
            
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка при обновлении настроек: {e}")
            return False
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def load_config_from_file() -> Optional[Dict]:
    """Загрузить конфигурацию из файла"""
    if not CONFIG_FILE.exists():
        return None
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке конфигурации из файла: {e}")
        return None


def save_config_to_file(config_dict: Dict) -> Tuple[bool, str]:
    """Сохранить конфигурацию в файл
    
    Returns:
        Кортеж (успех, сообщение об ошибке)
    """
    try:
        with _config_lock:
            # Проверяем, не является ли путь директорией (известная проблема Docker)
            if CONFIG_FILE.exists() and CONFIG_FILE.is_dir():
                logger.warning(f"{CONFIG_FILE} является директорией, удаляем её")
                shutil.rmtree(CONFIG_FILE)
            
            # Создаем директорию, если её нет
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")
        return True, ""
    except PermissionError as e:
        error_msg = f"Нет прав на запись в файл {CONFIG_FILE}: {e}"
        logger.error(error_msg)
        return False, error_msg
    except OSError as e:
        error_msg = f"Ошибка файловой системы при сохранении {CONFIG_FILE}: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Ошибка при сохранении конфигурации в {CONFIG_FILE}: {e}"
        logger.error(error_msg)
        return False, error_msg


def get_updatable_config() -> Dict:
    """Получить только изменяемые параметры конфигурации"""
    return {
        "spread_threshold_percent": settings.spread_threshold_percent,
        "funding_rate_history_days": settings.funding_rate_history_days,
        "monitoring_interval_seconds": settings.monitoring_interval_seconds,
        "return_on_capital_threshold": settings.return_on_capital_threshold,
        "perpetual_symbol": settings.perpetual_symbol,
    }


def update_config(config_dict: Dict):
    """
    Обновить конфигурацию
    
    Args:
        config_dict: Словарь с новыми значениями
        
    Returns:
        Кортеж (успех, сообщение)
    """
    # Валидация значений
    if "spread_threshold_percent" in config_dict:
        try:
            threshold = float(config_dict["spread_threshold_percent"])
            if threshold < 0 or threshold > 100:
                return False, "Порог спреда должен быть от 0 до 100%"
        except (ValueError, TypeError):
            return False, "Неверное значение для порога спреда"
    
    if "funding_rate_history_days" in config_dict:
        try:
            days = int(config_dict["funding_rate_history_days"])
            if days < 1 or days > 365:
                return False, "Количество дней истории должно быть от 1 до 365"
        except (ValueError, TypeError):
            return False, "Неверное значение для количества дней истории"
    
    if "monitoring_interval_seconds" in config_dict:
        try:
            interval = int(config_dict["monitoring_interval_seconds"])
            if interval < 1 or interval > 3600:
                return False, "Интервал мониторинга должен быть от 1 до 3600 секунд"
        except (ValueError, TypeError):
            return False, "Неверное значение для интервала мониторинга"
    
    if "return_on_capital_threshold" in config_dict:
        try:
            threshold = float(config_dict["return_on_capital_threshold"])
            if threshold < 0 or threshold > 1000:
                return False, "Порог доходности на капитал должен быть от 0 до 1000%"
        except (ValueError, TypeError):
            return False, "Неверное значение для порога доходности на капитал"
    
    # Обновляем настройки
    if not settings.update_from_dict(config_dict):
        return False, "Ошибка при обновлении настроек"
    
    # Сохраняем в файл
    updatable_config = get_updatable_config()
    success, error_msg = save_config_to_file(updatable_config)
    if not success:
        return False, f"Ошибка при сохранении конфигурации: {error_msg}"
    
    return True, "Конфигурация успешно обновлена"


# Загружаем начальную конфигурацию
initial_config = Settings()

# Загружаем сохраненную конфигурацию из файла, если она есть
saved_config = load_config_from_file()
if saved_config:
    initial_config.update_from_dict(saved_config)
    logger.info("Загружена конфигурация из файла config.json")

# Глобальный объект настроек
settings = initial_config
