"""
WebSocket клиент для получения данных от ByBit в реальном времени
"""
import asyncio
import json
import logging
from typing import Dict, Callable, Optional, List
import websocket
import threading
import time

logger = logging.getLogger(__name__)


class ByBitWebSocketClient:
    """
    WebSocket клиент для получения данных от ByBit в реальном времени
    """
    
    def __init__(self, testnet: bool = False):
        """
        Инициализация WebSocket клиента
        
        Args:
            testnet: Использовать testnet (по умолчанию False - mainnet)
        """
        self.testnet = testnet
        self.ws_linear = None
        self.ws_spot = None
        self.ws_linear_thread = None
        self.ws_spot_thread = None
        self.callbacks: Dict[str, List[Callable]] = {}
        self.subscribed_symbols: Dict[str, set] = {
            'linear': set(),
            'spot': set()
        }
        self._is_running = False
        self._reconnect_delay = 5  # секунд
        self._pending_subscriptions = {
            'linear': [],
            'spot': []
        }
        
        logger.info(f"Инициализация ByBit WebSocket клиента (testnet={testnet})")
    
    def _get_ws_url(self, category: str) -> str:
        """Получить URL для WebSocket подключения"""
        if self.testnet:
            return "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            return "wss://stream.bybit.com/v5/public/linear"
    
    def _on_message_linear(self, ws, message):
        """Обработчик сообщений для linear (фьючерсы)"""
        try:
            data = json.loads(message)
            
            # Проверяем тип сообщения
            if 'topic' in data:
                topic = data['topic']
                
                # Обработка тикеров
                if topic.startswith('tickers.'):
                    symbol = topic.split('.')[1]
                    if 'data' in data:
                        ticker_data = data['data']
                        self._trigger_callback(f'ticker_linear_{symbol}', ticker_data)
                        logger.debug(f"Получен тикер для {symbol}: mark_price={ticker_data.get('markPrice')}, last_price={ticker_data.get('lastPrice')}")
            
            # Ответ на ping
            elif 'op' in data and data['op'] == 'ping':
                logger.debug("Получен ping от linear, отправляем pong")
                pong_message = json.dumps({"op": "pong"})
                ws.send(pong_message)
            
            # Подтверждение подписки
            elif 'success' in data:
                if data['success']:
                    logger.info(f"Успешная подписка linear: {data.get('ret_msg', 'OK')}")
                else:
                    logger.error(f"Ошибка подписки linear: {data.get('ret_msg', 'Unknown error')}")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения linear: {e}", exc_info=True)
    
    def _on_message_spot(self, ws, message):
        """Обработчик сообщений для spot"""
        try:
            data = json.loads(message)
            
            if 'topic' in data:
                topic = data['topic']
                
                # Обработка тикеров spot
                if topic.startswith('tickers.'):
                    symbol = topic.split('.')[1]
                    if 'data' in data:
                        ticker_data = data['data']
                        self._trigger_callback(f'ticker_spot_{symbol}', ticker_data)
                        logger.debug(f"Получен spot тикер для {symbol}: last_price={ticker_data.get('lastPrice')}")
            
            elif 'op' in data and data['op'] == 'ping':
                logger.debug("Получен ping от spot, отправляем pong")
                pong_message = json.dumps({"op": "pong"})
                ws.send(pong_message)
            
            elif 'success' in data:
                if data['success']:
                    logger.info(f"Успешная подписка spot: {data.get('ret_msg', 'OK')}")
                else:
                    logger.error(f"Ошибка подписки spot: {data.get('ret_msg', 'Unknown error')}")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения spot: {e}", exc_info=True)
    
    def _trigger_callback(self, event: str, data: Dict):
        """Вызвать все зарегистрированные callback для события"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Ошибка в callback для {event}: {e}", exc_info=True)
    
    def register_callback(self, event: str, callback: Callable):
        """
        Зарегистрировать callback для события
        
        Args:
            event: Название события (например, 'ticker_linear_ETHUSDT')
            callback: Функция для вызова при получении данных
        """
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
        logger.info(f"Зарегистрирован callback для события: {event}")
    
    def _on_error_linear(self, ws, error):
        """Обработчик ошибок для linear"""
        logger.error(f"WebSocket linear ошибка: {error}")
    
    def _on_close_linear(self, ws, close_status_code, close_msg):
        """Обработчик закрытия для linear"""
        logger.info(f"WebSocket linear закрыт: {close_status_code} - {close_msg}")
        if self._is_running:
            logger.info("Попытка переподключения linear через 5 секунд...")
            time.sleep(self._reconnect_delay)
            self._start_linear_ws()
    
    def _on_open_linear(self, ws):
        """Обработчик открытия соединения для linear"""
        logger.info("WebSocket linear подключен")
        
        # Подписываемся на все отложенные подписки
        for symbol in self._pending_subscriptions['linear']:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"tickers.{symbol}"]
            }
            ws.send(json.dumps(subscribe_message))
            logger.info(f"Подписка на linear тикер: {symbol}")
    
    def _on_error_spot(self, ws, error):
        """Обработчик ошибок для spot"""
        logger.error(f"WebSocket spot ошибка: {error}")
    
    def _on_close_spot(self, ws, close_status_code, close_msg):
        """Обработчик закрытия для spot"""
        logger.info(f"WebSocket spot закрыт: {close_status_code} - {close_msg}")
        if self._is_running:
            logger.info("Попытка переподключения spot через 5 секунд...")
            time.sleep(self._reconnect_delay)
            self._start_spot_ws()
    
    def _on_open_spot(self, ws):
        """Обработчик открытия соединения для spot"""
        logger.info("WebSocket spot подключен")
        
        # Подписываемся на все отложенные подписки
        for symbol in self._pending_subscriptions['spot']:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"tickers.{symbol}"]
            }
            ws.send(json.dumps(subscribe_message))
            logger.info(f"Подписка на spot тикер: {symbol}")
    
    def _start_linear_ws(self):
        """Запустить WebSocket для linear"""
        url = self._get_ws_url('linear')
        self.ws_linear = websocket.WebSocketApp(
            url,
            on_message=self._on_message_linear,
            on_error=self._on_error_linear,
            on_close=self._on_close_linear,
            on_open=self._on_open_linear
        )
        
        # Запускаем в отдельном потоке
        self.ws_linear_thread = threading.Thread(target=self.ws_linear.run_forever)
        self.ws_linear_thread.daemon = True
        self.ws_linear_thread.start()
    
    def _start_spot_ws(self):
        """Запустить WebSocket для spot"""
        url = "wss://stream.bybit.com/v5/public/spot"
        self.ws_spot = websocket.WebSocketApp(
            url,
            on_message=self._on_message_spot,
            on_error=self._on_error_spot,
            on_close=self._on_close_spot,
            on_open=self._on_open_spot
        )
        
        # Запускаем в отдельном потоке
        self.ws_spot_thread = threading.Thread(target=self.ws_spot.run_forever)
        self.ws_spot_thread.daemon = True
        self.ws_spot_thread.start()
    
    def start(self):
        """Запустить WebSocket подключения"""
        try:
            self._is_running = True
            
            # Запускаем WebSocket для linear (фьючерсы)
            logger.info("Подключение к ByBit WebSocket (linear)...")
            self._start_linear_ws()
            
            # Запускаем WebSocket для spot
            logger.info("Подключение к ByBit WebSocket (spot)...")
            self._start_spot_ws()
            
            # Даем время на подключение
            time.sleep(2)
            
            logger.info("WebSocket подключения установлены")
            
        except Exception as e:
            logger.error(f"Ошибка при запуске WebSocket: {e}", exc_info=True)
            self._is_running = False
            raise
    
    def subscribe_ticker(self, symbol: str, category: str = 'linear'):
        """
        Подписаться на тикер символа
        
        Args:
            symbol: Символ (например, 'ETHUSDT', 'ETHUSDT-28MAR25')
            category: Категория ('linear' или 'spot')
        """
        try:
            # Добавляем в список отложенных подписок
            if symbol not in self._pending_subscriptions[category]:
                self._pending_subscriptions[category].append(symbol)
            
            # Если WebSocket уже подключен, подписываемся сразу
            if category == 'linear' and self.ws_linear:
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"tickers.{symbol}"]
                }
                self.ws_linear.send(json.dumps(subscribe_message))
                self.subscribed_symbols['linear'].add(symbol)
                logger.info(f"Подписка на linear тикер: {symbol}")
                
            elif category == 'spot' and self.ws_spot:
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"tickers.{symbol}"]
                }
                self.ws_spot.send(json.dumps(subscribe_message))
                self.subscribed_symbols['spot'].add(symbol)
                logger.info(f"Подписка на spot тикер: {symbol}")
                
        except Exception as e:
            logger.error(f"Ошибка подписки на тикер {symbol} ({category}): {e}", exc_info=True)
    
    def unsubscribe_ticker(self, symbol: str, category: str = 'linear'):
        """
        Отписаться от тикера символа
        
        Args:
            symbol: Символ
            category: Категория ('linear' или 'spot')
        """
        try:
            if category == 'linear' and self.ws_linear:
                # pybit не предоставляет прямой метод отписки, нужно переподключиться
                self.subscribed_symbols['linear'].discard(symbol)
                logger.info(f"Отписка от linear тикера: {symbol}")
                
            elif category == 'spot' and self.ws_spot:
                self.subscribed_symbols['spot'].discard(symbol)
                logger.info(f"Отписка от spot тикера: {symbol}")
                
        except Exception as e:
            logger.error(f"Ошибка отписки от тикера {symbol} ({category}): {e}", exc_info=True)
    
    def stop(self):
        """Остановить WebSocket подключения"""
        try:
            self._is_running = False
            
            if self.ws_linear:
                logger.info("Закрытие WebSocket linear...")
                self.ws_linear.close()
                self.ws_linear = None
            
            if self.ws_spot:
                logger.info("Закрытие WebSocket spot...")
                self.ws_spot.close()
                self.ws_spot = None
            
            logger.info("WebSocket подключения закрыты")
            
        except Exception as e:
            logger.error(f"Ошибка при остановке WebSocket: {e}", exc_info=True)
    
    def is_connected(self) -> bool:
        """Проверить, подключены ли WebSocket"""
        return self._is_running and (self.ws_linear is not None or self.ws_spot is not None)
    
    def get_subscribed_symbols(self, category: str = 'linear') -> set:
        """Получить список подписанных символов"""
        return self.subscribed_symbols.get(category, set())

