"""
Клиент для работы с ByBit API
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)


class ByBitClient:
    """Клиент для взаимодействия с ByBit API"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = False):
        """
        Инициализация клиента ByBit
        
        Args:
            api_key: API ключ ByBit (необязателен для публичных данных)
            api_secret: API секрет ByBit (необязателен для публичных данных)
            testnet: Использовать тестовую сеть
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Инициализация единого клиента для линейных фьючерсов
        # В новой версии pybit параметр category передается в методы, а не в конструктор
        client_kwargs = {}
        
        if testnet:
            client_kwargs["testnet"] = testnet
        
        # API ключи нужны только для приватных запросов
        # Для публичных данных (тикеры, funding rate) они не требуются
        if api_key and api_secret:
            client_kwargs["api_key"] = api_key
            client_kwargs["api_secret"] = api_secret
        
        self.client = HTTP(**client_kwargs) if client_kwargs else HTTP()
        
        # Оставляем обратную совместимость со старым кодом
        self.perpetual_client = self.client
        self.futures_client = self.client
    
    def get_perpetual_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить текущую цену бессрочного фьючерса
        
        Args:
            symbol: Символ инструмента (например, ETHUSDT)
            
        Returns:
            Словарь с данными тикера или None при ошибке
        """
        if not symbol:
            logger.warning("Символ не указан для получения тикера бессрочного фьючерса")
            return None
        
        try:
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            ret_code = response.get("retCode")
            if ret_code != 0:
                ret_msg = response.get("retMsg", "Unknown error")
                logger.warning(f"ByBit API вернул код ошибки {ret_code}: {ret_msg} для символа {symbol}")
                return None
            
            result = response.get("result", {})
            ticker_list = result.get("list", [])
            
            if not ticker_list:
                logger.warning(f"Тикер не найден для символа {symbol}")
                return None
            
            ticker = ticker_list[0]
            # API ByBit возвращает время сервера в поле "time" на верхнем уровне ответа
            # Если его нет, используем текущее время
            server_time = response.get("time", 0)
            if not server_time:
                server_time = int(time.time() * 1000)
            
            return {
                "symbol": ticker.get("symbol"),
                "last_price": float(ticker.get("lastPrice", 0)),
                "mark_price": float(ticker.get("markPrice", 0)),
                "index_price": float(ticker.get("indexPrice", 0)),
                "timestamp": int(server_time)  # Время сервера получения данных
            }
        except Exception as e:
            logger.error(f"Ошибка при получении тикера бессрочного фьючерса {symbol}: {e}", exc_info=True)
        
        return None
    
    def get_spot_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить текущую spot цену инструмента
        
        Args:
            symbol: Символ инструмента (например, ETHUSDT)
            
        Returns:
            Словарь с данными тикера или None при ошибке
        """
        if not symbol:
            logger.warning("Символ не указан для получения spot тикера")
            return None
        
        try:
            response = self.client.get_tickers(
                category="spot",
                symbol=symbol
            )
            
            ret_code = response.get("retCode")
            if ret_code != 0:
                ret_msg = response.get("retMsg", "Unknown error")
                logger.warning(f"ByBit API вернул код ошибки {ret_code}: {ret_msg} для spot символа {symbol}")
                return None
            
            result = response.get("result", {})
            ticker_list = result.get("list", [])
            
            if not ticker_list:
                logger.warning(f"Spot тикер не найден для символа {symbol}")
                return None
            
            ticker = ticker_list[0]
            # API ByBit возвращает время сервера в поле "time" на верхнем уровне ответа
            server_time = response.get("time", 0)
            if not server_time:
                server_time = int(time.time() * 1000)
            
            return {
                "symbol": ticker.get("symbol"),
                "last_price": float(ticker.get("lastPrice", 0)),
                "timestamp": int(server_time)
            }
        except Exception as e:
            logger.error(f"Ошибка при получении spot тикера {symbol}: {e}", exc_info=True)
        
        return None
    
    def get_futures_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить текущую цену срочного фьючерса
        
        Args:
            symbol: Символ инструмента (например, ETHUSDT-26DEC25 или ETHUSDT-26JUN26)
                   Формат на ByBit: ETHUSDT-DDMMMYY (например, ETHUSDT-26DEC25)
            
        Returns:
            Словарь с данными тикера или None при ошибке
        """
        if not symbol:
            logger.warning("Символ не указан для получения тикера срочного фьючерса")
            return None
        
        try:
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            ret_code = response.get("retCode")
            if ret_code != 0:
                ret_msg = response.get("retMsg", "Unknown error")
                logger.warning(f"ByBit API вернул код ошибки {ret_code}: {ret_msg} для символа {symbol}")
                return None
            
            result = response.get("result", {})
            ticker_list = result.get("list", [])
            
            if not ticker_list:
                logger.warning(f"Тикер не найден для символа {symbol}")
                return None
            
            ticker = ticker_list[0]
            # API ByBit возвращает время сервера в поле "time" на верхнем уровне ответа
            # Если его нет, используем текущее время
            server_time = response.get("time", 0)
            if not server_time:
                server_time = int(time.time() * 1000)
            
            return {
                "symbol": ticker.get("symbol"),
                "last_price": float(ticker.get("lastPrice", 0)),
                "mark_price": float(ticker.get("markPrice", 0)),
                "index_price": float(ticker.get("indexPrice", 0)),
                "timestamp": int(server_time)  # Время сервера получения данных
            }
        except Exception as e:
            logger.error(f"Ошибка при получении тикера срочного фьючерса {symbol}: {e}", exc_info=True)
        
        return None
    
    def get_current_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Получить текущий Funding Rate для бессрочного фьючерса
        
        Args:
            symbol: Символ инструмента (например, ETHUSDT)
            
        Returns:
            Словарь с данными Funding Rate или None при ошибке
        """
        if not symbol:
            logger.warning("Символ не указан для получения Funding Rate")
            return None
        
        try:
            response = self.client.get_funding_rate_history(
                category="linear",
                symbol=symbol,
                limit=1
            )
            
            ret_code = response.get("retCode")
            if ret_code != 0:
                ret_msg = response.get("retMsg", "Unknown error")
                logger.warning(f"ByBit API вернул код ошибки {ret_code}: {ret_msg} для символа {symbol}")
                return None
            
            result = response.get("result", {})
            funding_list = result.get("list", [])
            
            if not funding_list:
                logger.warning(f"Funding Rate не найден для символа {symbol}")
                return None
            
            funding_data = funding_list[0]
            return {
                "symbol": funding_data.get("symbol"),
                "funding_rate": float(funding_data.get("fundingRate", 0)),
                "timestamp": int(funding_data.get("fundingRateTimestamp", 0))
            }
        except Exception as e:
            logger.error(f"Ошибка при получении текущего Funding Rate для {symbol}: {e}", exc_info=True)
        
        return None
    
    def get_funding_rate_history(
        self, 
        symbol: str, 
        days: int = 7
    ) -> List[Dict]:
        """
        Получить историю Funding Rate за указанный период
        
        Args:
            symbol: Символ инструмента (например, ETHUSDT)
            days: Количество дней истории
            
        Returns:
            Список словарей с историей Funding Rate
        """
        try:
            # ByBit API возвращает до 200 записей за раз
            # Funding Rate обновляется каждые 8 часов, поэтому за 7 дней будет около 21 записи
            limit = min(days * 3, 200)
            
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            response = self.client.get_funding_rate_history(
                category="linear",
                symbol=symbol,
                startTime=start_time,
                endTime=end_time,
                limit=limit
            )
            
            if response.get("retCode") == 0:
                history = response.get("result", {}).get("list", [])
                return [
                    {
                        "symbol": item.get("symbol"),
                        "funding_rate": float(item.get("fundingRate", 0)),
                        "timestamp": int(item.get("fundingRateTimestamp", 0))
                    }
                    for item in history
                ]
        except Exception as e:
            logger.error(f"Ошибка при получении истории Funding Rate для {symbol}: {e}")
        
        return []
    
    def calculate_average_funding_rate(
        self, 
        symbol: str, 
        days: int = 7
    ) -> Optional[float]:
        """
        Рассчитать средний Funding Rate за период
        
        Args:
            symbol: Символ инструмента
            days: Количество дней для расчета
            
        Returns:
            Средний Funding Rate или None при ошибке
        """
        history = self.get_funding_rate_history(symbol, days)
        
        if not history:
            return None
        
        rates = [item["funding_rate"] for item in history]
        return sum(rates) / len(rates) if rates else None
    
    def get_available_futures(self, base_symbol: str = "ETHUSDT") -> List[Dict]:
        """
        Получить список доступных срочных фьючерсов для базового символа
        
        Args:
            base_symbol: Базовый символ (например, ETHUSDT)
            
        Returns:
            Список словарей с информацией о доступных срочных фьючерсах
        """
        try:
            response = self.client.get_instruments_info(
                category="linear",
                limit=1000
            )
            
            ret_code = response.get("retCode")
            if ret_code != 0:
                ret_msg = response.get("retMsg", "Unknown error")
                logger.warning(f"ByBit API вернул код ошибки {ret_code}: {ret_msg} при получении списка фьючерсов")
                return []
            
            result = response.get("result", {})
            instruments = result.get("list", [])
            
            # Фильтруем по базовому символу и типу контракта (LinearFutures)
            futures = []
            for inst in instruments:
                symbol = inst.get("symbol", "")
                contract_type = inst.get("contractType", "")
                delivery_time = inst.get("deliveryTime", "")
                
                # Ищем срочные фьючерсы (LinearFutures) для базового символа
                if (contract_type == "LinearFutures" and 
                    symbol.startswith(base_symbol) and
                    delivery_time and delivery_time != "0"):
                    
                    futures.append({
                        "symbol": symbol,
                        "contract_type": contract_type,
                        "delivery_time": int(delivery_time),
                        "settle_coin": inst.get("settleCoin", ""),
                        "status": inst.get("status", "")
                    })
            
            # Сортируем по дате экспирации
            futures.sort(key=lambda x: x["delivery_time"])
            
            logger.info(f"Найдено {len(futures)} срочных фьючерсов для {base_symbol}")
            return futures
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка срочных фьючерсов для {base_symbol}: {e}", exc_info=True)
            return []
    
    def get_all_futures_tickers(self, symbols: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Получить тикеры для нескольких срочных фьючерсов одновременно
        
        Args:
            symbols: Список символов срочных фьючерсов
            
        Returns:
            Словарь {символ: данные_тикера} или {символ: None} при ошибке
        """
        results = {}
        
        for symbol in symbols:
            ticker = self.get_futures_ticker(symbol)
            results[symbol] = ticker
        
        return results

