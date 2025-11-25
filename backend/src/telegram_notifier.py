"""
Модуль для отправки уведомлений в Telegram
"""
import logging
from typing import Optional
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
import asyncio

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Инициализация Telegram бота
        
        Args:
            bot_token: Токен Telegram бота
            chat_id: ID чата для отправки сообщений
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot: Optional[Bot] = None
        
        if bot_token:
            self.bot = Bot(token=bot_token)
    
    async def send_message(self, message: str) -> bool:
        """
        Отправить сообщение в Telegram
        
        Args:
            message: Текст сообщения
            
        Returns:
            True если сообщение отправлено успешно
        """
        if not self.bot or not self.chat_id:
            logger.warning(f"Telegram бот не настроен: bot={self.bot is not None}, chat_id={bool(self.chat_id)}")
            return False
        
        try:
            logger.debug(f"Попытка отправить сообщение в Telegram (chat_id={self.chat_id})")
            result = await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"Сообщение успешно отправлено в Telegram. Message ID: {result.message_id}")
            return True
        except TelegramError as e:
            logger.error(f"Ошибка Telegram API при отправке сообщения: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Telegram: {e}", exc_info=True)
            return False
    
    def send_message_sync(self, message: str) -> bool:
        """
        Синхронная отправка сообщения в Telegram
        
        Args:
            message: Текст сообщения
            
        Returns:
            True если сообщение отправлено успешно
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_message(message))
    
    async def send_alert(
        self,
        futures_symbol: str,
        spread_percent: float,
        funding_rate: float,
        threshold_percent: float
    ) -> bool:
        """
        Отправить сигнал о спреде
        
        Args:
            futures_symbol: Символ срочного фьючерса
            spread_percent: Спред в процентах
            funding_rate: Funding Rate
            threshold_percent: Порог в процентах
            
        Returns:
            True если сообщение отправлено успешно
        """
        funding_rate_percent = funding_rate * 100 if funding_rate < 1 else funding_rate
        
        message = (
            f"🚨 <b>СИГНАЛ: Спред ниже порога</b>\n\n"
            f"📊 Фьючерс: <code>{futures_symbol}</code>\n"
            f"📈 Спред: <b>{spread_percent:.4f}%</b>\n"
            f"💰 Funding Rate: <b>{funding_rate_percent:.4f}%</b>\n"
            f"⚡ Порог: <b>{threshold_percent:.2f}%</b>\n"
            f"📉 Разница: <b>{funding_rate_percent - spread_percent:.4f}%</b>\n\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return await self.send_message(message)
    
    async def send_return_on_capital_alert(
        self,
        futures_symbol: str,
        return_on_capital: float,
        threshold: float,
        net_profit_usdt: float,
        days_until_expiration: float,
        capital_usdt: float = None,
        leverage: int = None
    ) -> bool:
        """
        Отправить сигнал о доходности на капитал
        
        Args:
            futures_symbol: Символ срочного фьючерса
            return_on_capital: Доходность на капитал в % годовых
            threshold: Порог в % годовых
            net_profit_usdt: Чистая прибыль в USDT
            days_until_expiration: Дней до экспирации
            capital_usdt: Капитал в USDT (опционально)
            leverage: Плечо (опционально)
            
        Returns:
            True если сообщение отправлено успешно
        """
        logger.info(f"Формирование сообщения для Telegram: {futures_symbol}, ROC={return_on_capital:.2f}%")
        
        message_parts = [
            f"🎯 <b>СИГНАЛ: Доходность на капитал превысила порог!</b>\n\n",
            f"📊 Фьючерс: <code>{futures_symbol}</code>\n",
            f"💰 Доходность на капитал: <b>{return_on_capital:.2f}% годовых</b>\n",
            f"⚡ Порог: <b>{threshold:.2f}% годовых</b>\n",
            f"💵 Чистая прибыль: <b>${net_profit_usdt:.2f} USDT</b>\n",
            f"📅 Дней до экспирации: <b>{days_until_expiration:.1f}</b>\n"
        ]
        
        if capital_usdt is not None:
            message_parts.append(f"💼 Капитал: <b>{capital_usdt:.2f} USDT</b>\n")
        if leverage is not None:
            message_parts.append(f"💪 Плечо: <b>{leverage}x</b>\n")
        
        message_parts.append(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = "".join(message_parts)
        
        logger.debug(f"Отправка сообщения в Telegram (chat_id={self.chat_id[:10]}...): {message[:100]}...")
        result = await self.send_message(message)
        logger.info(f"Результат отправки сообщения в Telegram: {result}")
        return result

