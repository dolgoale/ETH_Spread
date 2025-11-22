"""
Конфигурация приложения с поддержкой динамического изменения
"""
import os
import json
import threading
from typing import List, Dict, Optional
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
    
    # Web Server
    web_server_host: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    web_server_port: int = int(os.getenv("WEB_SERVER_PORT", "8000"))
    
    # Symbols (изменяемые через веб-интерфейс)
    perpetual_symbol: str = os.getenv("PERPETUAL_SYMBOL", "ETHUSDT")
    futures_symbols: str = os.getenv("FUTURES_SYMBOLS", "ETHUSDT-26DEC25,ETHUSDT-26JUN26,ETHUSDT-25SEP26")
    
    @property
    def futures_symbols_list(self) -> List[str]:
        """Список символов срочных фьючерсов"""
        return [s.strip() for s in self.futures_symbols.split(",") if s.strip()]
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь для API"""
        return {
            "spread_threshold_percent": self.spread_threshold_percent,
            "funding_rate_history_days": self.funding_rate_history_days,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "perpetual_symbol": self.perpetual_symbol,
            "futures_symbols": self.futures_symbols,
            "futures_symbols_list": self.futures_symbols_list,
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
            
            if "perpetual_symbol" in data:
                self.perpetual_symbol = str(data["perpetual_symbol"]).strip()
            
            if "futures_symbols" in data:
                self.futures_symbols = str(data["futures_symbols"]).strip()
            
            if "futures_symbols_list" in data:
                # Если передан список, преобразуем в строку
                if isinstance(data["futures_symbols_list"], list):
                    self.futures_symbols = ",".join([str(s).strip() for s in data["futures_symbols_list"]])
                else:
                    self.futures_symbols = str(data["futures_symbols_list"]).strip()
            
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


def save_config_to_file(config_dict: Dict) -> bool:
    """Сохранить конфигурацию в файл"""
    try:
        with _config_lock:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации: {e}")
        return False


def get_updatable_config() -> Dict:
    """Получить только изменяемые параметры конфигурации"""
    return {
        "spread_threshold_percent": settings.spread_threshold_percent,
        "funding_rate_history_days": settings.funding_rate_history_days,
        "monitoring_interval_seconds": settings.monitoring_interval_seconds,
        "perpetual_symbol": settings.perpetual_symbol,
        "futures_symbols": settings.futures_symbols,
        "futures_symbols_list": settings.futures_symbols_list,
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
    
    # Обновляем настройки
    if not settings.update_from_dict(config_dict):
        return False, "Ошибка при обновлении настроек"
    
    # Сохраняем в файл
    updatable_config = get_updatable_config()
    if not save_config_to_file(updatable_config):
        return False, "Ошибка при сохранении конфигурации"
    
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
