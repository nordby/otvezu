# telegram_bot.py - Исправленный Telegram бот с отслеживанием времени поездок

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from database import DatabaseManager, User

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния FSM для диалога
class TripStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()
    waiting_for_vehicle = State()
    waiting_for_waybill = State()
    waiting_for_route = State()
    waiting_for_quantity = State()
    confirming_trip = State()

class ExpeditionBot:
    def __init__(self, token: str, db_manager: DatabaseManager):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = db_manager
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message, state: FSMContext):
            """Обработчик команды /start"""
            user_id = message.from_user.id
            
            # Проверяем, есть ли уже авторизованный пользователь
            user = self.db.get_user_by_telegram_id(user_id)
            if user:
                # Инициализируем сессию если её нет
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = {
                        'user': user,
                        'current_trip': {}
                    }
                
                # Проверяем активный рейс
                active_trip = self.db.get_user_active_trip(user.id)
                menu = self.get_main_menu(active_trip)
                
                welcome_msg = f"Добро пожаловать, {user.first_name} {user.surname}!\n"
                
                if active_trip:
                    status_text = {
                        'created': 'создан, ожидает начала поездки',
                        'started': 'в процессе выполнения'
                    }
                    welcome_msg += f"\n📍 У вас есть активный рейс #{active_trip['id']} ({status_text.get(active_trip['status'], active_trip['status'])})"
                
                welcome_msg += "\n\nИспользуйте кнопки меню для навигации."
                
                await message.answer(welcome_msg, reply_markup=menu)
                return
            
            await message.answer(
                "🚛 Добро пожаловать в систему экспедирования!\n\n"
                "Для входа в систему введите вашу фамилию:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(TripStates.waiting_for_login)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_login))
        async def process_login(message: types.Message, state: FSMContext):
            """Обработка ввода фамилии"""
            surname = message.text.strip()
            await state.update_data(surname=surname)
            
            await message.answer(
                f"Фамилия: {surname}\n"
                f"Теперь введите ваш пароль:"
            )
            await state.set_state(TripStates.waiting_for_password)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_password))
        async def process_password(message: types.Message, state: FSMContext):
            """Обработка ввода пароля"""
            password = message.text.strip()
            data = await state.get_data()
            surname = data.get('surname')
            
            # Аутентификация пользователя
            user = self.db.authenticate_user(surname, password)
            
            if user and user.role == 'driver':
                # Привязываем Telegram ID к пользователю
                self.db.link_telegram_user(user.id, message.from_user.id)
                
                # Инициализируем сессию пользователя
                self.user_sessions[message.from_user.id] = {
                    'user': user,
                    'current_trip': {}
                }
                
                # Проверяем активный рейс
                active_trip = self.db.get_user_active_trip(user.id)
                menu = self.get_main_menu(active_trip)
                
                welcome_msg = f"✅ Авторизация успешна!\nДобро пожаловать, {user.first_name} {user.surname}!"
                
                if active_trip:
                    status_text = {
                        'created': 'создан, ожидает начала поездки',
                        'started': 'в процессе выполнения'
                    }
                    welcome_msg += f"\n\n📍 У вас есть активный рейс #{active_trip['id']} ({status_text.get(active_trip['status'], active_trip['status'])})"
                
                welcome_msg += "\n\nИспользуйте кнопки меню для навигации."
                
                await message.answer(welcome_msg, reply_markup=menu)
                await state.clear()
            else:
                await message.answer(
                    "❌ Неверная фамилия или пароль!\n"
                    "Попробуйте еще раз.\n\n"
                    "Введите вашу фамилию:"
                )
                await state.set_state(TripStates.waiting_for_login)
        
        @self.dp.message(Command("trip"))
        async def cmd_trip(message: types.Message, state: FSMContext):
            """Обработчик команды /trip - начало добавления рейса"""
            await start_trip_creation(message, state)
        
        async def start_trip_creation(message: types.Message, state: FSMContext):
            """Функция для начала создания рейса"""
            user_id = message.from_user.id
            
            if user_id not in self.user_sessions:
                await message.answer(
                    "❌ Вы не авторизованы в системе.\n"
                    "Используйте команду /start для входа."
                )
                return
            
            user = self.user_sessions[user_id]['user']
            
            # Проверяем, нет ли уже активного рейса
            active_trip = self.db.get_user_active_trip(user.id)
            if active_trip:
                await message.answer(
                    f"❌ У вас уже есть активный рейс #{active_trip['id']}.\n"
                    f"Завершите текущий рейс перед созданием нового.",
                    reply_markup=self.get_main_menu(active_trip)
                )
                return
            
            # Получаем активные ТС
            vehicles = self.db.get_active_vehicles()
            if not vehicles:
                await message.answer(
                    "❌ В системе нет доступных транспортных средств.\n"
                    "Обратитесь к администратору."
                )
                return
            
            # Инициализируем новый рейс
            self.user_sessions[user_id]['current_trip'] = {}
            
            await message.answer(
                "🚛 Создание нового рейса\n\n"
                "Выберите ваше транспортное средство:",
                reply_markup=self.get_vehicles_keyboard(vehicles)
            )
            await state.set_state(TripStates.waiting_for_vehicle)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_vehicle))
        async def process_vehicle_selection(message: types.Message, state: FSMContext):
            """Обработка выбора ТС"""
            user_id = message.from_user.id
            vehicle_text = message.text.strip()
            
            logger.info(f"Пользователь {user_id} выбрал ТС: '{vehicle_text}'")
            
            # Находим ТС по номеру - улучшенный поиск
            vehicles = self.db.get_active_vehicles()
            selected_vehicle = None
            
            # Извлекаем номер из текста кнопки
            for vehicle in vehicles:
                # Проверяем точное соответствие с форматом кнопки
                expected_text = f"🚛 {vehicle.number} ({vehicle.model})"
                if vehicle_text == expected_text:
                    selected_vehicle = vehicle
                    logger.info(f"Найдено точное соответствие ТС: {vehicle.number}")
                    break
                # Альтернативная проверка по номеру
                elif vehicle.number in vehicle_text:
                    selected_vehicle = vehicle
                    logger.info(f"Найдено соответствие по номеру ТС: {vehicle.number}")
                    break
            
            if not selected_vehicle:
                logger.warning(f"ТС не найдено для текста: '{vehicle_text}'")
                await message.answer(
                    "❌ Выберите транспортное средство из предложенных вариантов:",
                    reply_markup=self.get_vehicles_keyboard(vehicles)
                )
                return
            
            # Сохраняем выбранное ТС
            self.user_sessions[user_id]['current_trip']['vehicle_id'] = selected_vehicle.id
            self.user_sessions[user_id]['current_trip']['vehicle_number'] = selected_vehicle.number
            
            await message.answer(
                f"✅ Выбрано ТС: {selected_vehicle.number} ({selected_vehicle.model})\n\n"
                f"Теперь введите номер путевого листа:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(TripStates.waiting_for_waybill)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_waybill))
        async def process_waybill(message: types.Message, state: FSMContext):
            """Обработка ввода номера путевого листа"""
            user_id = message.from_user.id
            waybill_number = message.text.strip()
            
            # Простая валидация номера путевого листа
            if not waybill_number.isdigit() or len(waybill_number) < 6:
                await message.answer(
                    "❌ Номер путевого листа должен содержать только цифры и быть не менее 6 символов.\n"
                    "Введите номер путевого листа:"
                )
                return
            
            # Сохраняем номер путевого листа
            self.user_sessions[user_id]['current_trip']['waybill_number'] = waybill_number
            
            # Получаем активные маршруты
            routes = self.db.get_active_routes(include_price=False)  # Цену водителям не показываем
            if not routes:
                await message.answer(
                    "❌ В системе нет доступных маршрутов.\n"
                    "Обратитесь к администратору."
                )
                return
            
            await message.answer(
                f"✅ Путевой лист: {waybill_number}\n\n"
                f"Выберите маршрут:",
                reply_markup=self.get_routes_keyboard(routes)
            )
            await state.set_state(TripStates.waiting_for_route)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_route))
        async def process_route_selection(message: types.Message, state: FSMContext):
            """Обработка выбора маршрута"""
            user_id = message.from_user.id
            route_text = message.text.strip()
            
            logger.info(f"Пользователь {user_id} выбрал маршрут: '{route_text}'")
            
            # Находим маршрут по номеру - улучшенный поиск
            routes = self.db.get_active_routes()
            selected_route = None
            
            for route in routes:
                # Проверяем точное соответствие с форматом кнопки
                expected_text = f"🗺 Маршрут №{route.number} - {route.name}"
                if route_text == expected_text:
                    selected_route = route
                    logger.info(f"Найдено точное соответствие маршрута: {route.number}")
                    break
                # Альтернативная проверка по номеру
                elif f"№{route.number}" in route_text:
                    selected_route = route
                    logger.info(f"Найдено соответствие по номеру маршрута: {route.number}")
                    break
            
            if not selected_route:
                logger.warning(f"Маршрут не найден для текста: '{route_text}'")
                routes_display = self.db.get_active_routes(include_price=False)
                await message.answer(
                    "❌ Выберите маршрут из предложенных вариантов:",
                    reply_markup=self.get_routes_keyboard(routes_display)
                )
                return
            
            # Сохраняем выбранный маршрут
            self.user_sessions[user_id]['current_trip']['route_id'] = selected_route.id
            self.user_sessions[user_id]['current_trip']['route_number'] = selected_route.number
            self.user_sessions[user_id]['current_trip']['route_name'] = selected_route.name
            
            await message.answer(
                f"✅ Выбран маршрут: №{selected_route.number} - {selected_route.name}\n\n"
                f"Введите количество доставленного товара (в штуках):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(TripStates.waiting_for_quantity)
        
        @self.dp.message(StateFilter(TripStates.waiting_for_quantity))
        async def process_quantity(message: types.Message, state: FSMContext):
            """Обработка ввода количества товара"""
            user_id = message.from_user.id
            quantity_text = message.text.strip()
            
            try:
                quantity = int(quantity_text)
                if quantity <= 0:
                    raise ValueError("Количество должно быть положительным")
            except ValueError:
                await message.answer(
                    "❌ Введите корректное количество товара (целое положительное число):"
                )
                return
            
            # Сохраняем количество
            self.user_sessions[user_id]['current_trip']['quantity_delivered'] = quantity
            
            # Формируем сводку для подтверждения
            trip_data = self.user_sessions[user_id]['current_trip']
            user = self.user_sessions[user_id]['user']
            
            summary = (
                f"📋 Подтверждение рейса\n\n"
                f"👤 Водитель: {user.first_name} {user.surname}\n"
                f"🚛 ТС: {trip_data['vehicle_number']}\n"
                f"📄 Путевой лист: {trip_data['waybill_number']}\n"
                f"🗺 Маршрут: №{trip_data['route_number']} - {trip_data['route_name']}\n"
                f"📦 Количество: {quantity} шт.\n"
                f"📅 Дата: {date.today().strftime('%d.%m.%Y')}\n\n"
                f"❗ После создания рейса вам нужно будет нажать 'Начать поездку' когда отправляетесь, "
                f"и 'Завершить поездку' по окончании.\n\n"
                f"Создать рейс?"
            )
            
            await message.answer(
                summary,
                reply_markup=self.get_confirmation_keyboard()
            )
            await state.set_state(TripStates.confirming_trip)
        
        @self.dp.message(StateFilter(TripStates.confirming_trip))
        async def process_confirmation(message: types.Message, state: FSMContext):
            """Обработка подтверждения рейса"""
            user_id = message.from_user.id
            confirmation = message.text.strip()
            
            if confirmation == "✅ Подтвердить":
                # Создаем рейс в базе данных
                trip_data = self.user_sessions[user_id]['current_trip']
                user = self.user_sessions[user_id]['user']
                
                try:
                    trip_id = self.db.create_trip(
                        user_id=user.id,
                        vehicle_id=trip_data['vehicle_id'],
                        route_id=trip_data['route_id'],
                        waybill_number=trip_data['waybill_number'],
                        quantity_delivered=trip_data['quantity_delivered']
                    )
                    
                    # Получаем созданный рейс
                    active_trip = self.db.get_user_active_trip(user.id)
                    
                    await message.answer(
                        f"✅ Рейс #{trip_id} создан успешно!\n\n"
                        f"📍 Статус: Ожидает начала поездки\n"
                        f"⏰ Нажмите 'Начать поездку' когда отправляетесь по маршруту.",
                        reply_markup=self.get_main_menu(active_trip)
                    )
                    
                    # Очищаем данные создания рейса
                    self.user_sessions[user_id]['current_trip'] = {}
                    await state.clear()
                    
                except Exception as e:
                    logger.error(f"Ошибка создания рейса: {e}")
                    await message.answer(
                        "❌ Произошла ошибка при создании рейса.\n"
                        "Попробуйте еще раз или обратитесь к администратору.",
                        reply_markup=self.get_main_menu()
                    )
                    await state.clear()
                    
            elif confirmation == "❌ Отменить":
                await message.answer(
                    "❌ Создание рейса отменено.\n"
                    "Используйте кнопки меню для создания нового рейса.",
                    reply_markup=self.get_main_menu()
                )
                self.user_sessions[user_id]['current_trip'] = {}
                await state.clear()
            else:
                await message.answer(
                    "❓ Пожалуйста, выберите один из предложенных вариантов:",
                    reply_markup=self.get_confirmation_keyboard()
                )
        
        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            """Обработчик команды /help"""
            help_text = (
                "🆘 Справка по боту\n\n"
                "📋 Доступные команды:\n"
                "/start - Авторизация в системе\n"
                "/trip - Создать новый рейс\n"
                "/help - Показать эту справку\n\n"
                "🔄 Процесс работы с рейсом:\n"
                "1. Создайте рейс (выбор ТС, маршрута, количества)\n"
                "2. Нажмите 'Начать поездку' когда отправляетесь\n"
                "3. Нажмите 'Завершить поездку' по прибытии\n"
                "4. Данные автоматически добавляются в календарь\n\n"
                "📍 Статусы рейсов:\n"
                "• Создан - ожидает начала поездки\n"
                "• В пути - поездка начата\n"
                "• Завершен - поездка закончена\n\n"
                "❓ При возникновении проблем обратитесь к администратору."
            )
            await message.answer(help_text)
        
        @self.dp.message()
        async def handle_text_messages(message: types.Message, state: FSMContext):
            """Обработчик текстовых сообщений в главном меню"""
            user_id = message.from_user.id
            text = message.text.strip()
            
            # Проверяем состояние FSM
            current_state = await state.get_state()
            if current_state is not None:
                # Если мы в процессе диалога, не обрабатываем как команды главного меню
                logger.warning(f"Получено сообщение '{text}' в состоянии {current_state}")
                return
            
            if user_id not in self.user_sessions:
                await message.answer(
                    "❌ Вы не авторизованы в системе.\n"
                    "Используйте команду /start для входа."
                )
                return
            
            user = self.user_sessions[user_id]['user']
            
            if text == "➕ Создать рейс":
                await start_trip_creation(message, state)
                
            elif text == "🚀 Начать поездку":
                await self.handle_start_trip(message, user)
                
            elif text == "🏁 Завершить поездку":
                await self.handle_complete_trip(message, user)
                
            elif text == "📋 Мои рейсы":
                await self.show_user_trips(message, user)
                
            elif text == "ℹ️ Справка":
                await cmd_help(message)
                
            else:
                logger.info(f"Неизвестная команда от пользователя {user_id}: '{text}'")
                await message.answer(
                    "❓ Неизвестная команда.\n"
                    "Используйте кнопки меню или команду /help для справки.",
                    reply_markup=self.get_main_menu()
                )
    
    async def handle_start_trip(self, message: types.Message, user: User):
        """Обработка начала поездки"""
        active_trip = self.db.get_user_active_trip(user.id)
        
        if not active_trip:
            await message.answer(
                "❌ У вас нет активного рейса для начала поездки.",
                reply_markup=self.get_main_menu()
            )
            return
        
        if active_trip['status'] != 'created':
            await message.answer(
                f"❌ Рейс #{active_trip['id']} уже начат или завершен.",
                reply_markup=self.get_main_menu(active_trip)
            )
            return
        
        try:
            # Создаем событие в календаре с начальным временем (1 минута для лучшего отображения)
            calendar_event_id = await self.create_calendar_event(active_trip, user, duration_hours=0.017)
            
            # Начинаем поездку
            success = self.db.start_trip(active_trip['id'], calendar_event_id)
            
            if success:
                start_time = datetime.now().strftime('%H:%M')
                await message.answer(
                    f"🚀 Поездка начата!\n\n"
                    f"📍 Рейс: #{active_trip['id']}\n"
                    f"🕐 Время начала: {start_time}\n"
                    f"🗺 Маршрут: №{active_trip['route_number']} - {active_trip['route_name']}\n"
                    f"🚛 ТС: {active_trip['vehicle_number']}\n\n"
                    f"📅 Событие добавлено в календарь.\n"
                    f"⏰ Нажмите 'Завершить поездку' по прибытии.",
                    reply_markup=self.get_main_menu(self.db.get_user_active_trip(user.id))
                )
            else:
                await message.answer(
                    "❌ Ошибка при начале поездки. Попробуйте еще раз.",
                    reply_markup=self.get_main_menu(active_trip)
                )
                
        except Exception as e:
            logger.error(f"Ошибка начала поездки: {e}")
            await message.answer(
                "❌ Произошла ошибка при начале поездки.",
                reply_markup=self.get_main_menu(active_trip)
            )
    
    async def handle_complete_trip(self, message: types.Message, user: User):
        """Обработка завершения поездки"""
        active_trip = self.db.get_user_active_trip(user.id)
        
        if not active_trip:
            await message.answer(
                "❌ У вас нет активного рейса для завершения.",
                reply_markup=self.get_main_menu()
            )
            return
        
        if active_trip['status'] != 'started':
            await message.answer(
                f"❌ Рейс #{active_trip['id']} не начат или уже завершен.",
                reply_markup=self.get_main_menu(active_trip)
            )
            return
        
        try:
            # Завершаем поездку
            success = self.db.complete_trip(active_trip['id'])

            if success:
                logger.info(f"🎯 Рейс {active_trip['id']} успешно завершен в базе данных")
                
                # Получаем обновленные данные сразу после завершения
                completed_trips = self.db.get_trips_for_report()
                completed_trip = None
                for trip in completed_trips:
                    if trip['id'] == active_trip['id']:
                        completed_trip = trip
                        break
                
                duration_text = ""
                if completed_trip and completed_trip.get('duration_hours'):
                    hours = int(completed_trip['duration_hours'])
                    minutes = int((completed_trip['duration_hours'] - hours) * 60)
                    duration_text = f"\n⏱ Продолжительность: {hours}ч {minutes}мин"
                    logger.info(f"🔍 Данные завершенного рейса: статус={completed_trip.get('status')}, продолжительность={completed_trip.get('duration_hours')}")
                else:
                    logger.warning(f"❌ Не удалось найти завершенный рейс {active_trip['id']} в базе")
                
                # Обновляем событие в календаре с реальным временем
                await self.update_calendar_event(active_trip, user)
                
                end_time = datetime.now().strftime('%H:%M')
                await message.answer(
                    f"🏁 Поездка завершена!\n\n"
                    f"📍 Рейс: #{active_trip['id']}\n"
                    f"🕐 Время завершения: {end_time}{duration_text}\n"
                    f"🗺 Маршрут: №{active_trip['route_number']} - {active_trip['route_name']}\n"
                    f"🚛 ТС: {active_trip['vehicle_number']}\n"
                    f"📦 Доставлено: {active_trip['quantity_delivered']} шт.\n\n"
                    f"📅 Событие в календаре обновлено с реальным временем.\n"
                    f"✅ Данные переданы в систему отчетности.",
                    reply_markup=self.get_main_menu()
                )
            else:
                await message.answer(
                    "❌ Ошибка при завершении поездки. Попробуйте еще раз.",
                    reply_markup=self.get_main_menu(active_trip)
                )
                
        except Exception as e:
            logger.error(f"Ошибка завершения поездки: {e}")
            await message.answer(
                "❌ Произошла ошибка при завершении поездки.",
                reply_markup=self.get_main_menu(active_trip)
            )
    
    async def show_user_trips(self, message: types.Message, user: User):
        """Показать рейсы пользователя"""
        try:
            # Получаем рейсы за последние 7 дней
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            trips = self.db.get_trips_for_report(
                start_date=start_date,
                end_date=end_date,
                user_id=user.id
            )
            
            if not trips:
                await message.answer(
                    "📋 У вас нет рейсов за последние 7 дней.",
                    reply_markup=self.get_main_menu()
                )
                return
            
            # Формируем отчет
            report_text = f"📋 Ваши рейсы за последние 7 дней:\n\n"
            
            status_emoji = {
                'created': '🟡',
                'started': '🔵', 
                'completed': '🟢',
                'cancelled': '🔴'
            }
            
            status_text = {
                'created': 'Создан',
                'started': 'В пути',
                'completed': 'Завершен',
                'cancelled': 'Отменен'
            }
            
            for trip in trips[:10]:  # Показываем последние 10
                emoji = status_emoji.get(trip['status'], '⚪')
                status = status_text.get(trip['status'], trip['status'])
                
                trip_info = f"{emoji} Рейс #{trip['id']} ({status})\n"
                trip_info += f"📅 {trip['date']}\n"
                trip_info += f"🗺 Путевой лист: {trip['waybill_number']}\n"
                trip_info += f"🚛 ТС: {trip['vehicle_number']}\n"
                trip_info += f"📦 Количество: {trip['quantity']} шт.\n"
                
                if trip['duration_hours']:
                    hours = int(trip['duration_hours'])
                    minutes = int((trip['duration_hours'] - hours) * 60)
                    trip_info += f"⏱ Время: {hours}ч {minutes}мин\n"
                
                trip_info += "\n"
                report_text += trip_info
            
            # Добавляем статистику
            completed_trips = [t for t in trips if t['status'] == 'completed']
            total_revenue = sum(t['total_amount'] for t in completed_trips)
            total_hours = sum(t['duration_hours'] for t in completed_trips if t['duration_hours'])
            
            report_text += f"📊 Статистика за 7 дней:\n"
            report_text += f"✅ Завершено рейсов: {len(completed_trips)}\n"

            if total_hours:
                report_text += f"⏱ Общее время: {total_hours:.1f} часов\n"
            
            await message.answer(report_text, reply_markup=self.get_main_menu())
            
        except Exception as e:
            logger.error(f"Ошибка получения рейсов пользователя: {e}")
            await message.answer(
                "❌ Ошибка получения данных о рейсах.",
                reply_markup=self.get_main_menu()
            )
    
    def get_main_menu(self, active_trip: Dict[str, Any] = None) -> ReplyKeyboardMarkup:
        """Создание главного меню в зависимости от состояния рейса"""
        builder = ReplyKeyboardBuilder()
        
        if active_trip:
            if active_trip['status'] == 'created':
                # Рейс создан, можно начать поездку
                builder.row(KeyboardButton(text="🚀 Начать поездку"))
            elif active_trip['status'] == 'started':
                # Поездка начата, можно завершить
                builder.row(KeyboardButton(text="🏁 Завершить поездку"))
        else:
            # Нет активного рейса, можно создать новый
            builder.row(KeyboardButton(text="➕ Создать рейс"))
        
        builder.row(KeyboardButton(text="📋 Мои рейсы"))
        builder.row(KeyboardButton(text="ℹ️ Справка"))
        
        return builder.as_markup(resize_keyboard=True, persistent=True)
    
    def get_vehicles_keyboard(self, vehicles) -> ReplyKeyboardMarkup:
        """Создание клавиатуры для выбора ТС"""
        builder = ReplyKeyboardBuilder()
        for vehicle in vehicles:
            button_text = f"🚛 {vehicle.number} ({vehicle.model})"
            builder.row(KeyboardButton(text=button_text))
        return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    
    def get_routes_keyboard(self, routes) -> ReplyKeyboardMarkup:
        """Создание клавиатуры для выбора маршрута"""
        builder = ReplyKeyboardBuilder()
        for route in routes:
            button_text = f"🗺 Маршрут №{route.number} - {route.name}"
            builder.row(KeyboardButton(text=button_text))
        return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    
    def get_confirmation_keyboard(self) -> ReplyKeyboardMarkup:
        """Создание клавиатуры для подтверждения"""
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="✅ Подтвердить"))
        builder.row(KeyboardButton(text="❌ Отменить"))
        return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    
    async def create_calendar_event(self, trip_data: Dict[str, Any], user: User, duration_hours: float = 2.0) -> Optional[str]:
        """Создание события в Google Календаре с улучшенной продолжительностью"""
        try:
            from google_calendar import CalendarIntegration
            
            calendar_integration = CalendarIntegration(enabled=True)
            
            if not calendar_integration.enabled:
                logger.warning("Google Calendar интеграция отключена")
                return None
            
            # Подготавливаем данные для календаря
            calendar_trip_data = {
                'id': trip_data['id'],
                'waybill_number': trip_data['waybill_number'],
                'vehicle_number': trip_data['vehicle_number'],
                'route_number': trip_data['route_number'],
                'route_name': trip_data['route_name'],
                'quantity_delivered': trip_data['quantity_delivered'],
                'duration_hours': duration_hours,
                'started_at': datetime.now().isoformat()
            }
            
            calendar_user_data = {
                'id': user.id,
                'surname': user.surname,
                'first_name': user.first_name,
                'middle_name': user.middle_name
            }
            
            # Создаем событие
            event_id = calendar_integration.create_trip_event_sync(calendar_trip_data, calendar_user_data)
            
            if event_id:
                logger.info(f"Создано событие в Google Calendar: {event_id}")
                return event_id
            else:
                logger.error("Не удалось создать событие в Google Calendar")
                return None
                
        except ImportError:
            logger.warning("Модуль google_calendar не доступен")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания события в календаре: {e}")
            return None
    
    async def update_calendar_event(self, trip_data: Dict[str, Any], user: User) -> bool:
        """Обновление события в Google Календаре с реальным временем"""
        try:
            from google_calendar import CalendarIntegration
            
            calendar_integration = CalendarIntegration(enabled=True)
            
            if not calendar_integration.enabled or not trip_data.get('calendar_event_id'):
                logger.warning("Google Calendar интеграция отключена или нет ID события")
                return False
            
            # Получаем актуальные данные рейса
            logger.info(f"🔍 Ищем рейс ID: {trip_data['id']}")
            updated_trips = self.db.get_trips_for_report()
            
            current_trip = None
            for trip in updated_trips:
                if trip['id'] == trip_data['id']:
                    current_trip = trip
                    logger.info(f"✅ Найден рейс: {trip}")
                    break
            
            if not current_trip:
                logger.warning(f"❌ Рейс с ID {trip_data['id']} не найден в базе")
                return False
            
            # Проверяем наличие данных о продолжительности
            if not current_trip.get('duration_hours'):
                logger.warning(f"⚠️ У рейса {trip_data['id']} нет данных о продолжительности. Статус: {current_trip.get('status')}")
                
                # Если рейс завершен, но нет duration_hours, попробуем обновить без них
                if current_trip.get('status') == 'completed':
                    logger.info("🔄 Пытаемся обновить событие без данных о продолжительности")
                else:
                    return False
            
            # Подготавливаем данные для обновления
            calendar_trip_data = {
                'id': current_trip['id'],
                'waybill_number': current_trip['waybill_number'],
                'vehicle_number': current_trip['vehicle_number'],
                'route_number': trip_data['route_number'],
                'route_name': trip_data['route_name'],
                'quantity_delivered': current_trip.get('quantity', 0),
                'duration_hours': current_trip.get('duration_hours', 0),
                'started_at': current_trip.get('started_at'),
                'completed_at': current_trip.get('completed_at')
            }
            
            calendar_user_data = {
                'id': user.id,
                'surname': user.surname,
                'first_name': user.first_name,
                'middle_name': user.middle_name
            }
            
            logger.info(f"📅 Обновляем событие календаря с данными: {calendar_trip_data}")
            
            # Обновляем событие
            success = calendar_integration.update_trip_event_sync(
                trip_data['calendar_event_id'], 
                calendar_trip_data, 
                calendar_user_data
            )
            
            if success:
                logger.info(f"✅ Обновлено событие в Google Calendar: {trip_data['calendar_event_id']}")
                return True
            else:
                logger.error("❌ Не удалось обновить событие в Google Calendar")
                return False
                
        except ImportError:
            logger.warning("⚠️ Модуль google_calendar не доступен")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка обновления события в календаре: {e}")
            return False
    
    async def start_polling(self):
        """Запуск бота в режиме long polling"""
        try:
            logger.info("🤖 Запуск Telegram бота...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
        finally:
            await self.bot.session.close()

# Функция для запуска бота
async def main():
    # Токен бота (получить у @BotFather)
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Установите токен бота в переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    # Инициализация базы данных
    from database import DatabaseManager
    db = DatabaseManager()
    
    # Создание и запуск бота
    bot = ExpeditionBot(BOT_TOKEN, db)
    
    print("🤖 Telegram бот запускается...")
    await bot.start_polling()

if __name__ == "__main__":
    asyncio.run(main())