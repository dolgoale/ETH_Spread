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
        spread_threshold_percent: float,
        funding_rate_history_days: int
    ):
        """
        Инициализация монитора
        
        Args:
            bybit_client: Клиент ByBit API
            telegram_notifier: Уведомитель Telegram
            perpetual_symbol: Символ бессрочного фьючерса
            spread_threshold_percent: Порог для сигнала в процентах
            funding_rate_history_days: Количество дней истории Funding Rate
        """
        self.bybit_client = bybit_client
        self.telegram_notifier = telegram_notifier
        self.perpetual_symbol = perpetual_symbol
        self.spread_threshold_percent = spread_threshold_percent
        self.funding_rate_history_days = funding_rate_history_days
        self._config_callback: Optional[Callable] = None
        
        # Хранилище данных
        self.current_spreads: Dict[str, SpreadData] = {}
        self.current_funding_rate: Optional[FundingRateData] = None
        self.last_alert_time: Dict[str, datetime] = defaultdict(lambda: datetime.min)
        self.last_return_alert_time: Dict[str, datetime] = defaultdict(lambda: datetime.min)
        
        # Callback для обновления данных (для веб-интерфейса)
        self.data_update_callback: Optional[Callable] = None
    
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
            "spread_threshold_percent": config.settings.spread_threshold_percent,
            "funding_rate_history_days": config.settings.funding_rate_history_days,
            "return_on_capital_threshold": config.settings.return_on_capital_threshold,
            "capital_usdt": config.settings.capital_usdt,
            "leverage": config.settings.leverage,
        }
    
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
        
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
        
        # Получаем доступные фьючерсы динамически
        available_futures = await loop.run_in_executor(
            executor,
            self.bybit_client.get_available_futures,
            perpetual_symbol
        )
        
        # Получаем данные параллельно
        perpetual_task = loop.run_in_executor(
            executor,
            self.bybit_client.get_perpetual_ticker,
            perpetual_symbol
        )
        
        # Получаем тикеры для доступных фьючерсов (первые 8)
        futures_symbols = [f.get("symbol") for f in available_futures[:8] if f.get("symbol")]
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
            perpetual_symbol
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
            
            # Получаем актуальную конфигурацию
            current_config = self._get_config()
            perpetual_symbol = current_config.get("perpetual_symbol", self.perpetual_symbol)
            funding_rate_history_days = current_config.get("funding_rate_history_days", self.funding_rate_history_days)
            spread_threshold_percent = current_config.get("spread_threshold_percent", self.spread_threshold_percent)
            return_on_capital_threshold = current_config.get("return_on_capital_threshold", config.settings.return_on_capital_threshold)
            capital_usdt = current_config.get("capital_usdt", config.settings.capital_usdt)
            leverage = current_config.get("leverage", config.settings.leverage)
            
            # Рассчитываем спреды только если есть данные по срочным фьючерсам
            spreads = []
            if futures_tickers:
                spreads = SpreadCalculator.calculate_spreads(perpetual_ticker, futures_tickers)
                
                # Сохраняем текущие спреды
                for spread in spreads:
                    self.current_spreads[spread.futures_symbol] = spread
                
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
            else:
                logger.warning("Не удалось получить данные по срочным фьючерсам, пропускаем расчет спредов")
            
            logger.debug(f"Начало проверки доходности на капитал: порог={return_on_capital_threshold}%, капитал={capital_usdt} USDT, плечо={leverage}x, фьючерсов={len(futures_tickers)}")
            await self._check_return_on_capital(
                perpetual_ticker=perpetual_ticker,
                futures_tickers=futures_tickers,
                spreads=spreads,
                return_on_capital_threshold=return_on_capital_threshold,
                capital_usdt=capital_usdt,
                leverage=leverage
            )
            logger.debug(f"Завершена проверка доходности на капитал")
            
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
        # Защита от слишком частых сигналов (минимум 5 минут между сигналами для одного фьючерса)
        now = datetime.now()
        last_alert = self.last_alert_time[spread.futures_symbol]
        
        if (now - last_alert).total_seconds() < 300:  # 5 минут = 300 секунд
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
    
    async def _check_return_on_capital(
        self,
        perpetual_ticker: Optional[Dict],
        futures_tickers: List[Dict],
        spreads: List[SpreadData],
        return_on_capital_threshold: float,
        capital_usdt: float,
        leverage: int
    ):
        """
        Проверить доходность на капитал и отправить сигнал если превышен порог
        
        Args:
            perpetual_ticker: Данные бессрочного фьючерса
            futures_tickers: Список данных срочных фьючерсов
            spreads: Список спредов
            return_on_capital_threshold: Порог доходности в % годовых
            capital_usdt: Капитал в USDT
            leverage: Плечо
        """
        if not perpetual_ticker or not futures_tickers or capital_usdt <= 0 or leverage <= 0:
            logger.debug(f"Пропущена проверка доходности: perpetual_ticker={perpetual_ticker is not None}, futures_count={len(futures_tickers) if futures_tickers else 0}, capital={capital_usdt}, leverage={leverage}")
            return
        
        perpetual_mark_price = perpetual_ticker.get("mark_price", 0)
        if perpetual_mark_price <= 0:
            return
        
        # Получаем данные о доступных фьючерсах для расчета дней до экспирации
        import concurrent.futures
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
        
        # Получаем список доступных фьючерсов для получения delivery_time
        current_config = self._get_config()
        perpetual_symbol = current_config.get("perpetual_symbol", self.perpetual_symbol)
        
        available_futures = await loop.run_in_executor(
            executor,
            self.bybit_client.get_available_futures,
            perpetual_symbol
        )
        
        # Создаем словарь delivery_times
        delivery_times = {}
        for future_info in available_futures:
            symbol = future_info.get("symbol")
            delivery_time_ms = future_info.get("delivery_time")
            if symbol and delivery_time_ms:
                delivery_times[symbol] = delivery_time_ms
        
        # Создаем словарь спредов по символу
        spreads_dict = {spread.futures_symbol: spread for spread in spreads}
        
        # Для каждого фьючерса рассчитываем доходность
        for futures_ticker in futures_tickers:
            symbol = futures_ticker.get("symbol", "")
            if not symbol or symbol not in spreads_dict:
                continue
            
            spread = spreads_dict[symbol]
            
            # Получаем дни до экспирации
            delivery_time_ms = delivery_times.get(symbol)
            if not delivery_time_ms:
                continue
            
            from datetime import datetime
            delivery_dt = datetime.fromtimestamp(delivery_time_ms / 1000)
            days_until_exp = (delivery_dt - datetime.now()).total_seconds() / 86400.0
            if days_until_exp <= 0:
                continue
            
            # Получаем суммарный FR за дни до экспирации
            days_for_fr = int(days_until_exp) if days_until_exp > 0 else 30
            days_for_fr = min(days_for_fr, 365)
            
            history = await loop.run_in_executor(
                executor,
                self.bybit_client.get_funding_rate_history,
                perpetual_symbol,
                days_for_fr
            )
            
            if not history:
                continue
            
            # Рассчитываем суммарный FR до экспирации (аналогично _get_instruments_data)
            rates = [item["funding_rate"] for item in history]
            total_fr_for_days = sum(rates) if rates else 0
            actual_payments_in_history = len(history)
            expected_payments_in_history = days_for_fr * 3
            
            if actual_payments_in_history >= expected_payments_in_history * 0.95:
                avg_fr_per_payment = total_fr_for_days / actual_payments_in_history if actual_payments_in_history > 0 else 0
                payments_until_exp = days_until_exp * 3
                funding_rate_until_exp = avg_fr_per_payment * payments_until_exp * 100
            else:
                avg_fr_per_payment = total_fr_for_days / actual_payments_in_history if actual_payments_in_history > 0 else 0
                payments_until_exp = days_until_exp * 3
                funding_rate_until_exp = avg_fr_per_payment * payments_until_exp * 100
            
            # Комиссии (4 сделки × 0.0290%)
            TOTAL_TRADING_FEES = 0.1160
            
            # Чистая прибыль в % = FR до экспирации - Спред % - Комиссии
            net_profit_percent = funding_rate_until_exp - spread.spread_percent - TOTAL_TRADING_FEES
            
            # Рассчитываем количество контрактов
            initial_margin_rate = 1 / leverage
            contract_size = 1
            contracts_per_side = capital_usdt / 2 / (perpetual_mark_price * contract_size * initial_margin_rate)
            contracts_count = int(contracts_per_side)
            
            # Размер позиции по бессрочному фьючерсу
            perpetual_position_size = contracts_count * perpetual_mark_price * contract_size
            
            # Чистая прибыль в USDT
            net_profit_usdt = perpetual_position_size * net_profit_percent / 100
            
            # Доходность на капитал в % годовых
            # Формула: (чистая прибыль в USDT / капитал * 100) / дни до экспирации * 365
            return_on_capital = (net_profit_usdt / capital_usdt * 100) / days_until_exp * 365
            
            # Логируем расчет для отладки
            logger.debug(f"Проверка доходности для {symbol}: ROC={return_on_capital:.2f}%, порог={return_on_capital_threshold:.2f}%, прибыль={net_profit_usdt:.2f} USDT, дней={days_until_exp:.1f}")
            
            # Проверяем порог (используем >= для учета случаев, когда доходность точно равна порогу)
            is_above_threshold = return_on_capital > return_on_capital_threshold
            logger.debug(f"Сравнение для {symbol}: {return_on_capital:.4f} > {return_on_capital_threshold:.4f} = {is_above_threshold}")
            
            if is_above_threshold:
                # Защита от спама (минимум 5 минут между сигналами)
                now = datetime.now()
                last_alert = self.last_return_alert_time[symbol]
                
                if (now - last_alert).total_seconds() < 300:  # 5 минут = 300 секунд
                    logger.debug(f"Пропущен сигнал доходности для {symbol} (слишком частые сигналы, последний: {last_alert})")
                    continue
                
                # Отправляем сигнал
                logger.info(f"Порог превышен для {symbol}: {return_on_capital:.2f}% > {return_on_capital_threshold:.2f}%, отправка сигнала в Telegram...")
                success = await self.telegram_notifier.send_return_on_capital_alert(
                    futures_symbol=symbol,
                    return_on_capital=return_on_capital,
                    threshold=return_on_capital_threshold,
                    net_profit_usdt=net_profit_usdt,
                    days_until_expiration=days_until_exp,
                    capital_usdt=capital_usdt,
                    leverage=leverage
                )
                
                if success:
                    self.last_return_alert_time[symbol] = now
                    logger.info(f"✅ Сигнал доходности успешно отправлен для {symbol}: {return_on_capital:.2f}% > {return_on_capital_threshold:.2f}%")
                else:
                    logger.error(f"❌ Ошибка при отправке сигнала доходности для {symbol}")
    
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

