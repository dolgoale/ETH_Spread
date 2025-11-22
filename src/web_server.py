"""
Веб-сервер для отображения данных в реальном времени
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .monitor import SpreadMonitor

# Импорт config из корня проекта
import sys
from pathlib import Path
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
import config

logger = logging.getLogger(__name__)


class WebServer:
    """Веб-сервер для отображения данных мониторинга"""
    
    def __init__(self, monitor: SpreadMonitor):
        """
        Инициализация веб-сервера
        
        Args:
            monitor: Экземпляр монитора спредов
        """
        self.monitor = monitor
        self.app = FastAPI(title="ETH Spread Monitor")
        self.connected_clients: Set[WebSocket] = set()
        self.instruments_clients: Set[WebSocket] = set()
        self._instruments_broadcast_task = None
        self._is_running = False
        
        # Устанавливаем callback для обновления данных
        self.monitor.set_data_update_callback(self.broadcast_update)
        
        # Устанавливаем callback для получения конфигурации
        self.monitor.set_config_callback(lambda: config.get_updatable_config())
        
        # Регистрируем маршруты
        self._setup_routes()
    
    def _setup_routes(self):
        """Настроить маршруты веб-сервера"""
        
        # Регистрируем startup event для запуска фоновых задач
        @self.app.on_event("startup")
        async def startup_event():
            """Запуск фоновых задач при старте сервера"""
            self._is_running = True
            asyncio.create_task(self._start_instruments_broadcast())
            logger.info("Фоновая задача для обновления инструментов запущена")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            """Главная страница со списком инструментов"""
            from fastapi.responses import Response
            html = get_main_page_html_template()
            response = Response(
                content=html,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            return response
        
        @self.app.get("/api/data")
        async def get_data():
            """API endpoint для получения текущих данных"""
            return self.monitor.get_current_data()
        
        @self.app.get("/api/config")
        async def get_config():
            """API endpoint для получения текущей конфигурации"""
            return config.get_updatable_config()
        
        @self.app.put("/api/config")
        async def update_config_endpoint(config_data: dict):
            """API endpoint для обновления конфигурации"""
            try:
                success, message = config.update_config(config_data)
                
                # Обновляем параметры монитора напрямую для немедленного применения
                current_config = config.get_updatable_config()
                if "return_on_capital_threshold" in config_data:
                    # Порог доходности обновляется через конфигурацию, не требует прямого обновления монитора
                    pass
                if "capital_usdt" in config_data:
                    # Капитал обновляется через конфигурацию, не требует прямого обновления монитора
                    pass
                if "leverage" in config_data:
                    # Плечо обновляется через конфигурацию, не требует прямого обновления монитора
                    pass
                if "perpetual_symbol" in config_data:
                    self.monitor.perpetual_symbol = config_data["perpetual_symbol"]
                if "spread_threshold_percent" in config_data:
                    self.monitor.spread_threshold_percent = float(config_data["spread_threshold_percent"])
                if "funding_rate_history_days" in config_data:
                    self.monitor.funding_rate_history_days = int(config_data["funding_rate_history_days"])
                
                if success:
                    # Отправляем обновленную конфигурацию всем клиентам через WebSocket
                    await self._broadcast_config_update()
                
                return {"success": success, "message": message, "config": config.get_updatable_config()}
            except Exception as e:
                logger.error(f"Ошибка при обновлении конфигурации: {e}", exc_info=True)
                return {"success": False, "message": f"Ошибка: {str(e)}"}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint для real-time обновлений"""
            await websocket.accept()
            self.connected_clients.add(websocket)
            
            try:
                # Отправляем начальные данные
                initial_data = self.monitor.get_current_data()
                await websocket.send_json(initial_data)
                
                # Ждем сообщений от клиента (keep-alive)
                while True:
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    except asyncio.TimeoutError:
                        # Отправляем ping для поддержания соединения
                        await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                pass
            finally:
                self.connected_clients.discard(websocket)
        
        @self.app.websocket("/ws/instruments")
        async def websocket_instruments_endpoint(websocket: WebSocket):
            """WebSocket endpoint для real-time обновлений инструментов"""
            await websocket.accept()
            self.instruments_clients.add(websocket)
            logger.info(f"WebSocket клиент подключен к /ws/instruments. Всего: {len(self.instruments_clients)}")
            
            try:
                # Отправляем начальные данные сразу
                instruments_data = await self._get_instruments_data()
                await websocket.send_json({"type": "instruments", "data": instruments_data})
                
                # Ждем ping от клиента для поддержания соединения
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                        # Отвечаем на ping клиента
                        if message == "ping":
                            await websocket.send_text("pong")
                    except asyncio.TimeoutError:
                        # Отправляем ping для поддержания соединения
                        try:
                            await websocket.send_json({"type": "ping"})
                        except:
                            break  # Соединение разорвано
                    except WebSocketDisconnect:
                        raise
            except WebSocketDisconnect:
                logger.info("WebSocket клиент отключен от /ws/instruments")
            except Exception as e:
                logger.error(f"Ошибка в WebSocket соединении /ws/instruments: {e}", exc_info=True)
            finally:
                self.instruments_clients.discard(websocket)
                logger.info(f"WebSocket клиент удален. Осталось: {len(self.instruments_clients)}")
        
        @self.app.get("/ETH", response_class=HTMLResponse)
        async def eth_page():
            """Страница с данными по ETH"""
            from fastapi.responses import Response
            html = get_instruments_html_template("ETH", "ETHUSDT", "Ethereum")
            response = Response(
                content=html,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            return response
        
        @self.app.get("/BTC", response_class=HTMLResponse)
        async def btc_page():
            """Страница с данными по BTC"""
            from fastapi.responses import Response
            html = get_instruments_html_template("BTC", "BTCUSDT", "Bitcoin")
            response = Response(
                content=html,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            return response
        
        @self.app.get("/SOL", response_class=HTMLResponse)
        async def sol_page():
            """Страница с данными по SOL"""
            from fastapi.responses import Response
            html = get_instruments_html_template("SOL", "SOLUSDT", "Solana")
            response = Response(
                content=html,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            return response
        
        # Оставляем старый маршрут /instruments для обратной совместимости (редирект на /ETH)
        @self.app.get("/instruments", response_class=HTMLResponse)
        async def instruments_redirect():
            """Редирект со старой страницы /instruments на /ETH"""
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/ETH", status_code=301)
        
        @self.app.get("/api/instruments")
        async def get_instruments_endpoint():
            """API endpoint для получения данных по всем инструментам"""
            try:
                return await self._get_instruments_data()
            except Exception as e:
                logger.error(f"Ошибка при получении данных по инструментам: {e}", exc_info=True)
                return {"error": str(e)}
        
        @self.app.get("/api/instruments/{instrument}")
        async def get_instrument_data_endpoint(instrument: str):
            """API endpoint для получения данных по конкретному инструменту (ETH, BTC, SOL)"""
            try:
                # Маппинг символов инструментов
                instrument_map = {
                    "ETH": "ETHUSDT",
                    "BTC": "BTCUSDT",
                    "SOL": "SOLUSDT"
                }
                
                if instrument.upper() not in instrument_map:
                    return {"error": f"Неизвестный инструмент: {instrument}"}
                
                perpetual_symbol = instrument_map[instrument.upper()]
                return await self._get_instruments_data(perpetual_symbol=perpetual_symbol)
            except Exception as e:
                logger.error(f"Ошибка при получении данных по инструменту {instrument}: {e}", exc_info=True)
                return {"error": str(e)}
    
    async def _get_instruments_data(self, perpetual_symbol: Optional[str] = None):
        """Метод для получения данных по всем инструментам
        
        Args:
            perpetual_symbol: Символ бессрочного фьючерса (например, ETHUSDT, BTCUSDT, SOLUSDT).
                              Если не указан, используется из конфигурации.
        """
        import concurrent.futures
        from datetime import datetime
        from .spread_calculator import SpreadCalculator
        
        # Безрисковая процентная ставка для расчета справедливой цены
        RISK_FREE_RATE_ANNUAL = 0.04  # 4% годовых
        
        # Получаем данные напрямую через bybit_client
        bybit_client = self.monitor.bybit_client
        current_config = self.monitor._get_config()
        
        # Используем переданный символ или берем из конфигурации
        if perpetual_symbol is None:
            perpetual_symbol = current_config.get("perpetual_symbol", self.monitor.perpetual_symbol)
        
        # Получаем ВСЕ доступные срочные фьючерсы для базового символа
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
        
        # Получаем список всех доступных срочных фьючерсов
        available_futures = await loop.run_in_executor(
            executor,
            bybit_client.get_available_futures,
            perpetual_symbol
        )
        
        # Извлекаем символы из списка доступных фьючерсов
        futures_symbols = [f["symbol"] for f in available_futures] if available_futures else []
        
        # Получаем данные по бессрочному фьючерсу
        perpetual_ticker = await loop.run_in_executor(
            executor,
            bybit_client.get_perpetual_ticker,
            perpetual_symbol
        )
        
        # Получаем текущий Funding Rate в моменте
        current_funding_rate_data = await loop.run_in_executor(
            executor,
            bybit_client.get_current_funding_rate,
            perpetual_symbol
        )
        current_funding_rate = current_funding_rate_data.get("funding_rate", 0) if current_funding_rate_data else 0
        
        # Получаем суммарный FR за 3 месяца (90 дней)
        total_fr_3months = await loop.run_in_executor(
            executor,
            bybit_client.calculate_total_funding_rate,
            perpetual_symbol,
            90  # 90 дней (3 месяца)
        )
        if total_fr_3months is None:
            total_fr_3months = 0
        
        # Получаем суммарный FR за 6 месяцев (180 дней)
        total_fr_6months = await loop.run_in_executor(
            executor,
            bybit_client.calculate_total_funding_rate,
            perpetual_symbol,
            180  # 180 дней (6 месяцев)
        )
        if total_fr_6months is None:
            total_fr_6months = 0
        
        # Получаем суммарный FR за 365 дней
        total_fr_365days = await loop.run_in_executor(
            executor,
            bybit_client.calculate_total_funding_rate,
            perpetual_symbol,
            365  # 365 дней (год)
        )
        if total_fr_365days is None:
            total_fr_365days = 0
        
        # Получаем усредненный Funding Rate за последний месяц (30 дней) для расчетов срочных фьючерсов
        average_funding_rate = await loop.run_in_executor(
            executor,
            bybit_client.calculate_average_funding_rate,
            perpetual_symbol,
            30  # 30 дней (месяц)
        )
        if average_funding_rate is None:
            average_funding_rate = current_funding_rate if current_funding_rate else 0
        
        # Получаем spot цену ETH
        spot_ticker = await loop.run_in_executor(
            executor,
            bybit_client.get_spot_ticker,
            perpetual_symbol
        )
        
        spot_price = spot_ticker.get("last_price", 0) if spot_ticker else 0
        
        # Получаем данные по всем срочным фьючерсам параллельно
        futures_tasks = [
            loop.run_in_executor(
                executor,
                bybit_client.get_futures_ticker,
                symbol
            )
            for symbol in futures_symbols
        ]
        
        futures_tickers = await asyncio.gather(*futures_tasks)
        
        # Создаем словарь delivery_times для расчета спредов
        futures_delivery_times = {}
        for future_info in available_futures:
            symbol = future_info.get("symbol")
            delivery_time_ms = future_info.get("delivery_time")
            if symbol and delivery_time_ms:
                delivery_time = datetime.fromtimestamp(delivery_time_ms / 1000)
                futures_delivery_times[symbol] = delivery_time
        
        # Рассчитываем спреды для каждого фьючерса
        if perpetual_ticker:
            spreads = SpreadCalculator.calculate_spreads(
                perpetual_ticker,
                [t for t in futures_tickers if t]
            )
            
            # Создаем словарь спредов по символу
            spreads_dict = {spread.futures_symbol: spread for spread in spreads}
        else:
            spreads_dict = {}
        
        # Стандартный Funding Rate = 0.01% за 8 часов (0.0001 в десятичном виде)
        STANDARD_FUNDING_RATE = 0.0001  # 0.01% за 8 часов
        
        # Комиссии ByBit VIP2 для maker сделок (в процентах)
        # 4 сделки: покупка срочного (long), продажа срочного (закрытие long),
        # продажа бессрочного (short), покупка бессрочного (закрытие short)
        # Maker fee для VIP2 на фьючерсах: 0.0290% за сделку
        VIP2_MAKER_FEE_PERCENT = 0.0290  # 0.0290% за сделку
        TOTAL_TRADING_FEES = VIP2_MAKER_FEE_PERCENT * 4  # 4 сделки = 0.1160%
        
        # Формируем ответ с данными и информацией о дате экспирации, спреде и Funding Rate
        futures_data = []
        for i, ticker in enumerate(futures_tickers):
            if ticker:
                symbol = ticker.get("symbol", "")
                future_info = {
                    "symbol": symbol,
                    "mark_price": ticker.get("mark_price", 0),
                    "last_price": ticker.get("last_price", 0),
                    "timestamp": ticker.get("timestamp", 0)
                }
                
                # Добавляем информацию о дате экспирации если доступна
                if i < len(available_futures):
                    delivery_time = available_futures[i].get("delivery_time", 0)
                    if delivery_time:
                        future_info["delivery_time"] = delivery_time
                        # Рассчитываем дни до экспирации
                        delivery_dt = datetime.fromtimestamp(delivery_time / 1000)
                        days_until_exp = (delivery_dt - datetime.now()).total_seconds() / 86400.0
                        future_info["days_until_expiration"] = days_until_exp if days_until_exp > 0 else None
                
                # Добавляем данные о спреде, если они есть
                if symbol in spreads_dict:
                    spread_data = spreads_dict[symbol]
                    future_info["spread_percent"] = spread_data.spread_percent
                    
                    # Рассчитываем Funding Rate до экспирации на основе среднего FR за количество дней до экспирации
                    if future_info.get("days_until_expiration"):
                        days_until_exp = future_info["days_until_expiration"]
                        
                        # Получаем mark_price срочного фьючерса
                        futures_mark_price = ticker.get("mark_price", 0)
                        
                        # Безрисковая процентная ставка (r) - ставка по доллару за год
                        risk_free_rate_annual = RISK_FREE_RATE_ANNUAL
                        
                        # Время до экспирации в долях года (T)
                        time_to_expiration_years = days_until_exp / 365.0
                        
                        # Рассчитываем справедливую цену срочного фьючерса по классической модели
                        # F = S × (1 + r × T)
                        # где F - справедливая цена фьючерса, S - spot цена ETH, r - безрисковая ставка, T - время в долях года
                        fair_futures_price = spot_price * (1 + risk_free_rate_annual * time_to_expiration_years) if spot_price > 0 else 0
                        future_info["fair_futures_price"] = fair_futures_price
                        
                        # Справедливый спред % = разница в % между справедливой ценой срочного фьючерса и ценой бессрочного
                        # Справедливый спред % = (fair_futures_price - perpetual_mark_price) / perpetual_mark_price * 100
                        perpetual_mark_price = perpetual_ticker.get("mark_price", 0) if perpetual_ticker else 0
                        fair_spread_percent = ((fair_futures_price - perpetual_mark_price) / perpetual_mark_price * 100) if perpetual_mark_price > 0 else None
                        future_info["fair_spread_percent"] = fair_spread_percent
                        
                        # Получаем суммарный FR за количество дней, равное дням до экспирации
                        # Используем полную историю за нужный период (метод поддерживает множественные запросы)
                        days_for_fr = int(days_until_exp) if days_until_exp > 0 else 30
                        # Ограничиваем максимальное количество дней (365 - максимум доступной истории)
                        days_for_fr = min(days_for_fr, 365)
                        
                        # Получаем полную историю FR за период, равный дням до экспирации
                        history = await loop.run_in_executor(
                            executor,
                            bybit_client.get_funding_rate_history,
                            perpetual_symbol,
                            days_for_fr
                        )
                        
                        if history:
                            # Суммируем все FR из истории - это суммарный FR за период истории
                            rates = [item["funding_rate"] for item in history]
                            total_fr_for_days = sum(rates) if rates else 0
                            
                            # Количество выплат в истории (может быть меньше, если история неполная)
                            actual_payments_in_history = len(history)
                            expected_payments_in_history = days_for_fr * 3
                            
                            # Если получили полную историю, используем сумму напрямую
                            # Если период до экспирации отличается от периода истории, масштабируем
                            if actual_payments_in_history >= expected_payments_in_history * 0.95:  # 95% порог для учета возможных пропусков
                                # История почти полная - используем средний FR за выплату и масштабируем на период до экспирации
                                avg_fr_per_payment = total_fr_for_days / actual_payments_in_history if actual_payments_in_history > 0 else 0
                                payments_until_exp = days_until_exp * 3
                                funding_rate_until_exp = avg_fr_per_payment * payments_until_exp * 100
                            else:
                                # История неполная - масштабируем имеющийся суммарный FR
                                avg_fr_per_payment = total_fr_for_days / actual_payments_in_history if actual_payments_in_history > 0 else 0
                                payments_until_exp = days_until_exp * 3
                                funding_rate_until_exp = avg_fr_per_payment * payments_until_exp * 100
                        else:
                            # Fallback: рассчитываем суммарный FR на основе текущего FR
                            avg_fr_per_payment = current_funding_rate if current_funding_rate else 0
                            payments_until_exp = days_until_exp * 3
                            funding_rate_until_exp = avg_fr_per_payment * payments_until_exp * 100
                            total_fr_for_days = current_funding_rate * days_for_fr * 3
                        
                        future_info["funding_rate_until_expiration"] = funding_rate_until_exp
                        future_info["average_fr_days_used"] = days_for_fr  # Сохраняем количество дней, за которое рассчитан FR
                        
                        # Стандартный FR до экспирации (суммарный)
                        # Стандартный FR = 0.0001 (0.01%) за каждую выплату (8 часов)
                        # Количество выплат до экспирации (уже рассчитано выше)
                        # payments_until_exp = days_until_exp * 3
                        
                        # Суммарный стандартный FR до экспирации = стандартный FR × количество выплат
                        standard_fr_until_exp = STANDARD_FUNDING_RATE * payments_until_exp * 100
                        
                        future_info["standard_funding_rate_until_expiration"] = standard_fr_until_exp
                        
                        # Чистая прибыль (суммарный FR за кол-во дней до экспирации) = FR до экспирации - Спред % - Комиссии
                        net_profit_current_fr = funding_rate_until_exp - spread_data.spread_percent - TOTAL_TRADING_FEES
                        future_info["net_profit_current_fr"] = net_profit_current_fr
                        
                        # Чистая прибыль (стандартный FR) = стандартный FR до экспирации - Спред % - Комиссии
                        net_profit_standard_fr = standard_fr_until_exp - spread_data.spread_percent - TOTAL_TRADING_FEES
                        future_info["net_profit_standard_fr"] = net_profit_standard_fr
                    else:
                        future_info["fair_futures_price"] = None
                        future_info["fair_spread_percent"] = None
                        future_info["funding_rate_until_expiration"] = None
                        future_info["standard_funding_rate_until_expiration"] = None
                        future_info["net_profit_current_fr"] = None
                        future_info["net_profit_standard_fr"] = None
                else:
                    future_info["fair_futures_price"] = None
                    future_info["fair_spread_percent"] = None
                
                futures_data.append(future_info)
        
        # Для бессрочного фьючерса добавляем текущий Funding Rate и spot цену
        perpetual_data = None
        if perpetual_ticker:
            perpetual_data = {
                "symbol": perpetual_symbol,
                "mark_price": perpetual_ticker.get("mark_price", 0),
                "last_price": perpetual_ticker.get("last_price", 0),
                "timestamp": perpetual_ticker.get("timestamp", 0),
                "spot_price": spot_price,  # Spot цена ETH
                "current_funding_rate": current_funding_rate * 100 if current_funding_rate else 0,  # Текущий FR за последние 8 часов (в процентах)
                "total_funding_rate_3months": total_fr_3months * 100 if total_fr_3months else 0,  # Суммарный FR за 3 месяца (в процентах)
                "total_funding_rate_6months": total_fr_6months * 100 if total_fr_6months else 0,  # Суммарный FR за 6 месяцев (в процентах)
                "total_funding_rate_365days": total_fr_365days * 100 if total_fr_365days else 0  # Суммарный FR за 365 дней (в процентах)
            }
        
        return {
            "perpetual": perpetual_data,
            "futures": futures_data,
            "risk_free_rate_annual": RISK_FREE_RATE_ANNUAL * 100  # В процентах для отображения
        }
    
    def broadcast_update(self, data: Dict):
        """
        Отправить обновление всем подключенным клиентам
        
        Args:
            data: Данные для отправки
        """
        if not self.connected_clients:
            return
        
        # Создаем задачу для асинхронной рассылки
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._broadcast(data))
            else:
                loop.run_until_complete(self._broadcast(data))
        except RuntimeError:
            # Если event loop не доступен, создаем новый
            asyncio.create_task(self._broadcast(data))
    
    async def _broadcast(self, data: Dict):
        """Асинхронная рассылка данных всем клиентам"""
        disconnected = set()
        
        for client in self.connected_clients:
            try:
                await client.send_json(data)
            except Exception as e:
                logger.error(f"Ошибка при отправке данных клиенту: {e}")
                disconnected.add(client)
        
        # Удаляем отключенных клиентов
        self.connected_clients -= disconnected
    
    async def _broadcast_config_update(self):
        """Отправить обновленную конфигурацию всем клиентам"""
        if not self.connected_clients:
            return
        
        config_data = {
            "type": "config_update",
            "config": config.get_updatable_config()
        }
        
        await self._broadcast(config_data)
    
    async def _start_instruments_broadcast(self):
        """Запустить фоновую задачу для постоянной отправки данных инструментов"""
        async def broadcast_instruments_loop():
            """Бесконечный цикл для отправки данных инструментов всем подключенным клиентам"""
            logger.info("Фоновая задача broadcast_instruments_loop запущена")
            while self._is_running:
                try:
                    # Получаем данные инструментов (включая spot цену)
                    instruments_data = await self._get_instruments_data()
                    
                    # Отправляем только если есть подключенные клиенты
                    if self.instruments_clients:
                        logger.debug(f"Отправка данных {len(self.instruments_clients)} клиентам")
                        await self._broadcast_instruments({
                            "type": "instruments",
                            "data": instruments_data
                        })
                    
                    # Обновляем данные каждые 2 секунды
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Ошибка в цикле broadcast_instruments: {e}", exc_info=True)
                    await asyncio.sleep(2)  # Пауза перед повтором
        
        # Создаем фоновую задачу
        self._instruments_broadcast_task = asyncio.create_task(broadcast_instruments_loop())
        logger.info("Фоновая задача для broadcast инструментов запущена")
    
    async def _broadcast_instruments(self, data: Dict):
        """Отправить данные инструментов всем подключенным клиентам WebSocket"""
        if not self.instruments_clients:
            return
        
        disconnected = set()
        
        for client in self.instruments_clients:
            try:
                await client.send_json(data)
            except Exception as e:
                logger.error(f"Ошибка при отправке данных инструментов клиенту: {e}")
                disconnected.add(client)
        
        # Удаляем отключенных клиентов
        self.instruments_clients -= disconnected
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Запустить веб-сервер
        
        Args:
            host: Хост для прослушивания
            port: Порт для прослушивания
        """
        uvicorn.run(self.app, host=host, port=port)


def get_html_template() -> str:
    """Получить HTML шаблон для веб-интерфейса"""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ETH Spread Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            margin-top: 10px;
        }
        
        .status.connected {
            background: #10b981;
            color: white;
        }
        
        .status.disconnected {
            background: #ef4444;
            color: white;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .card h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 20px;
        }
        
        .funding-rate {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .rate-item {
            display: flex;
            justify-content: space-between;
            padding: 15px;
            background: #f3f4f6;
            border-radius: 10px;
        }
        
        .rate-item .label {
            font-weight: 600;
            color: #6b7280;
        }
        
        .rate-item .value {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }
        
        .spreads-container {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .spread-item {
            padding: 20px;
            background: #f3f4f6;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        
        .spread-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .spread-symbol {
            font-weight: bold;
            font-size: 18px;
            color: #1f2937;
        }
        
        .spread-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .spread-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 14px;
            color: #6b7280;
        }
        
        .spread-details div {
            display: flex;
            justify-content: space-between;
        }
        
        .alert {
            padding: 15px;
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            border-radius: 10px;
            margin-top: 15px;
            color: #92400e;
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .timestamp {
            text-align: right;
            color: #9ca3af;
            font-size: 12px;
            margin-top: 10px;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .tab {
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.7);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .tab:hover {
            background: rgba(255, 255, 255, 0.9);
        }
        
        .tab.active {
            background: #667eea;
            color: white;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .config-form {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .form-group label {
            font-weight: 600;
            color: #374151;
        }
        
        .form-group input,
        .form-group textarea {
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-group small {
            color: #6b7280;
            font-size: 12px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5568d3;
        }
        
        .btn-secondary {
            background: #6b7280;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #4b5563;
        }
        
        .form-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }
        
        .message {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        
        .message.success {
            background: #d1fae5;
            color: #065f46;
            border-left: 4px solid #10b981;
        }
        
        .message.error {
            background: #fee2e2;
            color: #991b1b;
            border-left: 4px solid #ef4444;
        }
        
        .message.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 ETH Spread Monitor</h1>
            <p>Мониторинг спредов между срочными и бессрочными фьючерсами на ByBit</p>
            <span id="status" class="status disconnected">Отключено</span>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('monitoring')">📊 Мониторинг</button>
            <button class="tab" onclick="showTab('settings')">⚙️ Настройки</button>
        </div>
        
        <div id="monitoring-tab" class="tab-content active">
        <div class="main-content">
            <div class="card">
                <h2>💰 Funding Rate</h2>
                <div class="funding-rate" id="funding-rate">
                    <div class="rate-item">
                        <span class="label">Текущий FR:</span>
                        <span class="value" id="current-fr">-</span>
                    </div>
                    <div class="rate-item">
                        <span class="label">Средний FR (7 дней):</span>
                        <span class="value" id="avg-fr">-</span>
                    </div>
                </div>
            </div>
            
            <div class="card full-width">
                <h2>📈 Спреды по фьючерсам</h2>
                <div class="spreads-container" id="spreads">
                    <div style="text-align: center; color: #9ca3af; padding: 40px;">
                        Загрузка данных...
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card full-width">
            <div class="timestamp">
                Последнее обновление: <span id="last-update">-</span>
            </div>
        </div>
        </div>
        
        <div id="settings-tab" class="tab-content">
            <div class="card full-width">
                <h2>⚙️ Настройки мониторинга</h2>
                <div id="config-message" class="message"></div>
                <form id="config-form" class="config-form">
                    <div class="form-group">
                        <label for="spread_threshold_percent">Порог спреда (%)</label>
                        <input type="number" id="spread_threshold_percent" name="spread_threshold_percent" 
                               step="0.01" min="0" max="100" required>
                        <small>Порог в процентах для отправки сигнала. Если спред меньше чем (Funding Rate - Порог), будет отправлен сигнал.</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="funding_rate_history_days">Дни истории Funding Rate</label>
                        <input type="number" id="funding_rate_history_days" name="funding_rate_history_days" 
                               min="1" max="365" required>
                        <small>Количество дней для расчета среднего Funding Rate (от 1 до 365).</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="monitoring_interval_seconds">Интервал мониторинга (секунды)</label>
                        <input type="number" id="monitoring_interval_seconds" name="monitoring_interval_seconds" 
                               min="1" max="3600" required>
                        <small>Интервал обновления данных в секундах (от 1 до 3600).</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="perpetual_symbol">Символ бессрочного фьючерса</label>
                        <input type="text" id="perpetual_symbol" name="perpetual_symbol" required>
                        <small>Символ бессрочного фьючерса (например, ETHUSDT). Символы срочных фьючерсов получаются автоматически.</small>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="resetForm()">Сбросить</button>
                        <button type="submit" class="btn btn-primary">Сохранить</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket подключен');
                document.getElementById('status').textContent = 'Подключено';
                document.getElementById('status').className = 'status connected';
                reconnectAttempts = 0;
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'ping') {
                    return;
                }
                
                if (data.type === 'config_update') {
                    // Обновление конфигурации через WebSocket
                    loadConfig();
                    showMessage('Конфигурация обновлена', 'success');
                    return;
                }
                
                updateUI(data);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket ошибка:', error);
            };
            
            ws.onclose = () => {
                console.log('WebSocket отключен');
                document.getElementById('status').textContent = 'Отключено';
                document.getElementById('status').className = 'status disconnected';
                
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(connect, 3000 * reconnectAttempts);
                }
            };
        }
        
        function updateUI(data) {
            // Обновляем Funding Rate
            if (data.funding_rate) {
                const fr = data.funding_rate;
                document.getElementById('current-fr').textContent = 
                    (fr.current_rate * 100).toFixed(3) + '%';
                document.getElementById('avg-fr').textContent = 
                    (fr.average_rate * 100).toFixed(3) + '%';
            }
            
            // Обновляем спреды
            const spreadsContainer = document.getElementById('spreads');
            if (data.spreads && Object.keys(data.spreads).length > 0) {
                spreadsContainer.innerHTML = '';
                
                Object.values(data.spreads).forEach(spread => {
                    const spreadItem = document.createElement('div');
                    spreadItem.className = 'spread-item';
                    
                    const spreadPercent = spread.spread_percent.toFixed(3);
                    const isNegative = spread.spread_percent < 0;
                    
                    spreadItem.innerHTML = `
                        <div class="spread-header">
                            <span class="spread-symbol">${spread.futures_symbol}</span>
                            <span class="spread-value" style="color: ${isNegative ? '#ef4444' : '#667eea'}">
                                ${spreadPercent}%
                            </span>
                        </div>
                        <div class="spread-details">
                            <div>
                                <span>Бессрочный:</span>
                                <span><b>$${spread.perpetual_price.toFixed(2)}</b></span>
                            </div>
                            <div>
                                <span>Срочный:</span>
                                <span><b>$${spread.futures_price.toFixed(2)}</b></span>
                            </div>
                            <div>
                                <span>Спред:</span>
                                <span><b>$${spread.spread.toFixed(2)}</b></span>
                            </div>
                            <div>
                                <span>Спред %:</span>
                                <span><b>${spreadPercent}%</b></span>
                            </div>
                        </div>
                    `;
                    
                    spreadsContainer.appendChild(spreadItem);
                });
            } else {
                spreadsContainer.innerHTML = 
                    '<div style="text-align: center; color: #9ca3af; padding: 40px;">Нет данных</div>';
            }
            
            // Обновляем время последнего обновления
            if (data.timestamp) {
                const date = new Date(data.timestamp);
                document.getElementById('last-update').textContent = 
                    date.toLocaleString('ru-RU');
            }
        }
        
        // Функция переключения вкладок
        function showTab(tabName) {
            // Скрываем все вкладки
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Убираем активный класс у всех кнопок
            document.querySelectorAll('.tab').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Показываем выбранную вкладку
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
            
            // Если открыли вкладку настроек, загружаем конфигурацию
            if (tabName === 'settings') {
                loadConfig();
            }
        }
        
        // Загрузка конфигурации
        function loadConfig() {
            fetch('/api/config')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('spread_threshold_percent').value = data.spread_threshold_percent || '';
                    document.getElementById('funding_rate_history_days').value = data.funding_rate_history_days || '';
                    document.getElementById('monitoring_interval_seconds').value = data.monitoring_interval_seconds || '';
                    document.getElementById('perpetual_symbol').value = data.perpetual_symbol || '';
                })
                .catch(error => {
                    console.error('Ошибка загрузки конфигурации:', error);
                    showMessage('Ошибка загрузки конфигурации', 'error');
                });
        }
        
        // Отправка формы конфигурации
        document.getElementById('config-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = {
                spread_threshold_percent: parseFloat(document.getElementById('spread_threshold_percent').value),
                funding_rate_history_days: parseInt(document.getElementById('funding_rate_history_days').value),
                monitoring_interval_seconds: parseInt(document.getElementById('monitoring_interval_seconds').value),
                perpetual_symbol: document.getElementById('perpetual_symbol').value.trim()
            };
            
            try {
                const response = await fetch('/api/config', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showMessage(result.message || 'Конфигурация успешно сохранена', 'success');
                    // Обновляем данные в форме
                    loadConfig();
                } else {
                    showMessage(result.message || 'Ошибка при сохранении конфигурации', 'error');
                }
            } catch (error) {
                console.error('Ошибка при сохранении конфигурации:', error);
                showMessage('Ошибка при сохранении конфигурации: ' + error.message, 'error');
            }
        });
        
        // Сброс формы
        function resetForm() {
            loadConfig();
        }
        
        // Показать сообщение
        function showMessage(text, type) {
            const messageEl = document.getElementById('config-message');
            messageEl.textContent = text;
            messageEl.className = 'message ' + type + ' show';
            
            setTimeout(() => {
                messageEl.classList.remove('show');
            }, 5000);
        }
        
        // Подключаемся при загрузке страницы
        connect();
        
        // Также загружаем начальные данные через REST API
        fetch('/api/data')
            .then(response => response.json())
            .then(data => updateUI(data))
            .catch(error => console.error('Ошибка загрузки данных:', error));
    </script>
</body>
</html>"""


def get_main_page_html_template() -> str:
    """Получить HTML шаблон для главной страницы со списком инструментов"""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BBSpreads - Мониторинг спредов</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .container {
            max-width: 1200px;
            width: 100%;
        }
        
        .header {
            text-align: center;
            margin-bottom: 50px;
            color: white;
        }
        
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .instruments-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
        }
        
        .instrument-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
            text-align: center;
            transition: transform 0.3s, box-shadow 0.3s;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        
        .instrument-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
        }
        
        .instrument-card h2 {
            font-size: 2.5em;
            margin-bottom: 15px;
            color: #667eea;
        }
        
        .instrument-card p {
            color: #6b7280;
            font-size: 1.1em;
        }
        
        .instrument-emoji {
            font-size: 4em;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 BBSpreads</h1>
            <p>Мониторинг спредов между срочными и бессрочными фьючерсами на ByBit</p>
        </div>
        
        <div class="instruments-grid">
            <a href="/ETH" class="instrument-card">
                <div class="instrument-emoji">Ξ</div>
                <h2>ETH</h2>
                <p>Ethereum</p>
            </a>
            
            <a href="/BTC" class="instrument-card">
                <div class="instrument-emoji">₿</div>
                <h2>BTC</h2>
                <p>Bitcoin</p>
            </a>
            
            <a href="/SOL" class="instrument-card">
                <div class="instrument-emoji">◎</div>
                <h2>SOL</h2>
                <p>Solana</p>
            </a>
        </div>
    </div>
</body>
</html>"""


def get_instruments_html_template(instrument_code: str = "ETH", perpetual_symbol: str = "ETHUSDT", instrument_name: str = "Ethereum") -> str:
    """Получить HTML шаблон для отображения инструмента
    
    Args:
        instrument_code: Код инструмента (ETH, BTC, SOL)
        perpetual_symbol: Символ бессрочного фьючерса (ETHUSDT, BTCUSDT, SOLUSDT)
        instrument_name: Название инструмента (Ethereum, Bitcoin, Solana)
    """
    # Используем обычную строку с .format() для избежания проблем с фигурными скобками в JavaScript
    # Все фигурные скобки в JavaScript должны быть удвоены {{ и }}
    template = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{instrument_code} Spread Monitor - {instrument_name}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        
        .header h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.5em;
            font-weight: 500;
        }
        
        .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            margin-top: 10px;
        }
        
        .status.connected {
            background: #10b981;
            color: white;
        }
        
        .status.disconnected {
            background: #ef4444;
            color: white;
        }
        
        .instruments-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.2em;
            font-weight: 500;
            padding-bottom: 8px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .instruments-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.85em;
        }
        
        .instruments-table th,
        .instruments-table td {
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .instruments-table th {
            background: #f3f4f6;
            font-weight: 500;
            color: #374151;
            position: sticky;
            top: 0;
        }
        
        .instruments-table tr:hover {
            background: #f9fafb;
        }
        
        .instruments-table tr.highlighted-row {
            font-weight: bold !important;
        }
        
        .instruments-table tr.highlighted-row td {
            font-weight: bold !important;
        }
        
        /* Рамка для выделенных колонок в выделенных строках */
        .instruments-table tr.highlighted-row td:nth-child(6),
        .instruments-table tr.highlighted-row td:nth-child(7),
        .instruments-table tr.highlighted-row td:nth-child(8),
        .instruments-table tr.highlighted-row td:nth-child(10),
        .instruments-table tr.highlighted-row td:nth-child(12),
        .instruments-table tr.highlighted-row td:nth-child(13) {
            border: 2px solid #667eea !important;
            border-radius: 4px;
            padding: 4px 8px !important;
            background-color: rgba(102, 126, 234, 0.05) !important;
        }
        
        /* Жирный шрифт для заголовков выделенных колонок */
        .instruments-table thead th:nth-child(6),
        .instruments-table thead th:nth-child(7),
        .instruments-table thead th:nth-child(8),
        .instruments-table thead th:nth-child(10),
        .instruments-table thead th:nth-child(12),
        .instruments-table thead th:nth-child(13) {
            font-weight: bold !important;
        }
        
        .instrument-symbol {
            font-weight: 500;
            color: #1f2937;
            font-size: 0.9em;
        }
        
        .price {
            font-size: 0.9em;
            font-weight: 400;
        }
        
        .price.mark {
            color: #10b981;
        }
        
        .price.last {
            color: #3b82f6;
        }
        
        .timestamp {
            color: #6b7280;
            font-size: 0.8em;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }
        
        .error {
            background: #fee2e2;
            color: #991b1b;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #ef4444;
        }
        
        .last-update {
            text-align: right;
            color: #9ca3af;
            font-size: 12px;
            margin-top: 20px;
        }
        
        .fees-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.85em;
        }
        
        .fees-table th,
        .fees-table td {
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .fees-table th {
            background: #f3f4f6;
            font-weight: 500;
            color: #374151;
        }
        
        .fees-table tr:hover {
            background: #f9fafb;
        }
        
        .fees-table .fee-value {
            color: #667eea;
            font-weight: 500;
        }
        
        .fees-table .fee-total {
            font-weight: 500;
            color: #1f2937;
            background: #f3f4f6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {instrument_code} Spread Monitor - {instrument_name}</h1>
            <p>Данные по инструменту {instrument_name} ({perpetual_symbol})</p>
            <div style="margin-top: 8px; font-size: 0.9em; color: #6b7280;">
                <span>Безрисковая ставка: <strong id="risk-free-rate">4.00</strong>% годовых</span>
            </div>
            <span id="status" class="status disconnected">Отключено</span>
        </div>
        
        <div class="instruments-container">
            <div class="section">
                <h2>📈 Бессрочный фьючерс и Spot</h2>
                <div id="perpetual-container">
                    <div class="loading">Загрузка данных...</div>
                </div>
            </div>
            
            <div class="section">
                <h2>📅 Срочные фьючерсы</h2>
                <div style="margin-bottom: 20px; padding: 15px; background: rgba(255, 255, 255, 0.7); border-radius: 8px;">
                    <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label for="capital-input" style="font-weight: 600; color: #374151;">Капитал (USDT):</label>
                            <input type="number" id="capital-input" value="50000" min="1" step="1" 
                                   style="padding: 8px 12px; border: 2px solid #e5e7eb; border-radius: 6px; font-size: 14px; width: 120px;">
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label for="leverage-input" style="font-weight: 600; color: #374151;">Плечо (x):</label>
                            <input type="number" id="leverage-input" value="20" min="1" max="200" step="1" 
                                   style="padding: 8px 12px; border: 2px solid #e5e7eb; border-radius: 6px; font-size: 14px; width: 80px;">
                        </div>
                        <button onclick="updateContractsCount()" 
                                style="padding: 8px 20px; background: #667eea; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px; transition: background 0.3s;"
                                onmouseover="this.style.background='#5568d3'" 
                                onmouseout="this.style.background='#667eea'">
                            Обновить
                        </button>
                        <div style="display: flex; align-items: center; gap: 10px; margin-left: auto;">
                            <span style="font-weight: 600; color: #374151;">Количество контрактов:</span>
                            <span id="contracts-count" style="color: #667eea; font-weight: 600; font-size: 16px;">-</span>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap; margin-top: 15px; padding-top: 15px; border-top: 1px solid #e5e7eb;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label for="return-threshold-input" style="font-weight: 600; color: #374151;">Порог доходности на капитал (% годовых):</label>
                            <input type="number" id="return-threshold-input" value="50" min="0" step="0.1" 
                                   style="padding: 8px 12px; border: 2px solid #e5e7eb; border-radius: 6px; font-size: 14px; width: 120px;">
                        </div>
                        <button onclick="updateReturnThreshold()" 
                                style="padding: 8px 20px; background: #10b981; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px; transition: background 0.3s;"
                                onmouseover="this.style.background='#059669'" 
                                onmouseout="this.style.background='#10b981'">
                            Сохранить порог
                        </button>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 0.9em; color: #6b7280;">При доходности выше порога будет отправлено уведомление в Telegram</span>
                        </div>
                    </div>
                </div>
                <div id="futures-container">
                    <div class="loading">Загрузка данных...</div>
                </div>
            </div>
            
            <div class="section">
                <h2>💰 Комиссии ByBit VIP2 (учтены в расчете)</h2>
                <div id="fees-container">
                    <div class="loading">Загрузка данных...</div>
                </div>
            </div>
            
            <div class="last-update">
                Последнее обновление: <span id="last-update">-</span>
            </div>
        </div>
    </div>
    
    <script>
        let updateInterval = null;
        // Глобальная переменная для хранения цены бессрочного фьючерса
        let globalPerpetualMarkPrice = null;
        
        function formatPrice(price) {
            return new Intl.NumberFormat('ru-RU', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(price);
        }
        
        function formatTimestamp(timestamp) {
            if (!timestamp || timestamp === 0) return 'N/A';
            const date = new Date(timestamp);
            return date.toLocaleString('ru-RU');
        }
        
        function updateStatus(connected) {
            const statusEl = document.getElementById('status');
            if (connected) {
                statusEl.textContent = 'Подключено';
                statusEl.className = 'status connected';
            } else {
                statusEl.textContent = 'Отключено';
                statusEl.className = 'status disconnected';
            }
        }
        
        function updateReturnThreshold() {
            const thresholdInput = document.getElementById('return-threshold-input');
            if (!thresholdInput) return;
            
            const threshold = parseFloat(thresholdInput.value);
            if (isNaN(threshold) || threshold < 0) {
                alert('Введите корректное значение порога (от 0 и выше)');
                return;
            }
            
            // Отправляем запрос на обновление конфигурации
            fetch('/api/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    return_on_capital_threshold: threshold
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Порог доходности успешно сохранен: ' + threshold + '% годовых');
                } else {
                    alert('Ошибка при сохранении порога: ' + (data.message || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                console.error('Ошибка при сохранении порога:', error);
                alert('Ошибка при сохранении порога');
            });
        }
        
        function updateContractsCount() {
            console.log('Кнопка "Обновить" нажата');
            
            const capitalInput = document.getElementById('capital-input');
            const leverageInput = document.getElementById('leverage-input');
            const contractsCountEl = document.getElementById('contracts-count');
            
            if (!capitalInput || !leverageInput || !contractsCountEl) {
                console.error('Не найдены элементы ввода:', {
                    capitalInput: !!capitalInput,
                    leverageInput: !!leverageInput,
                    contractsCountEl: !!contractsCountEl
                });
                return;
            }
            
            const capital = parseFloat(capitalInput.value) || 0;
            const leverage = parseFloat(leverageInput.value) || 100;
            
            if (capital <= 0 || leverage <= 0) {
                contractsCountEl.textContent = '-';
                return;
            }
            
            // Получаем цену бессрочного фьючерса из глобальной переменной
            const perpetualMarkPrice = globalPerpetualMarkPrice;
            
            if (!perpetualMarkPrice || perpetualMarkPrice <= 0) {
                console.error('Цена бессрочного фьючерса не установлена!');
                contractsCountEl.textContent = 'Ошибка: нет цены';
                return;
            }
            
            console.log('Используемая цена для расчета:', {
                perpetualPrice: perpetualMarkPrice,
                fromGlobal: globalPerpetualMarkPrice
            });
            
            // Initial Margin Rate рассчитывается на основе плеча
            // Initial Margin Rate = 1 / Leverage
            const initialMarginRate = 1 / leverage;
            const contractSize = 1;
            
            // Рассчитываем количество контрактов
            // Капитал делится на 2 (для срочного и бессрочного) и на Initial Margin
            // Используем цену БЕССРОЧНОГО фьючерса для расчета
            const contractsPerSide = capital / 2 / (perpetualMarkPrice * contractSize * initialMarginRate);
            const contractsCount = Math.floor(contractsPerSide);
            
            // Отладочный вывод
            console.log('Расчет количества контрактов:', {
                capital: capital,
                leverage: leverage,
                perpetualPrice: perpetualMarkPrice,
                initialMarginRate: initialMarginRate,
                contractSize: contractSize,
                denominator: perpetualMarkPrice * contractSize * initialMarginRate,
                contractsPerSide: contractsPerSide,
                contractsCount: contractsCount
            });
            
            // Проверка на валидность результата
            if (isNaN(contractsCount) || contractsCount < 0) {
                console.error('Ошибка в расчете количества контрактов!', {
                    capital, leverage, perpetualPrice: perpetualMarkPrice, initialMarginRate, contractsPerSide
                });
                contractsCountEl.textContent = 'Ошибка';
                return;
            }
            
            contractsCountEl.textContent = contractsCount;
            
            // Обновляем таблицу фьючерсов, если она уже отображена
            // Пересчитываем чистую прибыль в USDT для всех строк без перезагрузки данных
            const futuresContainer = document.getElementById('futures-container');
            if (futuresContainer && futuresContainer.querySelector('table')) {
                // Обновляем только расчеты чистой прибыли в USDT, не перезагружая данные
                // Передаем рассчитанные значения, чтобы избежать повторного расчета
                updateNetProfitUSDT(contractsCount, perpetualMarkPrice);
            }
            
            // Убеждаемся, что WebSocket продолжает работать после обновления
            // Проверяем состояние WebSocket и переподключаемся при необходимости
            // Проверяем через setTimeout, чтобы переменные были объявлены
            setTimeout(() => {
                try {
                    if (typeof wsInstruments !== 'undefined' && wsInstruments && typeof WebSocket !== 'undefined') {
                        const OPEN_STATE = 1; // WebSocket.OPEN = 1
                        if (wsInstruments.readyState !== OPEN_STATE) {
                            console.log('WebSocket не подключен после обновления, переподключаемся...');
                            if (typeof connectInstrumentsWebSocket === 'function') {
                                connectInstrumentsWebSocket();
                            }
                        } else {
                            console.log('WebSocket продолжает работать после обновления');
                        }
                    }
                } catch (e) {
                    console.warn('Ошибка при проверке WebSocket:', e);
                }
            }, 100);
        }
        
        function updateNetProfitUSDT(contractsCount, perpetualMarkPrice) {
            // Если параметры не переданы или невалидны, не делаем расчет
            if (!contractsCount || contractsCount <= 0 || !perpetualMarkPrice || perpetualMarkPrice <= 0) {
                console.warn('Недостаточно данных для расчета чистой прибыли в USDT:', {
                    contractsCount: contractsCount,
                    perpetualMarkPrice: perpetualMarkPrice
                });
                return;
            }
            
            console.log('Обновление чистой прибыли в USDT', {
                contractsCount: contractsCount,
                perpetualMarkPrice: perpetualMarkPrice
            });
            
            // Обновляем только колонку с чистой прибылью в USDT для всех строк таблицы
            const futuresContainer = document.getElementById('futures-container');
            if (!futuresContainer) {
                console.warn('Контейнер фьючерсов не найден');
                return;
            }
            
            const table = futuresContainer.querySelector('table');
            if (!table) {
                console.warn('Таблица фьючерсов не найдена');
                return;
            }
            
            const rows = table.querySelectorAll('tbody tr');
            if (rows.length === 0) {
                console.warn('Строки в таблице фьючерсов не найдены');
                return;
            }
            
            console.log('Найдено строк в таблице:', rows.length);
            
            // Обновляем каждую строку таблицы
            rows.forEach(row => {
                // Находим ячейку с чистой прибылью в процентах (колонка "Чистая прибыль (на базе FR за кол-во дней до экспирации)")
                // Индексы колонок: 0-символ, 1-дни, 2-Mark Price, 3-Справедливая (скрыта), 4-Last (скрыта), 
                // 5-Спред %, 6-Справедливый спред %, 7-FR за кол-во дней, 8-FR стандартный, 
                // 9-Чистая прибыль (на базе FR) <- это нужно, 10-Чистая прибыль (стандартный FR), 11-USDT, 12-Доходность на капитал
                const netProfitPercentCell = row.querySelectorAll('td')[9]; // Индекс колонки "Чистая прибыль (на базе FR за кол-во дней до экспирации)"
                if (!netProfitPercentCell) return;
                
                // Получаем значение чистой прибыли в процентах из текста ячейки
                // Важно сохранить знак минус, если он есть
                // Используем и textContent и innerHTML для надежности
                const cellText = netProfitPercentCell.textContent.trim();
                const cellHTML = netProfitPercentCell.innerHTML.trim();
                
                // Проверяем, есть ли знак минус в исходном тексте (в textContent или innerHTML)
                const hasMinus = cellText.includes('-') || cellHTML.includes('-');
                
                // Извлекаем число (может быть с минусом)
                // Ищем паттерн: минус (опционально), затем цифры и точка
                const numberMatch = cellText.match(/-?\d+\.?\d*/);
                let netProfitPercent = 0;
                
                if (numberMatch) {
                    netProfitPercent = parseFloat(numberMatch[0]);
                } else {
                    // Fallback: удаляем все кроме цифр и точки, затем добавляем минус если нужно
                    let cleanText = cellText.replace(/[^0-9.-]/g, '');
                    netProfitPercent = parseFloat(cleanText) || 0;
                    if (hasMinus && netProfitPercent > 0) {
                        netProfitPercent = -netProfitPercent;
                    }
                }
                
                // Дополнительная проверка: если в тексте был минус, но число положительное, делаем отрицательным
                if (hasMinus && netProfitPercent > 0) {
                    netProfitPercent = -netProfitPercent;
                }
                
                if (isNaN(netProfitPercent)) {
                    console.warn('Не удалось распарсить процент чистой прибыли:', cellText);
                    return;
                }
                
                console.log('Парсинг процента:', {
                    cellText: cellText,
                    hasMinus: hasMinus,
                    parsedPercent: netProfitPercent
                });
                
                // Размер позиции по бессрочному фьючерсу (FR начисляется только на позицию бессрочного)
                const contractSize = 1; // Размер контракта для USDT-маржинальных контрактов
                const perpetualPositionSize = contractsCount * perpetualMarkPrice * contractSize;
                
                // Чистая прибыль в USDT = Процент чистой прибыли × Размер позиции по бессрочному фьючерсу
                // Важно: если процент отрицательный, результат тоже должен быть отрицательным
                const netProfitUSDT = perpetualPositionSize * netProfitPercent / 100;
                
                // Форматируем с учетом знака
                let netProfitUSDTDisplay;
                if (netProfitUSDT > 0) {
                    netProfitUSDTDisplay = `$${netProfitUSDT.toFixed(2)}`;
                } else if (netProfitUSDT < 0) {
                    netProfitUSDTDisplay = `-$${Math.abs(netProfitUSDT).toFixed(2)}`;
                } else {
                    netProfitUSDTDisplay = '$0.00';
                }
                
                // Обновляем ячейку с чистой прибылью в USDT (12-я колонка, индекс 11)
                const netProfitUSDTCell = row.querySelectorAll('td')[11];
                if (netProfitUSDTCell) {
                    // Цвет зависит от знака чистой прибыли
                    const color = netProfitUSDT > 0 ? '#10b981' : netProfitUSDT < 0 ? '#ef4444' : '#6b7280';
                    netProfitUSDTCell.innerHTML = `<span style="color: ${color}; font-weight: 500;">${netProfitUSDTDisplay}</span>`;
                }
                
                // Обновляем ячейку с доходностью на капитал (13-я колонка, индекс 12)
                // Получаем количество дней до экспирации из второй колонки (индекс 1)
                const daysUntilExpCell = row.querySelectorAll('td')[1];
                let daysUntilExpValue = null;
                if (daysUntilExpCell) {
                    const daysText = daysUntilExpCell.textContent.trim();
                    const daysMatch = daysText.match(/^([\d.]+)/);
                    if (daysMatch) {
                        daysUntilExpValue = parseFloat(daysMatch[1]);
                    }
                }
                
                // Получаем плечо из поля ввода
                const leverageInput = document.getElementById('leverage-input');
                const leverage = leverageInput ? parseFloat(leverageInput.value) || 20 : 20;
                
                // Рассчитываем доходность на капитал в % годовых
                // Новая формула: (("Чистая прибыль в USDT" / "капитал" * 100) / "дни до экспирации") * 365
                const returnOnCapitalCell = row.querySelectorAll('td')[12];
                
                // Получаем капитал из поля ввода
                const capitalInput = document.getElementById('capital-input');
                const capital = capitalInput ? parseFloat(capitalInput.value) || 50000 : 50000;
                
                if (returnOnCapitalCell && !isNaN(netProfitUSDT) && netProfitUSDT !== null && !isNaN(capital) && capital > 0 && daysUntilExpValue !== null && daysUntilExpValue > 0) {
                    // Расчет: (чистая прибыль в USDT / капитал * 100) / дни до экспирации * 365
                    const returnOnCapital = (netProfitUSDT / capital * 100) / daysUntilExpValue * 365;
                    
                    console.log('Расчет доходности на капитал:', {
                        netProfitUSDT: netProfitUSDT,
                        capital: capital,
                        daysUntilExpValue: daysUntilExpValue,
                        returnOnCapital: returnOnCapital
                    });
                    
                    // Форматируем с учетом знака
                    let returnOnCapitalDisplay;
                    if (returnOnCapital > 0) {
                        returnOnCapitalDisplay = returnOnCapital.toFixed(2) + '%';
                    } else if (returnOnCapital < 0) {
                        returnOnCapitalDisplay = returnOnCapital.toFixed(2) + '%'; // toFixed сохраняет знак минус
                    } else {
                        returnOnCapitalDisplay = '0.00%';
                    }
                    
                    const returnOnCapitalColor = returnOnCapital > 0 ? '#10b981' : returnOnCapital < 0 ? '#ef4444' : '#6b7280';
                    returnOnCapitalCell.innerHTML = `<span style="color: ${returnOnCapitalColor}; font-weight: 500;">${returnOnCapitalDisplay}</span>`;
                } else if (returnOnCapitalCell) {
                    console.warn('Недостаточно данных для расчета доходности:', {
                        netProfitUSDT: netProfitUSDT,
                        capital: capital,
                        daysUntilExpValue: daysUntilExpValue
                    });
                    returnOnCapitalCell.innerHTML = '<span style="color: #6b7280; font-weight: 500;">N/A</span>';
                }
            });
        }
        
        function displayPerpetual(perpetual) {
            const container = document.getElementById('perpetual-container');
            
            if (!perpetual) {
                container.innerHTML = '<div class="error">Данные по бессрочному фьючерсу не получены</div>';
                return;
            }
            
            const currentFR = perpetual.current_funding_rate !== undefined 
                ? perpetual.current_funding_rate.toFixed(3) + '%'
                : 'N/A';
            
            const totalFR3months = perpetual.total_funding_rate_3months !== undefined 
                ? perpetual.total_funding_rate_3months.toFixed(3) + '%'
                : 'N/A';
            
            const totalFR6months = perpetual.total_funding_rate_6months !== undefined 
                ? perpetual.total_funding_rate_6months.toFixed(3) + '%'
                : 'N/A';
            
            const totalFR365days = perpetual.total_funding_rate_365days !== undefined 
                ? perpetual.total_funding_rate_365days.toFixed(3) + '%'
                : 'N/A';
            
            const spotPrice = perpetual.spot_price !== undefined && perpetual.spot_price !== null
                ? formatPrice(perpetual.spot_price)
                : 'N/A';
            
            container.innerHTML = `
                <table class="instruments-table">
                    <thead>
                        <tr>
                            <th>Символ</th>
                            <th>Spot Price</th>
                            <th>Mark Price</th>
                            <th>Last Price</th>
                            <th title="Funding rate за последний завершившийся 8 часовой интервал">FR 8ч</th>
                            <th title="Суммарный Funding Rate, который был выплачен за последние 3 месяца от текущего времени">FR 3 мес</th>
                            <th title="Суммарный Funding Rate, который был выплачен за последние 6 месяцев от текущего времени">FR 6 мес</th>
                            <th title="Суммарный Funding Rate, который был выплачен за последний год">FR 1 год</th>
                            <th>Время обновления</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="instrument-symbol">${perpetual.symbol}</td>
                            <td class="price" style="color: #10b981; font-weight: 500;">${spotPrice}</td>
                            <td class="price mark">${formatPrice(perpetual.mark_price)}</td>
                            <td class="price last">${formatPrice(perpetual.last_price)}</td>
                            <td class="price" style="color: #3b82f6;">${currentFR}</td>
                            <td class="price" style="color: #8b5cf6;">${totalFR3months}</td>
                            <td class="price" style="color: #f59e0b;">${totalFR6months}</td>
                            <td class="price" style="color: #ef4444;">${totalFR365days}</td>
                            <td class="timestamp">${formatTimestamp(perpetual.timestamp)}</td>
                        </tr>
                    </tbody>
                </table>
            `;
            
            // Сохраняем цену бессрочного фьючерса в глобальную переменную
            if (perpetual.mark_price !== undefined && perpetual.mark_price !== null) {
                globalPerpetualMarkPrice = perpetual.mark_price;
                console.log('Установлена цена бессрочного фьючерса:', globalPerpetualMarkPrice);
            }
            
            // Обновляем количество контрактов после отображения данных бессрочного фьючерса
            updateContractsCount();
        }
        
        function displayFutures(futures) {
            const container = document.getElementById('futures-container');
            
            if (!futures || futures.length === 0) {
                container.innerHTML = '<div class="error">Данные по срочным фьючерсам не получены</div>';
                return;
            }
            
            let html = `
                <table class="instruments-table">
                    <thead>
                        <tr>
                            <th>Символ</th>
                            <th>Дней до экспирации</th>
                            <th>Mark Price</th>
                            <th style="display: none;">Справедливая цена</th>
                            <th style="display: none;">Last Price</th>
                            <th title="Разница между ценой срочного и бессрочного фьючерса в %">Спред %</th>
                            <th title="Спред между бессрочным фьючерсом и расчетной справедливой ценой срочного фьючерса">Справедливый спред %</th>
                            <th title="Суммарный Funding Rate, который был выплачен за количество дней, эквивалентное количеству дней до экспирации срочного фьючерса">FR за кол-во дней до экспирации</th>
                            <th title="Суммарный Funding Rate, который был БЫ выплачен за количество дней, эквивалентное количеству дней до экспирации срочного фьючерса, если бы ставка была базовой 0,01% за каждые 8 часов">FR (стандартный) за кол-во дней до экспирации</th>
                            <th title="Чистая прибыль, которую инвестор заработает, если войдет в сделку, и Funding Rate будет сохраняться таким же, как он был за последний интервал, эквивалентный кол-ву дней до экспирации">Чистая прибыль (на базе FR за кол-во дней до экспирации)</th>
                            <th title="Чистая прибыль в % от размера позиции по бессрочному фьючерсу, которую инвестор получит, в случае если Funding Rate будет сохраняться на стандартном уровне в 0.01% каждые 8 часов">Чистая прибыль (стандартный FR)</th>
                            <th title="Чистая прибыль, рассчитанная в USDT, рассчитывается на основе % чистой прибыли, рассчитанной на исторических значения Funding Rate за период, эквивалентный сроку до экспирации">Чистая прибыль (USDT)</th>
                            <th title="Доходность на вложенный капитал, который указан в поле &quot;Капитал&quot;, выраженная в % годовых с учетом срока экспирации">Доходность на капитал (% годовых)</th>
                            <th>Время обновления</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            futures.forEach(future => {
                const daysUntilExp = future.days_until_expiration !== undefined && future.days_until_expiration !== null
                    ? future.days_until_expiration.toFixed(1) + ' дней'
                    : 'N/A';
                
                // Справедливая цена фьючерса
                const fairFuturesPrice = future.fair_futures_price !== undefined && future.fair_futures_price !== null
                    ? formatPrice(future.fair_futures_price)
                    : 'N/A';
                
                const spreadPercent = future.spread_percent !== undefined && future.spread_percent !== null
                    ? future.spread_percent.toFixed(3) + '%'
                    : 'N/A';
                
                // Справедливый спред % = (fair_price - mark_price) / mark_price * 100
                const fairSpreadPercent = future.fair_spread_percent !== undefined && future.fair_spread_percent !== null
                    ? future.fair_spread_percent.toFixed(3) + '%'
                    : 'N/A';
                
                // Суммарный FR за кол-во дней до экспирации (рассчитан на основе суммарного FR за количество дней, равное дням до экспирации)
                const frUntilExpCurrent = future.funding_rate_until_expiration !== undefined && future.funding_rate_until_expiration !== null
                    ? future.funding_rate_until_expiration.toFixed(3) + '%'
                    : 'N/A';
                
                // Стандартный Funding Rate до экспирации (0.01% за 8 часов)
                const standardFRUntilExp = future.standard_funding_rate_until_expiration !== undefined && future.standard_funding_rate_until_expiration !== null
                    ? future.standard_funding_rate_until_expiration.toFixed(3) + '%'
                    : 'N/A';
                
                // Чистая прибыль (суммарный FR за кол-во дней до экспирации): FR до экспирации - Спред % - Комиссии
                const netProfitCurrentFR = future.net_profit_current_fr !== undefined && future.net_profit_current_fr !== null
                    ? future.net_profit_current_fr.toFixed(3) + '%'
                    : 'N/A';
                
                // Чистая прибыль (стандартный FR): суммарный стандартный FR до экспирации - Спред % - Комиссии
                const netProfitStandardFR = future.net_profit_standard_fr !== undefined && future.net_profit_standard_fr !== null
                    ? future.net_profit_standard_fr.toFixed(3) + '%'
                    : 'N/A';
                
                // Цвет для спреда
                const spreadColor = future.spread_percent !== undefined && future.spread_percent !== null
                    ? (future.spread_percent < 0 ? '#ef4444' : '#667eea')
                    : '#6b7280';
                
                // Цвет для справедливого спреда
                const fairSpreadColor = future.fair_spread_percent !== undefined && future.fair_spread_percent !== null
                    ? (future.fair_spread_percent < 0 ? '#ef4444' : '#10b981')
                    : '#6b7280';
                
                // Цвет для чистой прибыли (средний FR за месяц)
                const netProfitCurrentFRValue = future.net_profit_current_fr !== undefined && future.net_profit_current_fr !== null
                    ? future.net_profit_current_fr
                    : null;
                const netProfitCurrentFRColor = netProfitCurrentFRValue !== null
                    ? (netProfitCurrentFRValue > 0 ? '#10b981' : '#ef4444')
                    : '#6b7280';
                
                // Цвет для чистой прибыли (стандартный FR)
                const netProfitStandardFRValue = future.net_profit_standard_fr !== undefined && future.net_profit_standard_fr !== null
                    ? future.net_profit_standard_fr
                    : null;
                const netProfitStandardFRColor = netProfitStandardFRValue !== null
                    ? (netProfitStandardFRValue > 0 ? '#10b981' : '#ef4444')
                    : '#6b7280';
                
                // Проверка условия для выделения строки жирным шрифтом
                // Если "Спред %" < "FR за кол-во дней до экспирации" И "Спред %" < "Справедливый спред %" И "Чистая прибыль (на базе FR за кол-во дней до экспирации)" > 0
                const spreadPercentValue = future.spread_percent !== undefined && future.spread_percent !== null ? future.spread_percent : null;
                const frUntilExpValue = future.funding_rate_until_expiration !== undefined && future.funding_rate_until_expiration !== null ? future.funding_rate_until_expiration : null;
                const fairSpreadPercentValue = future.fair_spread_percent !== undefined && future.fair_spread_percent !== null ? future.fair_spread_percent : null;
                // netProfitCurrentFRValue уже определен выше
                
                const shouldHighlight = spreadPercentValue !== null && 
                                       frUntilExpValue !== null && 
                                       fairSpreadPercentValue !== null &&
                                       netProfitCurrentFRValue !== null &&
                                       spreadPercentValue < frUntilExpValue &&
                                       spreadPercentValue < fairSpreadPercentValue &&
                                       netProfitCurrentFRValue > 0;
                
                // Отладочный вывод (можно убрать после проверки)
                if (shouldHighlight) {
                    console.log(`Выделение строки ${future.symbol}:`, {
                        spread: spreadPercentValue,
                        fr: frUntilExpValue,
                        fairSpread: fairSpreadPercentValue,
                        netProfit: netProfitCurrentFRValue
                    });
                }
                
                // Применяем жирный шрифт ко всей строке
                const rowStyle = shouldHighlight ? 'font-weight: bold !important;' : '';
                const rowClass = shouldHighlight ? 'highlighted-row' : '';
                
                // Расчет чистой прибыли в USDT
                // Получаем капитал и плечо из полей ввода
                const capitalInput = document.getElementById('capital-input');
                const leverageInput = document.getElementById('leverage-input');
                const capital = capitalInput ? parseFloat(capitalInput.value) || 50000 : 50000;
                const leverage = leverageInput ? parseFloat(leverageInput.value) || 20 : 20;
                
                // Получаем цену бессрочного фьючерса
                const perpetualMarkPrice = globalPerpetualMarkPrice;
                
                // Переменные для чистой прибыли в USDT
                let netProfitUSDTDisplay;
                let netProfitUSDTColor;
                let netProfitUSDT = 0; // Объявляем вне блока для использования в расчете доходности
                
                // Если цена бессрочного фьючерса не установлена, не рассчитываем чистую прибыль в USDT
                if (!perpetualMarkPrice || perpetualMarkPrice <= 0) {
                    netProfitUSDTDisplay = 'N/A';
                    netProfitUSDTColor = '#6b7280';
                    netProfitUSDT = 0;
                } else {
                    // Initial Margin Rate рассчитывается на основе плеча
                    // Initial Margin Rate = 1 / Leverage
                    const initialMarginRate = 1 / leverage;
                    const contractSize = 1; // Размер контракта для USDT-маржинальных контрактов
                    
                    // Рассчитываем количество контрактов
                    // Капитал делится на 2 (для срочного и бессрочного) и на Initial Margin
                    // Используем цену БЕССРОЧНОГО фьючерса для расчета
                    const contractsPerSide = capital / 2 / (perpetualMarkPrice * contractSize * initialMarginRate);
                    const contractsCount = Math.floor(contractsPerSide); // Округляем вниз
                    
                    // Размер позиции по бессрочному фьючерсу (FR начисляется только на позицию бессрочного)
                    const perpetualPositionSize = contractsCount * perpetualMarkPrice * contractSize;
                    
                    // Чистая прибыль в USDT = Процент чистой прибыли × Размер позиции по бессрочному фьючерсу
                    // Важно: если процент отрицательный, результат тоже должен быть отрицательным
                    netProfitUSDT = netProfitCurrentFRValue !== null && perpetualMarkPrice > 0
                        ? (perpetualPositionSize * netProfitCurrentFRValue / 100)
                        : 0;
                    
                    // Форматируем с учетом знака
                    if (netProfitUSDT > 0) {
                        netProfitUSDTDisplay = `$${netProfitUSDT.toFixed(2)}`;
                    } else if (netProfitUSDT < 0) {
                        netProfitUSDTDisplay = `-$${Math.abs(netProfitUSDT).toFixed(2)}`;
                    } else {
                        netProfitUSDTDisplay = '$0.00';
                    }
                    
                    // Цвет зависит от знака чистой прибыли в USDT
                    netProfitUSDTColor = netProfitUSDT > 0 ? '#10b981' : netProfitUSDT < 0 ? '#ef4444' : '#6b7280';
                }
                
                // Расчет доходности на капитал в % годовых
                // Новая формула: (("Чистая прибыль в USDT" / "капитал" * 100) / "дни до экспирации") * 365
                let returnOnCapitalDisplay;
                let returnOnCapitalColor;
                const daysUntilExpValue = future.days_until_expiration !== undefined && future.days_until_expiration !== null 
                    ? future.days_until_expiration 
                    : null;
                
                // Используем чистую прибыль в USDT (уже рассчитана выше)
                // Проверяем, что все значения валидны
                if (!isNaN(netProfitUSDT) && netProfitUSDT !== 0 && !isNaN(capital) && capital > 0 && daysUntilExpValue !== null && daysUntilExpValue > 0) {
                    // Расчет: (чистая прибыль в USDT / капитал * 100) / дни до экспирации * 365
                    const returnOnCapital = (netProfitUSDT / capital * 100) / daysUntilExpValue * 365;
                    
                    console.log('Расчет доходности в displayFutures:', {
                        netProfitUSDT: netProfitUSDT,
                        capital: capital,
                        daysUntilExpValue: daysUntilExpValue,
                        returnOnCapital: returnOnCapital
                    });
                    
                    // Форматируем с учетом знака
                    if (returnOnCapital > 0) {
                        returnOnCapitalDisplay = returnOnCapital.toFixed(2) + '%';
                    } else if (returnOnCapital < 0) {
                        returnOnCapitalDisplay = returnOnCapital.toFixed(2) + '%'; // toFixed сохраняет знак минус
                    } else {
                        returnOnCapitalDisplay = '0.00%';
                    }
                    
                    returnOnCapitalColor = returnOnCapital > 0 ? '#10b981' : returnOnCapital < 0 ? '#ef4444' : '#6b7280';
                } else {
                    returnOnCapitalDisplay = 'N/A';
                    returnOnCapitalColor = '#6b7280';
                }
                
                html += `
                    <tr class="${rowClass}" style="${rowStyle}">
                        <td class="instrument-symbol">${future.symbol}</td>
                        <td class="timestamp">${daysUntilExp}</td>
                        <td class="price mark">${formatPrice(future.mark_price)}</td>
                        <td class="price" style="color: #8b5cf6; font-weight: 500; display: none;">${fairFuturesPrice}</td>
                        <td class="price last" style="display: none;">${formatPrice(future.last_price)}</td>
                        <td class="price" style="color: ${spreadColor};">${spreadPercent}</td>
                        <td class="price" style="color: ${fairSpreadColor};">${fairSpreadPercent}</td>
                        <td class="price" style="color: #667eea;">${frUntilExpCurrent}</td>
                        <td class="price" style="color: #10b981;">${standardFRUntilExp}</td>
                        <td class="price" style="color: ${netProfitCurrentFRColor}; font-weight: 500;">${netProfitCurrentFR}</td>
                        <td class="price" style="color: ${netProfitStandardFRColor}; font-weight: 500;">${netProfitStandardFR}</td>
                        <td class="price" style="color: ${netProfitUSDTColor}; font-weight: 500;">${netProfitUSDTDisplay}</td>
                        <td class="price" style="color: ${returnOnCapitalColor}; font-weight: 500;">${returnOnCapitalDisplay}</td>
                        <td class="timestamp">${formatTimestamp(future.timestamp)}</td>
                    </tr>
                `;
            });
            
            html += `
                    </tbody>
                </table>
            `;
            
            container.innerHTML = html;
        }
        
        function displayFees() {
            const container = document.getElementById('fees-container');
            
            // Комиссии ByBit VIP2 для maker сделок
            const VIP2_MAKER_FEE = 0.0290; // 0.0290% за сделку
            const trades = [
                { name: 'Покупка срочного фьючерса (long)', instrument: 'Срочный фьючерс', fee: VIP2_MAKER_FEE },
                { name: 'Продажа бессрочного фьючерса (short)', instrument: 'Бессрочный фьючерс', fee: VIP2_MAKER_FEE },
                { name: 'Продажа срочного фьючерса (закрытие long)', instrument: 'Срочный фьючерс', fee: VIP2_MAKER_FEE },
                { name: 'Покупка бессрочного фьючерса (закрытие short)', instrument: 'Бессрочный фьючерс', fee: VIP2_MAKER_FEE }
            ];
            
            const totalFee = VIP2_MAKER_FEE * 4;
            
            let html = `
                <table class="fees-table">
                    <thead>
                        <tr>
                            <th>Сделка</th>
                            <th>Инструмент</th>
                            <th>Тип ордера</th>
                            <th>Комиссия (maker)</th>
                            <th>Статус VIP2</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            trades.forEach(trade => {
                html += `
                    <tr>
                        <td>${trade.name}</td>
                        <td>${trade.instrument}</td>
                        <td>Maker (лимитный)</td>
                        <td class="fee-value">${trade.fee.toFixed(3)}%</td>
                        <td>VIP2</td>
                    </tr>
                `;
            });
            
            html += `
                        <tr class="fee-total">
                            <td colspan="2"><strong>ИТОГО комиссий:</strong></td>
                            <td></td>
                            <td class="fee-value" style="font-weight: 500;"><strong>${totalFee.toFixed(3)}%</strong></td>
                            <td>4 сделки × ${VIP2_MAKER_FEE.toFixed(3)}%</td>
                        </tr>
                    </tbody>
                </table>
                <div style="margin-top: 15px; padding: 10px; background: #f3f4f6; border-radius: 8px; font-size: 0.85em; color: #6b7280;">
                    <strong>Примечание:</strong> Комиссии вычитаются из чистой прибыли в колонках "Чистая прибыль (на базе FR за кол-во дней до экспирации)" и "Чистая прибыль (стандартный FR)". FR рассчитывается за количество дней, равное количеству дней до экспирации конкретного фьючерса.
                </div>
            `;
            
            container.innerHTML = html;
        }
        
        async function loadInstruments() {
            try {
                updateStatus(false);
                
                // Используем API для конкретного инструмента
                const instrumentCode = '{instrument_code}';
                console.log('Загрузка данных для инструмента:', instrumentCode);
                const response = await fetch('/api/instruments/' + instrumentCode);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                console.log('Данные получены:', data);
                
                if (data.error) {
                    console.error('Ошибка в данных:', data.error);
                    const perpetualContainer = document.getElementById('perpetual-container');
                    const futuresContainer = document.getElementById('futures-container');
                    if (perpetualContainer) {
                        perpetualContainer.innerHTML = `<div class="error">Ошибка: ${data.error}</div>`;
                    }
                    if (futuresContainer) {
                        futuresContainer.innerHTML = `<div class="error">Ошибка: ${data.error}</div>`;
                    }
                    return;
                }
                
                updateStatus(true);
                console.log('Отображение данных...');
                
                // Отображаем данные
                if (data.perpetual) {
                    displayPerpetual(data.perpetual);
                } else {
                    console.warn('Данные perpetual не найдены');
                }
                // Сначала обновляем perpetual, чтобы установить globalPerpetualMarkPrice
                if (data.perpetual) {
                    displayPerpetual(data.perpetual);
                }
                // Затем обновляем futures, чтобы использовать установленную цену
                if (data.futures && Array.isArray(data.futures)) {
                    setTimeout(() => {
                        displayFutures(data.futures);
                    }, 10);
                } else {
                    console.warn('Данные futures не найдены или не массив');
                }
                displayFees();
                
                // Обновляем безрисковую ставку
                if (data.risk_free_rate_annual !== undefined) {
                    document.getElementById('risk-free-rate').textContent = 
                        data.risk_free_rate_annual.toFixed(3);
                }
                
                // Обновляем время последнего обновления
                const now = new Date();
                document.getElementById('last-update').textContent = 
                    now.toLocaleString('ru-RU');
                
                // Обновляем количество контрактов после загрузки данных
                updateContractsCount();
                
            } catch (error) {
                console.error('Ошибка при загрузке данных:', error);
                updateStatus(false);
                const errorMsg = error.message || String(error);
                document.getElementById('perpetual-container').innerHTML = 
                    `<div class="error">Ошибка при загрузке данных: ${errorMsg}</div>`;
                document.getElementById('futures-container').innerHTML = 
                    `<div class="error">Ошибка при загрузке данных: ${errorMsg}</div>`;
            }
        }
        
        // Загрузка порога доходности из конфигурации
        function loadReturnThreshold() {
            fetch('/api/config')
                .then(response => response.json())
                .then(data => {
                    const thresholdInput = document.getElementById('return-threshold-input');
                    if (thresholdInput && data.return_on_capital_threshold !== undefined) {
                        thresholdInput.value = data.return_on_capital_threshold;
                    }
                })
                .catch(error => {
                    console.error('Ошибка при загрузке порога доходности:', error);
                });
        }
        
        // Ждем полной загрузки DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOM загружен, запускаем загрузку данных');
                // Загружаем порог доходности
                loadReturnThreshold();
                // Отображаем таблицу комиссий
                displayFees();
                // Загружаем начальные данные через HTTP
                loadInstruments();
            });
        } else {
            console.log('DOM уже загружен, запускаем загрузку данных');
            // Загружаем порог доходности
            loadReturnThreshold();
            // Отображаем таблицу комиссий сразу
            displayFees();
            // Загружаем начальные данные через HTTP
            loadInstruments();
        }
        
        // WebSocket для real-time обновлений
        let wsInstruments = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 50;
        
        function connectInstrumentsWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/instruments`;
            
            wsInstruments = new WebSocket(wsUrl);
            
            wsInstruments.onopen = () => {
                console.log('WebSocket подключен для инструментов');
                updateStatus(true);
                reconnectAttempts = 0;
            };
            
            wsInstruments.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    console.log('Получено WebSocket сообщение:', message.type);
                    
                    if (message.type === 'ping') {
                        // Отвечаем на ping
                        wsInstruments.send('pong');
                        return;
                    }
                    
                    if (message.type === 'instruments' && message.data) {
                        console.log('Обновление данных инструментов через WebSocket:', {
                            perpetual: message.data.perpetual?.symbol,
                            futures_count: message.data.futures?.length
                        });
                        
                        // Обновляем данные на странице
                        updateStatus(true);
                        
                        // Сначала обновляем perpetual, чтобы установить globalPerpetualMarkPrice
                        if (message.data.perpetual) {
                            displayPerpetual(message.data.perpetual);
                        }
                        // Затем обновляем futures, чтобы использовать установленную цену
                        // Используем setTimeout, чтобы globalPerpetualMarkPrice успела установиться
                        if (message.data.futures) {
                            setTimeout(() => {
                                displayFutures(message.data.futures);
                            }, 10);
                        }
                        
                        // Обновляем безрисковую ставку
                        if (message.data.risk_free_rate_annual !== undefined) {
                            document.getElementById('risk-free-rate').textContent = 
                                message.data.risk_free_rate_annual.toFixed(3);
                        }
                        
                        // Отображаем таблицу комиссий
                        displayFees();
                        
                        // Обновляем время последнего обновления
                        const now = new Date();
                        document.getElementById('last-update').textContent = 
                            now.toLocaleString('ru-RU');
                    }
                } catch (error) {
                    console.error('Ошибка при обработке сообщения WebSocket:', error);
                    console.error('Данные:', event.data);
                }
            };
            
            wsInstruments.onerror = (error) => {
                console.error('WebSocket ошибка:', error);
                updateStatus(false);
            };
            
            wsInstruments.onclose = () => {
                console.log('WebSocket отключен');
                updateStatus(false);
                
                // Переподключаемся с экспоненциальной задержкой
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 30000); // Макс 30 сек
                    console.log(`Попытка переподключения ${reconnectAttempts} через ${delay}мс...`);
                    setTimeout(connectInstrumentsWebSocket, delay);
                } else {
                    console.error('Достигнуто максимальное количество попыток переподключения');
                    // Fallback к обычным HTTP запросам
                    updateInterval = setInterval(loadInstruments, 5000);
                }
            };
        }
        
        // Подключаемся к WebSocket для real-time обновлений
        connectInstrumentsWebSocket();
        
        // Останавливаем все соединения при уходе со страницы
        window.addEventListener('beforeunload', () => {
            if (updateInterval) {
                clearInterval(updateInterval);
            }
            if (wsInstruments) {
                wsInstruments.close();
            }
        });
    </script>
</body>
</html>"""
    
    # Заменяем плейсхолдеры в шаблоне (используем replace вместо format, чтобы избежать проблем с фигурными скобками в CSS/JS)
    return template.replace("{instrument_code}", instrument_code).replace("{perpetual_symbol}", perpetual_symbol).replace("{instrument_name}", instrument_name)

