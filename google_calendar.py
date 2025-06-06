# google_calendar.py - Исправленная интеграция с Google Calendar

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальная переменная для определения доступности Google Calendar
GOOGLE_CALENDAR_AVAILABLE = False

# Безопасный импорт Google API
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
    logger.info("✅ Google Calendar API модули доступны")
except ImportError as e:
    logger.warning(f"⚠️ Google Calendar API недоступен: {e}")

class GoogleCalendarManager:
    """Менеджер для работы с Google Calendar API"""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.calendar_id = 'primary'
        self.is_authenticated = False
        
    def authenticate(self) -> bool:
        """Аутентификация с Google Calendar API"""
        if not GOOGLE_CALENDAR_AVAILABLE:
            logger.error("Google Calendar API недоступен")
            return False
            
        try:
            creds = None
            
            # Проверяем существующий токен
            if os.path.exists(self.token_file):
                try:
                    creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                    logger.info("Загружен существующий токен")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки токена: {e}")
                    creds = None
            
            # Если нет валидных учетных данных, запрашиваем авторизацию
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        logger.info("Токен обновлен")
                    except Exception as e:
                        logger.error(f"Ошибка обновления токена: {e}")
                        creds = None
                
                if not creds:
                    if not os.path.exists(self.credentials_file):
                        logger.error(f"Файл {self.credentials_file} не найден")
                        return False
                    
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_file, self.SCOPES)
                        creds = flow.run_local_server(port=0)
                        logger.info("Новая авторизация выполнена")
                    except Exception as e:
                        logger.error(f"Ошибка авторизации: {e}")
                        return False
                
                # Сохраняем учетные данные
                try:
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("Токен сохранен")
                except Exception as e:
                    logger.warning(f"Ошибка сохранения токена: {e}")
            
            # Создаем сервис
            self.service = build('calendar', 'v3', credentials=creds)
            self.is_authenticated = True
            logger.info("✅ Успешная аутентификация с Google Calendar")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка аутентификации с Google Calendar: {e}")
            self.is_authenticated = False
            return False
    
    def create_trip_event(self, trip_data: Dict[str, Any], user_data: Dict[str, Any]) -> Optional[str]:
        """Создание события рейса в календаре с улучшенной обработкой времени"""
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            # Определяем время события
            now = datetime.now()
            
            if trip_data.get('started_at'):
                # Если есть время начала, парсим его
                if isinstance(trip_data['started_at'], str):
                    try:
                        # Пробуем разные форматы времени
                        if 'T' in trip_data['started_at']:
                            # ISO формат
                            start_time = datetime.fromisoformat(trip_data['started_at'].replace('Z', ''))
                        else:
                            # Возможно, это уже datetime объект в строковом виде
                            start_time = datetime.fromisoformat(trip_data['started_at'])
                    except:
                        logger.warning(f"Не удалось парсить время начала: {trip_data['started_at']}")
                        start_time = now
                else:
                    start_time = trip_data['started_at']
            else:
                # Если нет времени начала, используем текущее время
                start_time = now
            
            # Определяем время окончания
            if trip_data.get('completed_at'):
                if isinstance(trip_data['completed_at'], str):
                    try:
                        if 'T' in trip_data['completed_at']:
                            end_time = datetime.fromisoformat(trip_data['completed_at'].replace('Z', ''))
                        else:
                            end_time = datetime.fromisoformat(trip_data['completed_at'])
                    except:
                        logger.warning(f"Не удалось парсить время окончания: {trip_data['completed_at']}")
                        duration = max(trip_data.get('duration_hours', 2.0), 1.0)  # Минимум 1 час
                        end_time = start_time + timedelta(hours=duration)
                else:
                    end_time = trip_data['completed_at']
            else:
                # Если поездка не завершена, используем продолжительность
                duration = max(trip_data.get('duration_hours', 2.0), 1.0)  # Минимум 1 час для видимости
                end_time = start_time + timedelta(hours=duration)
            
            # Убеждаемся, что end_time > start_time
            if end_time <= start_time:
                end_time = start_time + timedelta(hours=1)
            
            # Формируем название и описание
            driver_name = f"{user_data.get('surname', '')} {user_data.get('first_name', '')}"
            if user_data.get('middle_name'):
                driver_name += f" {user_data.get('middle_name', '')}"
            
            # Определяем статус поездки
            status_info = ""
            if trip_data.get('completed_at'):
                status_info = "✅ ЗАВЕРШЕНА"
                if trip_data.get('duration_hours'):
                    real_duration = trip_data['duration_hours']
                    hours = int(real_duration)
                    minutes = int((real_duration - hours) * 60)
                    status_info += f" ({hours}ч {minutes}мин)"
            elif trip_data.get('started_at'):
                status_info = "🚀 В ПУТИ"
            else:
                status_info = "⏰ ЗАПЛАНИРОВАНА"
            
            summary = f"Рейс #{trip_data.get('waybill_number', 'N/A')} - {driver_name} [{status_info}]"
            
            description = f"""
🚛 Детали рейса:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Водитель: {driver_name}
🚗 ТС: {trip_data.get('vehicle_number', 'N/A')}
📄 Путевой лист: {trip_data.get('waybill_number', 'N/A')}
🗺️ Маршрут: №{trip_data.get('route_number', 'N/A')} - {trip_data.get('route_name', '')}
📦 Доставлено: {trip_data.get('quantity_delivered', 0)} шт.
📅 Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{status_info}

⏰ Время события:
🚀 Начало: {start_time.strftime('%d.%m.%Y %H:%M')}
🏁 Окончание: {end_time.strftime('%d.%m.%Y %H:%M')}
⏱ Продолжительность: {(end_time - start_time).total_seconds() / 3600:.1f}ч
            """.strip()
            
            # Выбираем цвет в зависимости от статуса
            color_id = '9'  # Синий по умолчанию
            if trip_data.get('completed_at'):
                color_id = '10'  # Зеленый для завершенных
            elif trip_data.get('started_at'):
                color_id = '11'  # Красный для активных
            
            # Создаем событие
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Europe/Riga',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Europe/Riga',
                },
                'colorId': color_id,
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                    ],
                },
                'extendedProperties': {
                    'private': {
                        'source': 'expedition_system',
                        'trip_id': str(trip_data.get('id', '')),
                        'driver_id': str(user_data.get('id', '')),
                        'vehicle_number': trip_data.get('vehicle_number', ''),
                        'route_number': trip_data.get('route_number', ''),
                        'waybill_number': trip_data.get('waybill_number', ''),
                        'created_at': datetime.now().isoformat(),
                        'status': 'completed' if trip_data.get('completed_at') else 'started' if trip_data.get('started_at') else 'planned',
                        'duration_hours': str(trip_data.get('duration_hours', 0))
                    }
                }
            }
            
            # Создаем событие в календаре
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            event_id = created_event.get('id')
            event_link = created_event.get('htmlLink')
            
            logger.info(f"✅ Событие создано в Google Calendar: {event_id}")
            logger.info(f"🔗 Ссылка на событие: {event_link}")
            logger.info(f"⏰ Время события: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({(end_time - start_time).total_seconds() / 3600:.1f}ч)")
            
            return event_id
            
        except Exception as error:
            logger.error(f"❌ Ошибка при создании события: {error}")
            return None
    
    def update_trip_event(self, event_id: str, trip_data: Dict[str, Any], user_data: Dict[str, Any]) -> bool:
        """Обновление существующего события рейса с реальным временем"""
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            # Получаем существующее событие
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Обновляем время на основе реальных данных
            if trip_data.get('started_at') and trip_data.get('completed_at'):
                # Поездка завершена - используем реальное время
                try:
                    if isinstance(trip_data['started_at'], str):
                        start_time = datetime.fromisoformat(trip_data['started_at'].replace('Z', ''))
                    else:
                        start_time = trip_data['started_at']
                        
                    if isinstance(trip_data['completed_at'], str):
                        end_time = datetime.fromisoformat(trip_data['completed_at'].replace('Z', ''))
                    else:
                        end_time = trip_data['completed_at']
                except:
                    # Если не удалось парсить, оставляем текущее время
                    start_time = datetime.fromisoformat(event['start']['dateTime'])
                    end_time = datetime.fromisoformat(event['end']['dateTime'])
            elif trip_data.get('started_at'):
                # Поездка начата, но не завершена
                try:
                    if isinstance(trip_data['started_at'], str):
                        start_time = datetime.fromisoformat(trip_data['started_at'].replace('Z', ''))
                    else:
                        start_time = trip_data['started_at']
                    
                    # Используем расчетную продолжительность
                    duration = max(trip_data.get('duration_hours', 2.0), 1.0)
                    end_time = start_time + timedelta(hours=duration)
                except:
                    start_time = datetime.fromisoformat(event['start']['dateTime'])
                    end_time = datetime.fromisoformat(event['end']['dateTime'])
            else:
                # Оставляем текущее время
                start_time = datetime.fromisoformat(event['start']['dateTime'])
                end_time = datetime.fromisoformat(event['end']['dateTime'])
            
            # Убеждаемся, что end_time > start_time
            if end_time <= start_time:
                end_time = start_time + timedelta(hours=1)
            
            # Формируем обновленное название и описание
            driver_name = f"{user_data.get('surname', '')} {user_data.get('first_name', '')}"
            if user_data.get('middle_name'):
                driver_name += f" {user_data.get('middle_name', '')}"
            
            # Определяем статус поездки
            status_info = ""
            if trip_data.get('completed_at'):
                status_info = "✅ ЗАВЕРШЕНА"
                if trip_data.get('duration_hours'):
                    hours = int(trip_data['duration_hours'])
                    minutes = int((trip_data['duration_hours'] - hours) * 60)
                    status_info += f" ({hours}ч {minutes}мин)"
            elif trip_data.get('started_at'):
                status_info = "🚀 В ПУТИ"
            else:
                status_info = "⏰ ЗАПЛАНИРОВАНА"
            
            summary = f"Рейс #{trip_data.get('waybill_number', 'N/A')} - {driver_name} [{status_info}]"
            
            description = f"""
🚛 Детали рейса (ОБНОВЛЕНО):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Водитель: {driver_name}
🚗 ТС: {trip_data.get('vehicle_number', 'N/A')}
📄 Путевой лист: {trip_data.get('waybill_number', 'N/A')}
🗺️ Маршрут: №{trip_data.get('route_number', 'N/A')} - {trip_data.get('route_name', '')}
📦 Доставлено: {trip_data.get('quantity_delivered', 0)} шт.
📅 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{status_info}

⏰ Время поездки:
🚀 Начало: {start_time.strftime('%d.%m.%Y %H:%M')}
🏁 Окончание: {end_time.strftime('%d.%m.%Y %H:%M')}
⏱ Продолжительность: {(end_time - start_time).total_seconds() / 3600:.1f}ч
            """.strip()
            
            # Выбираем цвет в зависимости от статуса
            color_id = '10'  # Зеленый для завершенных
            if not trip_data.get('completed_at'):
                if trip_data.get('started_at'):
                    color_id = '11'  # Красный для активных
                else:
                    color_id = '9'   # Синий для запланированных
            
            # Обновляем данные события
            event['summary'] = summary
            event['description'] = description
            event['start']['dateTime'] = start_time.isoformat()
            event['end']['dateTime'] = end_time.isoformat()
            event['colorId'] = color_id
            
            # Обновляем расширенные свойства
            if 'extendedProperties' not in event:
                event['extendedProperties'] = {'private': {}}
            
            event['extendedProperties']['private'].update({
                'status': 'completed' if trip_data.get('completed_at') else 'started' if trip_data.get('started_at') else 'planned',
                'updated_at': datetime.now().isoformat(),
                'duration_hours': str(trip_data.get('duration_hours', 0)),
                'real_start_time': start_time.isoformat(),
                'real_end_time': end_time.isoformat()
            })
            
            # Обновляем событие
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"✅ Событие обновлено в Google Calendar: {event_id}")
            logger.info(f"⏰ Обновленное время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({(end_time - start_time).total_seconds() / 3600:.1f}ч)")
            return True
            
        except Exception as error:
            logger.error(f"❌ Ошибка при обновлении события: {error}")
            return False
    
    def delete_trip_event(self, event_id: str) -> bool:
        """Удаление события рейса из календаря"""
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"✅ Событие удалено из Google Calendar: {event_id}")
            return True
            
        except Exception as error:
            if hasattr(error, 'resp') and error.resp.status == 404:
                logger.warning(f"⚠️ Событие не найдено для удаления: {event_id}")
                return True  # Считаем успехом, если события уже нет
            logger.error(f"❌ Ошибка при удалении события: {error}")
            return False
    
    def test_connection(self) -> bool:
        """Тестирование подключения к Google Calendar"""
        if not GOOGLE_CALENDAR_AVAILABLE:
            logger.error("Google Calendar API недоступен")
            return False
            
        if not self.authenticate():
            return False
        
        try:
            calendar = self.service.calendars().get(calendarId='primary').execute()
            calendar_name = calendar.get('summary', 'Неизвестно')
            logger.info(f"✅ Подключение к Google Calendar успешно! Календарь: {calendar_name}")
            return True
            
        except Exception as error:
            logger.error(f"❌ Ошибка подключения к Google Calendar: {error}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Получение статуса подключения"""
        if not GOOGLE_CALENDAR_AVAILABLE:
            return {
                'is_available': False,
                'is_configured': False,
                'has_credentials': False,
                'has_token': False,
                'calendar_info': None,
                'error': 'Google Calendar API недоступен. Установите зависимости: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client'
            }
        
        has_credentials = os.path.exists(self.credentials_file)
        has_token = os.path.exists(self.token_file)
        
        status = {
            'is_available': True,
            'is_configured': self.is_authenticated,
            'has_credentials': has_credentials,
            'has_token': has_token,
            'calendar_info': None,
            'error': None
        }
        
        if has_credentials and has_token:
            if self.test_connection():
                try:
                    calendar = self.service.calendars().get(calendarId='primary').execute()
                    status['calendar_info'] = {
                        'name': calendar.get('summary'),
                        'id': calendar.get('id'),
                        'timezone': calendar.get('timeZone')
                    }
                    status['is_configured'] = True
                except:
                    status['error'] = 'Ошибка получения информации о календаре'
            else:
                status['error'] = 'Не удалось подключиться к календарю'
        elif not has_credentials:
            status['error'] = 'Отсутствует файл credentials.json'
        elif not has_token:
            status['error'] = 'Требуется авторизация'
        
        return status

# Функция-обертка для интеграции в основное приложение
class CalendarIntegration:
    """Обертка для интеграции с Google Calendar в системе экспедирования"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and GOOGLE_CALENDAR_AVAILABLE
        self.calendar_manager = None
        
        if self.enabled:
            self.calendar_manager = GoogleCalendarManager()
    
    def create_trip_event_sync(self, trip_data: Dict[str, Any], user_data: Dict[str, Any]) -> Optional[str]:
        """Синхронная версия создания события"""
        if not self.enabled or not self.calendar_manager:
            logger.info("ℹ️ Google Calendar отключен, событие не создано")
            return None
        
        try:
            event_id = self.calendar_manager.create_trip_event(trip_data, user_data)
            return event_id
        except Exception as e:
            logger.error(f"❌ Ошибка создания события в календаре: {e}")
            return None
    
    def update_trip_event_sync(self, event_id: str, trip_data: Dict[str, Any], user_data: Dict[str, Any]) -> bool:
        """Синхронная версия обновления события"""
        if not self.enabled or not self.calendar_manager:
            logger.info("ℹ️ Google Calendar отключен, событие не обновлено")
            return False
        
        try:
            return self.calendar_manager.update_trip_event(event_id, trip_data, user_data)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления события в календаре: {e}")
            return False
    
    def delete_trip_event_sync(self, event_id: str) -> bool:
        """Синхронная версия удаления события"""
        if not self.enabled or not self.calendar_manager:
            logger.info("ℹ️ Google Calendar отключен, событие не удалено")
            return False
        
        try:
            return self.calendar_manager.delete_trip_event(event_id)
        except Exception as e:
            logger.error(f"❌ Ошибка удаления события в календаре: {e}")
            return False
    
    def test_connection(self) -> Dict[str, Any]:
        """Тестирование подключения"""
        if not self.enabled:
            return {
                'success': False,
                'message': 'Google Calendar интеграция отключена',
                'calendar_info': None
            }
        
        try:
            if self.calendar_manager.test_connection():
                calendar = self.calendar_manager.service.calendars().get(calendarId='primary').execute()
                return {
                    'success': True,
                    'message': 'Подключение успешно',
                    'calendar_info': {
                        'name': calendar.get('summary'),
                        'id': calendar.get('id'),
                        'timezone': calendar.get('timeZone')
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'Не удалось подключиться к календарю',
                    'calendar_info': None
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Ошибка тестирования: {str(e)}',
                'calendar_info': None
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Получение статуса подключения"""
        if not self.enabled:
            return {
                'is_available': False,
                'is_configured': False,
                'has_credentials': False,
                'has_token': False,
                'calendar_info': None,
                'error': 'Google Calendar интеграция отключена'
            }
        
        return self.calendar_manager.get_connection_status()

# Глобальная функция для получения интеграции календаря
def get_calendar_integration(enabled: bool = True) -> CalendarIntegration:
    """Получение экземпляра интеграции календаря"""
    return CalendarIntegration(enabled=enabled)

# Функция для печати инструкций по настройке
def print_setup_instructions():
    """Печать инструкций по настройке Google Calendar"""
    print("\n📋 НАСТРОЙКА GOOGLE CALENDAR:")
    print("=" * 50)
    
    if not GOOGLE_CALENDAR_AVAILABLE:
        print("1. 📦 Установите зависимости:")
        print("   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        print()
    
    print("2. 🌐 Настройка Google Cloud Console:")
    print("   • Перейдите на https://console.cloud.google.com/")
    print("   • Создайте новый проект или выберите существующий")
    print("   • Включите Google Calendar API")
    print("   • Перейдите в 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'")
    print("   • Выберите 'Desktop application'")
    print("   • Скачайте JSON файл и переименуйте в 'credentials.json'")
    print("   • Поместите файл в корневую директорию проекта")
    print()
    print("3. 🔐 Первая авторизация:")
    print("   • Запустите систему")
    print("   • В настройках нажмите 'Настроить Google Calendar'")
    print("   • Откроется браузер для авторизации")
    print("   • Разрешите доступ к календарю")
    print("=" * 50)

if __name__ == "__main__":
    # Тестирование
    print("🔧 Тестирование Google Calendar...")
    
    calendar_integration = CalendarIntegration(enabled=True)
    status = calendar_integration.get_connection_status()
    
    print(f"📊 Статус подключения:")
    print(f"   • Доступен: {'✅' if status['is_available'] else '❌'}")
    print(f"   • Настроен: {'✅' if status['is_configured'] else '❌'}")
    
    if status['error']:
        print(f"   • Ошибка: {status['error']}")
    
    if status['is_configured']:
        print("\n🧪 Создание тестового события...")
        
        test_trip_data = {
            'id': 999,
            'waybill_number': 'TEST123',
            'vehicle_number': 'TEST-001',
            'route_number': '99',
            'route_name': 'Тестовый маршрут',
            'quantity_delivered': 100,
            'duration_hours': 2.5,
            'started_at': datetime.now().isoformat()
        }
        
        test_user_data = {
            'id': 999,
            'surname': 'Тестов',
            'first_name': 'Тест',
            'middle_name': 'Тестович'
        }
        
        event_id = calendar_integration.create_trip_event_sync(test_trip_data, test_user_data)
        
        if event_id:
            print(f"✅ Тестовое событие создано: {event_id}")
        else:
            print("❌ Ошибка создания тестового события")