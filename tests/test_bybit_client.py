"""
Тесты для модуля ByBitClient
"""
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from src.bybit_client import ByBitClient

# Настройка логирования для тестов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_bybit_client_initialization():
    """Тест инициализации клиента без API ключей (для публичных данных)"""
    logger.info("Тест 1: Инициализация клиента без API ключей")
    
    try:
        client = ByBitClient(api_key="", api_secret="", testnet=False)
        logger.info("✓ Клиент успешно инициализирован без API ключей")
        assert client is not None
        assert client.testnet == False
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при инициализации клиента: {e}")
        return False


def test_get_perpetual_ticker():
    """Тест получения тикера бессрочного фьючерса"""
    logger.info("Тест 2: Получение тикера бессрочного фьючерса ETHUSDT")
    
    try:
        client = ByBitClient(testnet=False)
        ticker = client.get_perpetual_ticker("ETHUSDT")
        
        if ticker is None:
            logger.warning("⚠ Тикер не получен (возможно, проблемы с сетью или API)")
            return False
        
        logger.info(f"✓ Тикер получен: {ticker}")
        assert "symbol" in ticker
        assert "mark_price" in ticker
        assert "last_price" in ticker
        assert ticker["symbol"] == "ETHUSDT"
        assert ticker["mark_price"] > 0
        logger.info(f"  Символ: {ticker['symbol']}")
        logger.info(f"  Mark Price: ${ticker['mark_price']:.2f}")
        logger.info(f"  Last Price: ${ticker['last_price']:.2f}")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при получении тикера: {e}")
        return False


def test_get_futures_ticker():
    """Тест получения тикера срочного фьючерса"""
    logger.info("Тест 3: Получение тикера срочного фьючерса")
    
    try:
        client = ByBitClient(testnet=False)
        # Используем правильный формат символов ByBit: ETHUSDT-DDMMMYY
        symbol = "ETHUSDT-26DEC25"  # Формат: ETHUSDT-деньмесяцгод
        ticker = client.get_futures_ticker(symbol)
        
        if ticker is None:
            logger.warning(f"⚠ Тикер для {symbol} не получен")
            return False
        
        # Проверяем структуру тикера
        logger.info(f"✓ Тикер получен для {symbol}: {ticker}")
        assert "symbol" in ticker
        assert "mark_price" in ticker
        assert "last_price" in ticker
        assert ticker["mark_price"] > 0
        logger.info(f"  Символ: {ticker['symbol']}")
        logger.info(f"  Mark Price: ${ticker['mark_price']:.2f}")
        logger.info(f"  Last Price: ${ticker['last_price']:.2f}")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при получении тикера срочного фьючерса: {e}")
        return False


def test_get_available_futures():
    """Тест получения списка доступных срочных фьючерсов"""
    logger.info("Тест 7: Получение списка доступных срочных фьючерсов")
    
    try:
        client = ByBitClient(testnet=False)
        futures = client.get_available_futures("ETHUSDT")
        
        if not futures:
            logger.warning("⚠ Список срочных фьючерсов пуст")
            return False
        
        logger.info(f"✓ Найдено {len(futures)} срочных фьючерсов:")
        for future in futures[:5]:  # Показываем первые 5
            symbol = future.get("symbol", "")
            delivery_time = future.get("delivery_time", 0)
            from datetime import datetime
            delivery_date = datetime.fromtimestamp(delivery_time / 1000).strftime("%Y-%m-%d") if delivery_time else "N/A"
            logger.info(f"  - {symbol} (delivery: {delivery_date})")
        
        if len(futures) > 5:
            logger.info(f"  ... и еще {len(futures) - 5} фьючерсов")
        
        assert len(futures) > 0
        assert all("symbol" in f for f in futures)
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при получении списка срочных фьючерсов: {e}")
        return False


def test_get_current_funding_rate():
    """Тест получения текущего Funding Rate"""
    logger.info("Тест 4: Получение текущего Funding Rate для ETHUSDT")
    
    try:
        client = ByBitClient(testnet=False)
        funding = client.get_current_funding_rate("ETHUSDT")
        
        if funding is None:
            logger.warning("⚠ Funding Rate не получен (возможно, проблемы с сетью или API)")
            return False
        
        logger.info(f"✓ Funding Rate получен: {funding}")
        assert "symbol" in funding
        assert "funding_rate" in funding
        assert funding["symbol"] == "ETHUSDT"
        logger.info(f"  Символ: {funding['symbol']}")
        logger.info(f"  Funding Rate: {funding['funding_rate']:.6f} ({funding['funding_rate'] * 100:.4f}%)")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при получении Funding Rate: {e}")
        return False


def test_get_funding_rate_history():
    """Тест получения истории Funding Rate"""
    logger.info("Тест 5: Получение истории Funding Rate за 7 дней")
    
    try:
        client = ByBitClient(testnet=False)
        history = client.get_funding_rate_history("ETHUSDT", days=7)
        
        if not history:
            logger.warning("⚠ История Funding Rate не получена")
            return False
        
        logger.info(f"✓ Получено записей истории: {len(history)}")
        assert len(history) > 0
        
        # Проверяем структуру первой записи
        first_record = history[0]
        assert "symbol" in first_record
        assert "funding_rate" in first_record
        assert "timestamp" in first_record
        
        logger.info(f"  Первая запись: {first_record}")
        logger.info(f"  Последняя запись: {history[-1]}")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при получении истории Funding Rate: {e}")
        return False


def test_calculate_average_funding_rate():
    """Тест расчета среднего Funding Rate"""
    logger.info("Тест 6: Расчет среднего Funding Rate за 7 дней")
    
    try:
        client = ByBitClient(testnet=False)
        avg_rate = client.calculate_average_funding_rate("ETHUSDT", days=7)
        
        if avg_rate is None:
            logger.warning("⚠ Средний Funding Rate не рассчитан")
            return False
        
        logger.info(f"✓ Средний Funding Rate: {avg_rate:.6f} ({avg_rate * 100:.4f}%)")
        assert isinstance(avg_rate, float)
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка при расчете среднего Funding Rate: {e}")
        return False


def run_all_tests():
    """Запуск всех тестов"""
    logger.info("=" * 60)
    logger.info("Запуск тестов для модуля ByBitClient")
    logger.info("=" * 60)
    
    tests = [
        ("Инициализация клиента", test_bybit_client_initialization),
        ("Получение тикера бессрочного фьючерса", test_get_perpetual_ticker),
        ("Получение тикера срочного фьючерса", test_get_futures_ticker),
        ("Получение текущего Funding Rate", test_get_current_funding_rate),
        ("Получение истории Funding Rate", test_get_funding_rate_history),
        ("Расчет среднего Funding Rate", test_calculate_average_funding_rate),
        ("Получение списка доступных срочных фьючерсов", test_get_available_futures),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"✗ Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
        logger.info("")
    
    # Итоги
    logger.info("=" * 60)
    logger.info("Результаты тестов:")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ ПРОШЕЛ" if result else "✗ ПРОВАЛЕН"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    logger.info(f"Всего тестов: {len(results)}")
    logger.info(f"Пройдено: {passed}")
    logger.info(f"Провалено: {failed}")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

