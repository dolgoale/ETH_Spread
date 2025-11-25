"""
Главный файл для запуска приложения мониторинга спредов ETH
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

from src.bybit_client import ByBitClient
from src.telegram_notifier import TelegramNotifier
from src.monitor import SpreadMonitor
from src.web_server import WebServer
import config

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Изменено на DEBUG для более детального логирования
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eth_spread_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class Application:
    """Основной класс приложения"""
    
    def __init__(self):
        """Инициализация приложения"""
        self.monitor: Optional[SpreadMonitor] = None
        self.web_server: Optional[WebServer] = None
        self.monitoring_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
    
    def setup(self):
        """Настройка компонентов приложения"""
        logger.info("Инициализация компонентов приложения...")
        
        # Проверка конфигурации
        if not config.settings.bybit_api_key or not config.settings.bybit_api_secret:
            logger.warning("API ключи ByBit не настроены. Некоторые функции могут не работать.")
        
        # Создание клиента ByBit
        bybit_client = ByBitClient(
            api_key=config.settings.bybit_api_key,
            api_secret=config.settings.bybit_api_secret,
            testnet=config.settings.bybit_testnet
        )
        
        # Создание уведомителя Telegram
        telegram_notifier = TelegramNotifier(
            bot_token=config.settings.telegram_bot_token,
            chat_id=config.settings.telegram_chat_id
        )
        
        if not config.settings.telegram_bot_token:
            logger.warning("Telegram бот не настроен. Уведомления не будут отправляться.")
        
        # Создание монитора
        self.monitor = SpreadMonitor(
            bybit_client=bybit_client,
            telegram_notifier=telegram_notifier,
            perpetual_symbol=config.settings.perpetual_symbol,
            spread_threshold_percent=config.settings.spread_threshold_percent,
            funding_rate_history_days=config.settings.funding_rate_history_days
        )
        
        # Создание веб-сервера
        self.web_server = WebServer(monitor=self.monitor)
        
        logger.info("Компоненты приложения инициализированы")
    
    async def start_monitoring(self):
        """Запустить мониторинг"""
        if not self.monitor:
            logger.error("Монитор не инициализирован")
            return
        
        logger.info("Запуск мониторинга...")
        self.monitoring_task = asyncio.create_task(
            self.monitor.start_monitoring(
                interval_seconds=config.settings.monitoring_interval_seconds
            )
        )
    
    async def start_web_server(self):
        """Запустить веб-сервер в отдельной задаче"""
        if not self.web_server:
            logger.error("Веб-сервер не инициализирован")
            return
        
        logger.info(f"Запуск веб-сервера на {config.settings.web_server_host}:{config.settings.web_server_port}")
        
        # Запускаем веб-сервер в отдельном потоке
        import threading
        
        def run_server():
            self.web_server.run(
                host=config.settings.web_server_host,
                port=config.settings.web_server_port
            )
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
    
    async def run(self):
        """Запустить приложение"""
        try:
            # Запускаем веб-сервер
            await self.start_web_server()
            
            # Небольшая задержка для запуска веб-сервера
            await asyncio.sleep(2)
            
            # Запускаем мониторинг
            await self.start_monitoring()
            
            logger.info("Приложение запущено. Нажмите Ctrl+C для остановки.")
            
            # Ждем сигнала остановки
            await self.shutdown_event.wait()
            
        except asyncio.CancelledError:
            logger.info("Приложение остановлено")
        except Exception as e:
            logger.error(f"Ошибка при работе приложения: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Остановка приложения"""
        logger.info("Остановка приложения...")
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Приложение остановлено")
    
    def handle_shutdown(self, signum, frame):
        """Обработчик сигналов остановки"""
        logger.info(f"Получен сигнал {signum}. Остановка приложения...")
        self.shutdown_event.set()


async def main():
    """Главная функция"""
    app = Application()
    
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, app.handle_shutdown)
    signal.signal(signal.SIGTERM, app.handle_shutdown)
    
    # Настройка и запуск
    app.setup()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

