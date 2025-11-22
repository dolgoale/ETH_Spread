"""
Основной модуль мониторинга спредов
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from collections import defaultdict

from .bybit_client import ByBitClient
from .spread_calculator import SpreadCalculator, SpreadData, FundingRateData
from .telegram_notifier import TelegramNotifier
import config

logger = logging.getLogger(__name__)


class SpreadMonitor:
    """Монитор спредов между фьючерсами"""
    
    def __init__(
        self,
        bybit_client: ByBitClient,
        telegram_notifier: TelegramNotifier,
        perpetual_symbol: str,
        futures_symbols: List[str],
        spread_threshold_percent: float,
        funding_rate_history_days: int
    ):
        """
        Инициализация монитора
        
        Args:
            bybit_client: Клиент ByBit API
            telegram_notifier: Уведомитель Telegram
            perpetual_symbol: Символ бессрочного фьючерса
            futures_symbols: Список символов срочных фьючерсов
            spread_threshold_percent: Порог для сигнала в процентах
            funding_rate_history_days: Количество дней истории Funding Rate
        """
        self.bybit_client = bybit_client
        self.telegram_notifier = telegram_notifier
        self.perpetual_symbol = perpetual_symbol
        self.futures_symbols = futures_symbols
        self.spread_threshold_percent = spread_threshold_percent
        self.funding_rate_history_days = funding_rate_history_days
        self._config_callback: Optional[Callable] = None
    
    def set_config_callback(self, callback: Callable):
        """Установить callback для получения актуальной конфигурации"""
        self._config_callback = callback
    
    def _get_config(self) -> Dict:
        """Получить актуальную конфигурацию"""
        if self._config_callback:
            return self._config_callback()
        # Fallback к глобальной конфигурации
        return {
            "perpetual_symbol": config.settings.perpetual_symbol,
            "futures_symbols": config.settings.futures_symbols_list,
            "spread_threshold_percent": config.settings.spread_threshold_percent,
            "funding_rate_history_days": config.settings.funding_rate_history_days,
        }
        
        # Хранилище данных
        self.current_spreads: Dict[str, SpreadData] = {}
        self.current_funding_rate: Optional[FundingRateData] = None
        self.last_alert_time: Dict[str, datetime] = defaultdict(lambda: datetime.min)
        
        # Callback для обновления данных (для веб-интерфейса)
        self.data_update_callback: Optional[Callable] = None
    
    def set_data_update_callback(self, callback: Callable):
        """Установить callback для обновления данных"""
        self.data_update_callback = callback
    
    async def fetch_data(self) -> Dict:
        """
        Получить все необходимые данные с биржи
        
        Returns:
            Словарь с данными: perpetual_ticker, futures_tickers, funding_rate
        """
        import concurrent.futures
        
        # Получаем актуальную конфигурацию
        current_config = self._get_config()
        perpetual_symbol = current_config.get("perpetual_symbol", self.perpetual_symbol)
        futures_symbols = current_config.get("futures_symbols", self.futures_symbols)
        
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
        
        # Получаем данные параллельно
        perpetual_task = loop.run_in_executor(
            executor,
            self.bybit_client.get_perpetual_ticker,
            perpetual_symbol
        )
        
        futures_tasks = [
            loop.run_in_executor(
                executor,
                self.bybit_client.get_futures_ticker,
                symbol
            )
            for symbol in futures_symbols
        ]
        
        funding_task = loop.run_in_executor(
            executor,
            self.bybit_client.get_current_funding_rate,
            self.perpetual_symbol
        )
        
        # Ждем завершения всех запросов
        perpetual_ticker = await perpetual_task
        futures_tickers = await asyncio.gather(*futures_tasks)
        funding_rate_data = await funding_task
        
        # Фильтруем None значения
        futures_tickers = [t for t in futures_tickers if t is not None]
        
        return {
            "perpetual_ticker": perpetual_ticker,
            "futures_tickers": futures_tickers,
            "funding_rate": funding_rate_data
        }
    
    async def update_data(self):
        """Обновить данные и проверить условия для сигналов"""
        try:
            # Получаем данные с биржи
            data = await self.fetch_data()
            
            perpetual_ticker = data.get("perpetual_ticker")
            futures_tickers = data.get("futures_tickers", [])
            funding_rate_data = data.get("funding_rate")
            
            if not perpetual_ticker:
                logger.warning(f"Не удалось получить данные по бессрочному фьючерсу {self.perpetual_symbol}")
                return
            
            if not futures_tickers:
                logger.warning("Не удалось получить данные по срочным фьючерсам")
                return
            
            # Рассчитываем спреды
            spreads = SpreadCalculator.calculate_spreads(perpetual_ticker, futures_tickers)
            
            # Сохраняем текущие спреды
            for spread in spreads:
                self.current_spreads[spread.futures_symbol] = spread
            
            # Получаем актуальную конфигурацию
            current_config = self._get_config()
            perpetual_symbol = current_config.get("perpetual_symbol", self.perpetual_symbol)
            funding_rate_history_days = current_config.get("funding_rate_history_days", self.funding_rate_history_days)
            spread_threshold_percent = current_config.get("spread_threshold_percent", self.spread_threshold_percent)
            
            # Получаем средний Funding Rate
            loop = asyncio.get_event_loop()
            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor()
            avg_funding_rate = await loop.run_in_executor(
                executor,
                self.bybit_client.calculate_average_funding_rate,
                perpetual_symbol,
                funding_rate_history_days
            )
            
            if funding_rate_data and avg_funding_rate is not None:
                self.current_funding_rate = FundingRateData(
                    symbol=perpetual_symbol,
                    current_rate=funding_rate_data.get("funding_rate", 0),
                    average_rate=avg_funding_rate,
                    timestamp=datetime.now()
                )
                
                # Проверяем условия для каждого спреда
                current_rate = funding_rate_data.get("funding_rate", 0)
                
                for spread in spreads:
                    should_alert = SpreadCalculator.should_alert(
                        spread_percent=spread.spread_percent,
                        funding_rate=current_rate,
                        threshold_percent=spread_threshold_percent
                    )
                    
                    if should_alert:
                        # Отправляем сигнал (с ограничением частоты)
                        await self._check_and_send_alert(spread, current_rate)
            
            # Вызываем callback для обновления веб-интерфейса
            if self.data_update_callback:
                self.data_update_callback(self.get_current_data())
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных: {e}", exc_info=True)
    
    async def _check_and_send_alert(
        self,
        spread: SpreadData,
        funding_rate: float
    ):
        """
        Проверить и отправить сигнал (с защитой от спама)
        
        Args:
            spread: Данные о спреде
            funding_rate: Текущий Funding Rate
        """
        # Защита от слишком частых сигналов (минимум 1 час между сигналами для одного фьючерса)
        now = datetime.now()
        last_alert = self.last_alert_time[spread.futures_symbol]
        
        if (now - last_alert).total_seconds() < 3600:
            logger.debug(f"Пропущен сигнал для {spread.futures_symbol} (слишком частые сигналы)")
            return
        
        # Отправляем сигнал
        success = await self.telegram_notifier.send_alert(
            futures_symbol=spread.futures_symbol,
            spread_percent=spread.spread_percent,
            funding_rate=funding_rate,
            threshold_percent=self.spread_threshold_percent
        )
        
        if success:
            self.last_alert_time[spread.futures_symbol] = now
            logger.info(f"Сигнал отправлен для {spread.futures_symbol}")
    
    def get_current_data(self) -> Dict:
        """
        Получить текущие данные мониторинга
        
        Returns:
            Словарь с текущими данными
        """
        return {
            "spreads": {
                symbol: spread.to_dict()
                for symbol, spread in self.current_spreads.items()
            },
            "funding_rate": self.current_funding_rate.to_dict() if self.current_funding_rate else None,
            "timestamp": datetime.now().isoformat()
        }
    
    async def start_monitoring(self, interval_seconds: int):
        """
        Запустить мониторинг в бесконечном цикле
        
        Args:
            interval_seconds: Начальный интервал обновления в секундах (будет обновляться динамически)
        """
        logger.info(f"Запуск мониторинга спредов (начальный интервал: {interval_seconds} сек)")
        
        while True:
            try:
                await self.update_data()
                
                # Получаем актуальный интервал из конфигурации
                current_config = self._get_config()
                current_interval = current_config.get("monitoring_interval_seconds", interval_seconds)
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}", exc_info=True)
                current_interval = interval_seconds
            
            await asyncio.sleep(current_interval)

