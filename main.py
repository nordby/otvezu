# main.py - Исправленный главный файл для запуска всей системы экспедирования

import asyncio
import threading
import time
import os
import sys
import logging
from datetime import datetime
from telegram_bot import ExpeditionBot


# Импорт модулей системы
from database import DatabaseManager
from telegram_bot import ExpeditionBot
from web_app import app, create_templates

# Безопасный импорт Google Calendar
try:
    from google_calendar import CalendarIntegration, print_setup_instructions
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    print("⚠️ Google Calendar модуль недоступен")
    
    # Создаем заглушки
    class CalendarIntegration:
        def __init__(self, enabled=False):
            self.enabled = False
    
    def print_setup_instructions():
        print("📋 НАСТРОЙКА GOOGLE CALENDAR:")
        print("1. Установите зависимости: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        print("2. Создайте проект в Google Cloud Console")
        print("3. Включите Google Calendar API")
        print("4. Создайте OAuth 2.0 credentials")
        print("5. Скачайте credentials.json")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('expedition_system.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class ExpeditionSystem:
    """Главный класс системы экспедирования"""
    
    def __init__(self):
        self.db_manager = None
        self.telegram_bot = None
        self.calendar_integration = None
        self.web_app_process = None
        
        # Настройки из переменных окружения
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.web_host = os.getenv("WEB_HOST", "0.0.0.0")
        self.web_port = int(os.getenv("WEB_PORT", "8000"))
        self.google_calendar_enabled = os.getenv("GOOGLE_CALENDAR_ENABLED", "true").lower() == "true"
        
    def initialize_database(self):
        """Инициализация базы данных"""
        logger.info("🗄️ Инициализация базы данных...")
        try:
            self.db_manager = DatabaseManager()
            logger.info("✅ База данных инициализирована успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            return False
    
    def initialize_calendar(self):
        """Инициализация интеграции с Google Calendar"""
        logger.info("📅 Инициализация Google Calendar...")
        try:
            if GOOGLE_CALENDAR_AVAILABLE:
                self.calendar_integration = CalendarIntegration(enabled=self.google_calendar_enabled)
                if self.calendar_integration.enabled:
                    logger.info("✅ Google Calendar интеграция активна")
                else:
                    logger.warning("⚠️ Google Calendar интеграция отключена")
            else:
                logger.warning("⚠️ Google Calendar API недоступен")
                self.calendar_integration = CalendarIntegration(enabled=False)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Google Calendar: {e}")
            self.calendar_integration = CalendarIntegration(enabled=False)
            return False
    
    def initialize_telegram_bot(self):
        """Инициализация Telegram бота"""
        if not self.telegram_token or self.telegram_token == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ Не установлен токен Telegram бота!")
            logger.info("💡 Установите переменную окружения TELEGRAM_BOT_TOKEN")
            logger.info("💡 Получить токен можно у @BotFather в Telegram")
            return False
        
        logger.info("🤖 Инициализация Telegram бота...")
        try:
            self.telegram_bot = ExpeditionBot(self.telegram_token, self.db_manager)
            logger.info("✅ Telegram бот инициализирован успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram бота: {e}")
            return False
    
    def create_sample_data(self):
        """Создание демонстрационных данных"""
        logger.info("📝 Создание демонстрационных данных...")
        
        try:
            # Проверяем, есть ли уже данные
            users = self.db_manager.get_all_users()
            vehicles = self.db_manager.get_active_vehicles()
            routes = self.db_manager.get_active_routes()
            
            if len(users) > 1:  # Больше чем только админ
                logger.info("ℹ️ Демонстрационные данные уже существуют")
                return True
            
            # Создание водителей
            logger.info("👥 Создание демонстрационных водителей...")
            driver1_id = self.db_manager.create_user("Иванов", "Иван", "Иванович", "driver")
            driver2_id = self.db_manager.create_user("Петров", "Петр", "Петрович", "driver")
            driver3_id = self.db_manager.create_user("Сидоров", "Сидор", "Сидорович", "driver")
            
            # Создание транспортных средств
            logger.info("🚛 Создание демонстрационного автопарка...")
            vehicle1_id = self.db_manager.create_vehicle("9745", "ГАЗель Next", 1.5)
            vehicle2_id = self.db_manager.create_vehicle("8621", "Ford Transit", 2.0)
            vehicle3_id = self.db_manager.create_vehicle("7432", "Mercedes Sprinter", 3.5)
            vehicle4_id = self.db_manager.create_vehicle("6159", "МАЗ-4371", 5.0)
            
            # Создание маршрутов
            logger.info("🗺️ Создание демонстрационных маршрутов...")
            route1_id = self.db_manager.create_route("13", "Центральный район", 2500.0, "Доставка в центр города")
            route2_id = self.db_manager.create_route("7", "Промышленная зона", 3200.0, "Доставка на промышленные предприятия")
            route3_id = self.db_manager.create_route("25", "Пригород", 4100.0, "Доставка в пригородные районы")
            route4_id = self.db_manager.create_route("8", "Торговые центры", 2800.0, "Доставка в ТЦ и магазины")
            route5_id = self.db_manager.create_route("14", "Жилые районы", 2200.0, "Доставка в спальные районы")
            
            # Создание демонстрационных рейсов
            logger.info("🚚 Создание демонстрационных рейсов...")
            from datetime import date, timedelta
            
            today = date.today()
            yesterday = today - timedelta(days=1)
            two_days_ago = today - timedelta(days=2)
            
            # Рейсы за сегодня
            self.db_manager.create_trip(driver1_id, vehicle1_id, route1_id, "19036101", 1558, today)
            self.db_manager.create_trip(driver2_id, vehicle2_id, route2_id, "19036102", 2340, today)
            self.db_manager.create_trip(driver3_id, vehicle3_id, route3_id, "19036103", 950, today)
            
            # Рейсы за вчера
            self.db_manager.create_trip(driver1_id, vehicle2_id, route4_id, "19036098", 1890, yesterday)
            self.db_manager.create_trip(driver2_id, vehicle1_id, route1_id, "19036099", 2100, yesterday)
            self.db_manager.create_trip(driver3_id, vehicle4_id, route5_id, "19036100", 3200, yesterday)
            
            # Рейсы позавчера
            self.db_manager.create_trip(driver1_id, vehicle3_id, route2_id, "19036095", 1750, two_days_ago)
            self.db_manager.create_trip(driver2_id, vehicle4_id, route3_id, "19036096", 2850, two_days_ago)
            self.db_manager.create_trip(driver3_id, vehicle1_id, route4_id, "19036097", 1620, two_days_ago)
            
            logger.info("✅ Демонстрационные данные созданы успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания демонстрационных данных: {e}")
            return False
    
    def run_web_app(self):
        """Запуск веб-приложения в отдельном потоке"""
        import uvicorn
        
        logger.info(f"🌐 Запуск веб-приложения на {self.web_host}:{self.web_port}...")
        
        try:
            uvicorn.run(
                app,
                host=self.web_host,
                port=self.web_port,
                log_level="info",
                access_log=True
            )
        except Exception as e:
            logger.error(f"❌ Ошибка запуска веб-приложения: {e}")
    
    async def run_telegram_bot(self):
        """Запуск Telegram бота"""
        if not self.telegram_bot:
            logger.error("❌ Telegram бот не инициализирован")
            return
        
        logger.info("🤖 Запуск Telegram бота...")
        logger.info(f"🔍 Тип объекта: {type(self.telegram_bot)}")
        logger.info(f"🔍 Методы объекта: {[method for method in dir(self.telegram_bot) if not method.startswith('_')]}")
        
        try:
            if hasattr(self.telegram_bot, 'start_polling'):
                await self.telegram_bot.start_polling()
            else:
                logger.error("❌ У объекта ExpeditionBot нет метода start_polling")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")
    
    def print_startup_info(self):
        """Вывод информации о запуске системы"""
        print("\n" + "="*60)
        print("🚛 СИСТЕМА АВТОМАТИЗАЦИИ ЭКСПЕДИРОВАНИЯ")
        print("="*60)
        print(f"📅 Запуск: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"🌐 Веб-интерфейс: http://localhost:{self.web_port}")
        print(f"👤 Администратор: admin / admin123")
        print(f"🤖 Telegram бот: {'✅ Активен' if self.telegram_bot else '❌ Отключен'}")
        print(f"📅 Google Calendar: {'✅ Активен' if self.calendar_integration and self.calendar_integration.enabled else '❌ Отключен'}")
        print("="*60)
        
        if not self.telegram_bot:
            print("⚠️ Для активации Telegram бота:")
            print("   1. Создайте бота у @BotFather")
            print("   2. Установите TELEGRAM_BOT_TOKEN в переменные окружения")
            print("   3. Перезапустите систему")
            print()
        
        if not (self.calendar_integration and self.calendar_integration.enabled):
            print("⚠️ Для активации Google Calendar:")
            if not GOOGLE_CALENDAR_AVAILABLE:
                print("   1. Установите зависимости: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
                print("   2. Настройте Google Cloud Console")
                print("   3. Скачайте credentials.json")
                print("   4. Запустите: python google_calendar.py --setup")
            else:
                print("   1. Настройте Google Cloud Console")
                print("   2. Скачайте credentials.json")
                print("   3. Запустите: python google_calendar.py --setup")
            print()
        
        print("📋 Доступные команды:")
        print("   • Веб-интерфейс: откройте браузер и перейдите по ссылке выше")
        print("   • Telegram бот: найдите вашего бота и отправьте /start")
        print("   • Остановка: Ctrl+C")
        print("="*60)
    
    async def run_system(self):
        """Запуск всей системы"""
        logger.info("🚀 Запуск системы экспедирования...")
        
        # Инициализация компонентов
        if not self.initialize_database():
            logger.error("❌ Критическая ошибка: не удалось инициализировать базу данных")
            return False
        
        self.initialize_calendar()
        
        telegram_ready = self.initialize_telegram_bot()
        
        # Создание демонстрационных данных
        self.create_sample_data()
        
        # Вывод информации о запуске
        self.print_startup_info()
        
        # Запуск веб-приложения в отдельном потоке
        web_thread = threading.Thread(
            target=self.run_web_app,
            daemon=True,
            name="WebAppThread"
        )
        web_thread.start()
        
        # Небольшая задержка для запуска веб-сервера
        await asyncio.sleep(2)
        
        # Запуск Telegram бота (если доступен)
        if telegram_ready:
            try:
                await self.run_telegram_bot()
            except KeyboardInterrupt:
                logger.info("🛑 Получен сигнал остановки")
            except Exception as e:
                logger.error(f"❌ Ошибка работы Telegram бота: {e}")
        else:
            logger.info("⏳ Система работает только с веб-интерфейсом")
            logger.info("🌐 Веб-интерфейс доступен по адресу: http://localhost:8000")
            
            # Ожидание сигнала остановки
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("🛑 Получен сигнал остановки")
        
        logger.info("📴 Система экспедирования остановлена")
        return True

def check_dependencies():
    """Проверка установленных зависимостей"""
    required_packages = {
        'fastapi': 'FastAPI веб-фреймворк',
        'uvicorn': 'ASGI сервер для FastAPI',
        'jinja2': 'Шаблонизатор для веб-интерфейса',
        'python-multipart': 'Обработка форм в FastAPI',
        'aiogram': 'Telegram Bot API',
        'openpyxl': 'Работа с Excel файлами',
        'aiofiles': 'Асинхронная работа с файлами'
    }
    
    optional_packages = {
        'google-auth': 'Google Calendar интеграция',
        'google-auth-oauthlib': 'OAuth для Google API',
        'google-auth-httplib2': 'HTTP клиент для Google API',
        'google-api-python-client': 'Google API клиент'
    }
    
    missing_required = []
    missing_optional = []
    
    # Проверка обязательных пакетов
    for package, description in required_packages.items():
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_required.append((package, description))
    
    # Проверка опциональных пакетов
    for package, description in optional_packages.items():
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_optional.append((package, description))
    
    if missing_required:
        print("❌ Отсутствуют обязательные зависимости:")
        for package, description in missing_required:
            print(f"   • {package}: {description}")
        print("\n📦 Установите их командой:")
        print(f"   pip install {' '.join([p[0] for p in missing_required])}")
        return False
    
    if missing_optional:
        print("⚠️ Отсутствуют опциональные зависимости:")
        for package, description in missing_optional:
            print(f"   • {package}: {description}")
        print("\n📦 Для полной функциональности установите:")
        print(f"   pip install {' '.join([p[0] for p in missing_optional])}")
    
    return True

def create_env_file():
    """Создание файла с переменными окружения"""
    env_content = """# Настройки системы экспедирования

# Токен Telegram бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Настройки веб-сервера
WEB_HOST=0.0.0.0
WEB_PORT=8000

# Google Calendar интеграция (true/false)
GOOGLE_CALENDAR_ENABLED=true

# Настройки базы данных
DATABASE_PATH=expedition.db

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=expedition_system.log
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("📝 Создан файл .env с настройками по умолчанию")
        print("✏️ Отредактируйте его для настройки системы")
    else:
        print("ℹ️ Файл .env уже существует")

def load_env_file():
    """Загрузка переменных окружения из файла"""
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    try:
                        key, value = line.strip().split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value
                    except ValueError:
                        continue

def install_requirements():
    """Установка необходимых зависимостей"""
    requirements = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "jinja2>=3.1.0",
        "python-multipart>=0.0.6",
        "aiogram>=3.0.0",
        "openpyxl>=3.1.0",
        "aiofiles>=23.0.0",
        "python-dotenv>=1.0.0"
    ]
    
    optional_requirements = [
        "google-auth>=2.23.0",
        "google-auth-oauthlib>=1.1.0",
        "google-auth-httplib2>=0.1.1",
        "google-api-python-client>=2.100.0"
    ]
    
    print("📦 Установка зависимостей...")
    
    import subprocess
    
    try:
        # Установка обязательных зависимостей
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade", "pip"
        ])
        
        subprocess.check_call([
            sys.executable, "-m", "pip", "install"
        ] + requirements)
        
        print("✅ Обязательные зависимости установлены")
        
        # Попытка установки опциональных зависимостей
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install"
            ] + optional_requirements)
            print("✅ Опциональные зависимости установлены")
        except subprocess.CalledProcessError:
            print("⚠️ Некоторые опциональные зависимости не установлены")
            print("   Google Calendar интеграция может быть недоступна")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def main():
    """Главная функция запуска"""
    print("🚛 Система автоматизации экспедирования")
    print("=" * 50)
    
    # Обработка аргументов командной строки
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--install":
            print("📦 Установка зависимостей...")
            if install_requirements():
                print("✅ Зависимости установлены успешно")
                print("🚀 Теперь запустите: python main.py")
            else:
                print("❌ Ошибка установки зависимостей")
            return
        
        elif command == "--setup-calendar":
            print_setup_instructions()
            return
        
        elif command == "--create-env":
            create_env_file()
            return
        
        elif command == "--help":
            print("📋 Доступные команды:")
            print("   python main.py              - Запуск системы")
            print("   python main.py --install    - Установка зависимостей")
            print("   python main.py --setup-calendar - Инструкции по настройке Google Calendar")
            print("   python main.py --create-env - Создание файла настроек .env")
            print("   python main.py --help       - Эта справка")
            return
    
    # Загрузка переменных окружения
    load_env_file()
    
    # Проверка зависимостей
    if not check_dependencies():
        print("\n💡 Запустите: python main.py --install")
        print("   для автоматической установки зависимостей")
        return
    
    # Создание файла настроек если его нет
    if not os.path.exists('.env'):
        create_env_file()
    
    # Запуск системы
    try:
        system = ExpeditionSystem()
        asyncio.run(system.run_system())
    except KeyboardInterrupt:
        logger.info("🛑 Система остановлена пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка системы: {e}")
        logger.exception("Подробности ошибки:")

if __name__ == "__main__":
    main()