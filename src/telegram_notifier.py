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
            logger.warning("Telegram бот не настроен")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML"
            )
            return True
        except TelegramError as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Telegram: {e}")
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

