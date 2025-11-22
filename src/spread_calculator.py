"""
Модуль для расчета спредов между фьючерсами
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SpreadData:
    """Данные о спреде"""
    futures_symbol: str
    perpetual_price: float
    futures_price: float
    spread: float
    spread_percent: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь"""
        return {
            "futures_symbol": self.futures_symbol,
            "perpetual_price": self.perpetual_price,
            "futures_price": self.futures_price,
            "spread": self.spread,
            "spread_percent": self.spread_percent,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class FundingRateData:
    """Данные о Funding Rate"""
    symbol: str
    current_rate: float
    average_rate: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь"""
        return {
            "symbol": self.symbol,
            "current_rate": self.current_rate,
            "average_rate": self.average_rate,
            "timestamp": self.timestamp.isoformat()
        }


class SpreadCalculator:
    """Калькулятор спредов"""
    
    @staticmethod
    def calculate_spread(
        perpetual_price: float,
        futures_price: float,
        futures_symbol: str
    ) -> SpreadData:
        """
        Рассчитать спред между бессрочным и срочным фьючерсом
        
        Args:
            perpetual_price: Цена бессрочного фьючерса
            futures_price: Цена срочного фьючерса
            futures_symbol: Символ срочного фьючерса
            
        Returns:
            Объект SpreadData со всеми расчетами
        """
        spread = futures_price - perpetual_price
        spread_percent = (spread / perpetual_price * 100) if perpetual_price > 0 else 0
        
        return SpreadData(
            futures_symbol=futures_symbol,
            perpetual_price=perpetual_price,
            futures_price=futures_price,
            spread=spread,
            spread_percent=spread_percent,
            timestamp=datetime.now()
        )
    
    @staticmethod
    def calculate_spreads(
        perpetual_ticker: Dict,
        futures_tickers: List[Dict]
    ) -> List[SpreadData]:
        """
        Рассчитать спреды для всех срочных фьючерсов
        
        Args:
            perpetual_ticker: Данные тикера бессрочного фьючерса
            futures_tickers: Список данных тикеров срочных фьючерсов
            
        Returns:
            Список объектов SpreadData
        """
        spreads = []
        
        perpetual_price = perpetual_ticker.get("mark_price", perpetual_ticker.get("last_price", 0))
        
        for futures_ticker in futures_tickers:
            futures_price = futures_ticker.get("mark_price", futures_ticker.get("last_price", 0))
            futures_symbol = futures_ticker.get("symbol", "")
            
            spread_data = SpreadCalculator.calculate_spread(
                perpetual_price=perpetual_price,
                futures_price=futures_price,
                futures_symbol=futures_symbol
            )
            spreads.append(spread_data)
        
        return spreads
    
    @staticmethod
    def should_alert(
        spread_percent: float,
        funding_rate: float,
        threshold_percent: float
    ) -> bool:
        """
        Проверить, нужно ли отправлять сигнал
        
        Условие: спред меньше чем Funding Rate на заданную величину в процентах
        
        Args:
            spread_percent: Спред в процентах
            funding_rate: Funding Rate (в процентах, например 0.01 = 1%)
            threshold_percent: Порог в процентах (например, 0.5 = 0.5%)
            
        Returns:
            True если нужно отправить сигнал
        """
        # Конвертируем funding_rate из десятичной дроби в проценты (если он в десятичном виде)
        # Например, 0.01 = 1%, поэтому умножаем на 100
        funding_rate_percent = funding_rate * 100 if funding_rate < 1 else funding_rate
        
        # Проверяем: спред < (funding_rate - threshold)
        return spread_percent < (funding_rate_percent - threshold_percent)

