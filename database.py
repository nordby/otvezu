# database.py - Исправленная схема базы данных с отслеживанием времени поездок

import sqlite3
import hashlib
import secrets
import datetime
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

# Настройка логирования
logger = logging.getLogger(__name__)

@dataclass
class User:
    id: Optional[int]
    surname: str
    first_name: str
    middle_name: str
    password_hash: str
    role: str  # 'driver' или 'admin'
    telegram_id: Optional[int]
    is_active: bool
    created_at: datetime.datetime

@dataclass
class Vehicle:
    id: Optional[int]
    number: str
    model: str
    capacity: float
    is_active: bool
    created_at: datetime.datetime

@dataclass
class Route:
    id: Optional[int]
    number: str
    name: str
    price: float
    description: str
    is_active: bool
    created_at: datetime.datetime

@dataclass
class Trip:
    id: Optional[int]
    user_id: int
    vehicle_id: int
    route_id: int
    waybill_number: str
    quantity_delivered: int
    trip_date: datetime.date
    created_at: datetime.datetime
    status: str  # 'created', 'started', 'completed', 'cancelled'
    started_at: Optional[datetime.datetime]
    completed_at: Optional[datetime.datetime]
    calendar_event_id: Optional[str]

class DatabaseManager:
    def __init__(self, db_path: str = "expedition.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация базы данных с созданием всех таблиц"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    surname TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    middle_name TEXT,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('driver', 'admin')),
                    telegram_id INTEGER UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица транспортных средств
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT UNIQUE NOT NULL,
                    model TEXT NOT NULL,
                    capacity REAL DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица маршрутов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    price REAL NOT NULL DEFAULT 0,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Обновленная таблица рейсов с отслеживанием времени
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    vehicle_id INTEGER NOT NULL,
                    route_id INTEGER NOT NULL,
                    waybill_number TEXT NOT NULL,
                    quantity_delivered INTEGER NOT NULL,
                    trip_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'created' CHECK (status IN ('created', 'started', 'completed', 'cancelled')),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    calendar_event_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
                    FOREIGN KEY (route_id) REFERENCES routes (id)
                )
            ''')
            
            # Таблица системных настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT
                )
            ''')
            
            # Создание индексов для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(trip_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)')
            
            conn.commit()
            
            # Миграция существующих данных
            self._migrate_existing_data()
            
            # Создание администратора по умолчанию
            self.create_default_admin()
    
    def _migrate_existing_data(self):
        """Миграция существующих данных для новых полей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, нужна ли миграция
            cursor.execute("PRAGMA table_info(trips)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'started_at' not in columns:
                # Добавляем новые колонки
                cursor.execute('ALTER TABLE trips ADD COLUMN started_at TIMESTAMP')
                cursor.execute('ALTER TABLE trips ADD COLUMN completed_at TIMESTAMP')
                cursor.execute('ALTER TABLE trips ADD COLUMN calendar_event_id TEXT')
                
                # Обновляем статус существующих рейсов
                cursor.execute("UPDATE trips SET status = 'completed' WHERE status != 'cancelled'")
                
                conn.commit()
                logger.info("✅ Миграция базы данных завершена")
    
    def create_default_admin(self):
        """Создание администратора по умолчанию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, есть ли уже администратор
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            
            if admin_count == 0:
                admin_password = "admin123"
                password_hash = self._hash_password(admin_password)
                
                cursor.execute('''
                    INSERT INTO users (surname, first_name, password_hash, role)
                    VALUES (?, ?, ?, ?)
                ''', ("admin", "admin", password_hash, "admin"))
                
                conn.commit()
                logger.info(f"Создан администратор по умолчанию. Логин: admin, Пароль: {admin_password}")
    
    def _hash_password(self, password: str) -> str:
        """Хеширование пароля"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return f"{salt}:{pwd_hash.hex()}"
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Проверка пароля"""
        try:
            salt, stored_hash = password_hash.split(':')
            pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return pwd_hash.hex() == stored_hash
        except:
            return False
    
    def generate_password(self) -> str:
        """Генерация случайного пароля для водителя"""
        return secrets.token_urlsafe(8)
    
    # CRUD операции для пользователей
    def create_user(self, surname: str, first_name: str, middle_name: str = "", 
                   role: str = "driver", password: str = None) -> int:
        """Создание нового пользователя"""
        if password is None:
            password = self.generate_password()
        
        password_hash = self._hash_password(password)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (surname, first_name, middle_name, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (surname, first_name, middle_name, password_hash, role))
            conn.commit()
            
            user_id = cursor.lastrowid
            logger.info(f"Создан пользователь ID: {user_id}, Пароль: {password}")
            return user_id
    
    def authenticate_user(self, surname: str, password: str) -> Optional[User]:
        """Аутентификация пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users WHERE surname = ? AND is_active = 1
            ''', (surname,))
            
            row = cursor.fetchone()
            if row and self.verify_password(password, row['password_hash']):
                return User(
                    id=row['id'],
                    surname=row['surname'],
                    first_name=row['first_name'],
                    middle_name=row['middle_name'] or "",
                    password_hash=row['password_hash'],
                    role=row['role'],
                    telegram_id=row['telegram_id'],
                    is_active=row['is_active'],
                    created_at=datetime.datetime.fromisoformat(row['created_at'])
                )
            return None
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users WHERE telegram_id = ? AND is_active = 1
            ''', (telegram_id,))
            
            row = cursor.fetchone()
            if row:
                return User(
                    id=row['id'],
                    surname=row['surname'],
                    first_name=row['first_name'],
                    middle_name=row['middle_name'] or "",
                    password_hash=row['password_hash'],
                    role=row['role'],
                    telegram_id=row['telegram_id'],
                    is_active=row['is_active'],
                    created_at=datetime.datetime.fromisoformat(row['created_at'])
                )
            return None
    
    def link_telegram_user(self, user_id: int, telegram_id: int):
        """Привязка Telegram ID к пользователю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET telegram_id = ? WHERE id = ?
            ''', (telegram_id, user_id))
            conn.commit()
    
    def get_all_users(self) -> List[User]:
        """Получение всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY surname, first_name')
            
            users = []
            for row in cursor.fetchall():
                users.append(User(
                    id=row['id'],
                    surname=row['surname'],
                    first_name=row['first_name'],
                    middle_name=row['middle_name'] or "",
                    password_hash=row['password_hash'],
                    role=row['role'],
                    telegram_id=row['telegram_id'],
                    is_active=row['is_active'],
                    created_at=datetime.datetime.fromisoformat(row['created_at'])
                ))
            return users
    
    # CRUD операции для транспортных средств
    def create_vehicle(self, number: str, model: str, capacity: float = 0) -> int:
        """Создание нового ТС"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vehicles (number, model, capacity)
                VALUES (?, ?, ?)
            ''', (number, model, capacity))
            conn.commit()
            return cursor.lastrowid
    
    def get_active_vehicles(self) -> List[Vehicle]:
        """Получение активных ТС"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicles WHERE is_active = 1 ORDER BY number')
            
            vehicles = []
            for row in cursor.fetchall():
                vehicles.append(Vehicle(
                    id=row['id'],
                    number=row['number'],
                    model=row['model'],
                    capacity=row['capacity'],
                    is_active=row['is_active'],
                    created_at=datetime.datetime.fromisoformat(row['created_at'])
                ))
            return vehicles
    
    # CRUD операции для маршрутов
    def create_route(self, number: str, name: str, price: float, description: str = "") -> int:
        """Создание нового маршрута"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO routes (number, name, price, description)
                VALUES (?, ?, ?, ?)
            ''', (number, name, price, description))
            conn.commit()
            return cursor.lastrowid
    
    def get_active_routes(self, include_price: bool = False) -> List[Route]:
        """Получение активных маршрутов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM routes WHERE is_active = 1 ORDER BY number')
            
            routes = []
            for row in cursor.fetchall():
                route = Route(
                    id=row['id'],
                    number=row['number'],
                    name=row['name'],
                    price=row['price'] if include_price else 0,
                    description=row['description'] or "",
                    is_active=row['is_active'],
                    created_at=datetime.datetime.fromisoformat(row['created_at'])
                )
                routes.append(route)
            return routes
    
    def get_route_price(self, route_id: int) -> float:
        """Получение цены маршрута"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT price FROM routes WHERE id = ?', (route_id,))
            row = cursor.fetchone()
            return row['price'] if row else 0
    
    # Обновленные CRUD операции для рейсов
    def create_trip(self, user_id: int, vehicle_id: int, route_id: int, 
                   waybill_number: str, quantity_delivered: int, 
                   trip_date: datetime.date = None) -> int:
        """Создание нового рейса"""
        if trip_date is None:
            trip_date = datetime.date.today()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trips (user_id, vehicle_id, route_id, waybill_number, 
                                 quantity_delivered, trip_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'created')
            ''', (user_id, vehicle_id, route_id, waybill_number, quantity_delivered, trip_date))
            conn.commit()
            return cursor.lastrowid
    
    def start_trip(self, trip_id: int, calendar_event_id: str = None) -> bool:
        """Начало поездки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trips 
                SET status = 'started', started_at = CURRENT_TIMESTAMP, calendar_event_id = ?
                WHERE id = ? AND status = 'created'
            ''', (calendar_event_id, trip_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def complete_trip(self, trip_id: int) -> bool:
        """Завершение поездки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trips 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'started'
            ''', (trip_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def cancel_trip(self, trip_id: int) -> bool:
        """Отмена рейса"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trips 
                SET status = 'cancelled'
                WHERE id = ? AND status IN ('created', 'started')
            ''', (trip_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_user_active_trip(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение активного рейса пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, u.surname, u.first_name, v.number as vehicle_number, 
                       r.number as route_number, r.name as route_name
                FROM trips t
                JOIN users u ON t.user_id = u.id
                JOIN vehicles v ON t.vehicle_id = v.id
                JOIN routes r ON t.route_id = r.id
                WHERE t.user_id = ? AND t.status IN ('created', 'started')
                ORDER BY t.created_at DESC
                LIMIT 1
            ''', (user_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_trips_for_report(self, start_date: datetime.date = None, 
                           end_date: datetime.date = None, 
                           status: str = None,
                           user_id: int = None,
                           vehicle_id: int = None,
                           route_id: int = None) -> List[Dict[str, Any]]:
        """Получение рейсов для отчета с фильтрами"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    t.id,
                    t.trip_date,
                    t.waybill_number,
                    t.quantity_delivered,
                    t.status,
                    t.started_at,
                    t.completed_at,
                    u.surname,
                    u.first_name,
                    u.middle_name,
                    v.number as vehicle_number,
                    v.model as vehicle_model,
                    r.number as route_number,
                    r.name as route_name,
                    r.price as route_price,
                    CASE 
                        WHEN t.started_at IS NOT NULL AND t.completed_at IS NOT NULL 
                        THEN (julianday(t.completed_at) - julianday(t.started_at)) * 24 
                        ELSE NULL 
                    END as trip_duration_hours
                FROM trips t
                JOIN users u ON t.user_id = u.id
                JOIN vehicles v ON t.vehicle_id = v.id
                JOIN routes r ON t.route_id = r.id
                WHERE 1=1
            '''
            
            params = []
            
            if start_date:
                query += ' AND t.trip_date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND t.trip_date <= ?'
                params.append(end_date)
            if status:
                query += ' AND t.status = ?'
                params.append(status)
            if user_id:
                query += ' AND t.user_id = ?'
                params.append(user_id)
            if vehicle_id:
                query += ' AND t.vehicle_id = ?'
                params.append(vehicle_id)
            if route_id:
                query += ' AND t.route_id = ?'
                params.append(route_id)
                
            query += ' ORDER BY t.trip_date DESC, t.id'
            
            cursor.execute(query, params)
            
            trips = []
            for row in cursor.fetchall():
                full_name = f"{row['surname']} {row['first_name']}"
                if row['middle_name']:
                    full_name += f" {row['middle_name']}"
                
                trips.append({
                    'id': row['id'],
                    'date': row['trip_date'],
                    'service_description': f"Услуги грузоперевозки, маршрут №{row['route_number']}",
                    'driver_name': full_name,
                    'rate': row['route_price'],
                    'vat_status': 'Без НДС',
                    'total_amount': row['route_price'],
                    'waybill_number': row['waybill_number'],
                    'quantity': row['quantity_delivered'],
                    'vehicle_number': row['vehicle_number'],
                    'vehicle_model': row['vehicle_model'],
                    'route_name': row['route_name'],
                    'status': row['status'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at'],
                    'duration_hours': round(row['trip_duration_hours'], 2) if row['trip_duration_hours'] else None
                })
            
            return trips
    
    # Методы для аналитики и отчетов
    def get_driver_statistics(self, start_date: datetime.date = None, end_date: datetime.date = None) -> List[Dict[str, Any]]:
        """Статистика по водителям"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    u.id,
                    u.surname,
                    u.first_name,
                    u.middle_name,
                    COUNT(t.id) as total_trips,
                    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_trips,
                    COUNT(CASE WHEN t.status = 'cancelled' THEN 1 END) as cancelled_trips,
                    SUM(CASE WHEN t.status = 'completed' THEN r.price ELSE 0 END) as total_revenue,
                    SUM(t.quantity_delivered) as total_quantity,
                    AVG(CASE 
                        WHEN t.started_at IS NOT NULL AND t.completed_at IS NOT NULL 
                        THEN (julianday(t.completed_at) - julianday(t.started_at)) * 24 
                        ELSE NULL 
                    END) as avg_trip_duration_hours
                FROM users u
                LEFT JOIN trips t ON u.id = t.user_id
                LEFT JOIN routes r ON t.route_id = r.id
                WHERE u.role = 'driver' AND u.is_active = 1
            '''
            
            params = []
            if start_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date >= ?)'
                params.append(start_date)
            if end_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date <= ?)'
                params.append(end_date)
            
            query += ' GROUP BY u.id ORDER BY total_revenue DESC'
            
            cursor.execute(query, params)
            
            stats = []
            for row in cursor.fetchall():
                full_name = f"{row['surname']} {row['first_name']}"
                if row['middle_name']:
                    full_name += f" {row['middle_name']}"
                
                stats.append({
                    'driver_id': row['id'],
                    'driver_name': full_name,
                    'total_trips': row['total_trips'] or 0,
                    'completed_trips': row['completed_trips'] or 0,
                    'cancelled_trips': row['cancelled_trips'] or 0,
                    'total_revenue': row['total_revenue'] or 0,
                    'total_quantity': row['total_quantity'] or 0,
                    'avg_duration_hours': round(row['avg_trip_duration_hours'], 2) if row['avg_trip_duration_hours'] else 0,
                    'completion_rate': round((row['completed_trips'] or 0) / max(row['total_trips'] or 1, 1) * 100, 1)
                })
            
            return stats
    
    def get_vehicle_statistics(self, start_date: datetime.date = None, end_date: datetime.date = None) -> List[Dict[str, Any]]:
        """Статистика по ТС"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    v.id,
                    v.number,
                    v.model,
                    COUNT(t.id) as total_trips,
                    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_trips,
                    SUM(CASE WHEN t.status = 'completed' THEN r.price ELSE 0 END) as total_revenue,
                    SUM(t.quantity_delivered) as total_quantity,
                    AVG(CASE 
                        WHEN t.started_at IS NOT NULL AND t.completed_at IS NOT NULL 
                        THEN (julianday(t.completed_at) - julianday(t.started_at)) * 24 
                        ELSE NULL 
                    END) as avg_trip_duration_hours
                FROM vehicles v
                LEFT JOIN trips t ON v.id = t.vehicle_id
                LEFT JOIN routes r ON t.route_id = r.id
                WHERE v.is_active = 1
            '''
            
            params = []
            if start_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date >= ?)'
                params.append(start_date)
            if end_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date <= ?)'
                params.append(end_date)
            
            query += ' GROUP BY v.id ORDER BY total_revenue DESC'
            
            cursor.execute(query, params)
            
            stats = []
            for row in cursor.fetchall():
                stats.append({
                    'vehicle_id': row['id'],
                    'vehicle_number': row['number'],
                    'vehicle_model': row['model'],
                    'total_trips': row['total_trips'] or 0,
                    'completed_trips': row['completed_trips'] or 0,
                    'total_revenue': row['total_revenue'] or 0,
                    'total_quantity': row['total_quantity'] or 0,
                    'avg_duration_hours': round(row['avg_trip_duration_hours'], 2) if row['avg_trip_duration_hours'] else 0
                })
            
            return stats
    
    def get_route_statistics(self, start_date: datetime.date = None, end_date: datetime.date = None) -> List[Dict[str, Any]]:
        """Статистика по маршрутам"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    r.id,
                    r.number,
                    r.name,
                    r.price,
                    COUNT(t.id) as total_trips,
                    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_trips,
                    SUM(CASE WHEN t.status = 'completed' THEN r.price ELSE 0 END) as total_revenue,
                    SUM(t.quantity_delivered) as total_quantity,
                    AVG(CASE 
                        WHEN t.started_at IS NOT NULL AND t.completed_at IS NOT NULL 
                        THEN (julianday(t.completed_at) - julianday(t.started_at)) * 24 
                        ELSE NULL 
                    END) as avg_trip_duration_hours
                FROM routes r
                LEFT JOIN trips t ON r.id = t.route_id
                WHERE r.is_active = 1
            '''
            
            params = []
            if start_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date >= ?)'
                params.append(start_date)
            if end_date:
                query += ' AND (t.trip_date IS NULL OR t.trip_date <= ?)'
                params.append(end_date)
            
            query += ' GROUP BY r.id ORDER BY total_revenue DESC'
            
            cursor.execute(query, params)
            
            stats = []
            for row in cursor.fetchall():
                stats.append({
                    'route_id': row['id'],
                    'route_number': row['number'],
                    'route_name': row['name'],
                    'route_price': row['price'],
                    'total_trips': row['total_trips'] or 0,
                    'completed_trips': row['completed_trips'] or 0,
                    'total_revenue': row['total_revenue'] or 0,
                    'total_quantity': row['total_quantity'] or 0,
                    'avg_duration_hours': round(row['avg_trip_duration_hours'], 2) if row['avg_trip_duration_hours'] else 0
                })
            
            return stats

    def reset_user_password(self, user_id: int) -> Optional[str]:
        """Сброс пароля пользователя на новый случайный"""
        try:
            new_password = self.generate_password()
            password_hash = self._hash_password(new_password)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET password_hash = ? WHERE id = ? AND role = 'driver'
                ''', (password_hash, user_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Пароль пользователя ID: {user_id} сброшен")
                    return new_password
                else:
                    logger.warning(f"Пользователь ID: {user_id} не найден или не является водителем")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка сброса пароля пользователя {user_id}: {e}")
            return None
    
    def change_user_password(self, user_id: int, new_password: str) -> bool:
        """Изменение пароля пользователя на указанный"""
        try:
            # Валидация пароля
            if len(new_password) < 6:
                logger.warning("Пароль должен содержать минимум 6 символов")
                return False
            
            password_hash = self._hash_password(new_password)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET password_hash = ? WHERE id = ? AND role = 'driver'
                ''', (password_hash, user_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Пароль пользователя ID: {user_id} изменен")
                    return True
                else:
                    logger.warning(f"Пользователь ID: {user_id} не найден или не является водителем")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка изменения пароля пользователя {user_id}: {e}")
            return False
    
    def delete_user(self, user_id: int, force: bool = False) -> tuple[bool, str]:
        """
        Удаление пользователя
        
        Args:
            user_id: ID пользователя
            force: Принудительное удаление (игнорировать связанные рейсы)
            
        Returns:
            tuple: (успех, сообщение)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, что пользователь существует и не является администратором
                cursor.execute('SELECT role, surname, first_name FROM users WHERE id = ?', (user_id,))
                user_row = cursor.fetchone()
                
                if not user_row:
                    return False, "Пользователь не найден"
                
                if user_row['role'] == 'admin':
                    return False, "Нельзя удалить администратора"
                
                # Проверяем связанные рейсы
                cursor.execute('SELECT COUNT(*) FROM trips WHERE user_id = ?', (user_id,))
                trips_count = cursor.fetchone()[0]
                
                if trips_count > 0 and not force:
                    return False, f"У пользователя есть {trips_count} рейсов. Используйте принудительное удаление или сначала удалите рейсы."
                
                # Если принудительное удаление, удаляем связанные рейсы
                if force and trips_count > 0:
                    cursor.execute('DELETE FROM trips WHERE user_id = ?', (user_id,))
                    logger.info(f"Удалено {trips_count} рейсов пользователя {user_id}")
                
                # Удаляем пользователя
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    user_name = f"{user_row['surname']} {user_row['first_name']}"
                    logger.info(f"Пользователь {user_name} (ID: {user_id}) удален")
                    return True, f"Пользователь {user_name} успешно удален"
                else:
                    return False, "Ошибка удаления пользователя"
                
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
            return False, f"Ошибка удаления: {str(e)}"
    
    def delete_vehicle(self, vehicle_id: int, force: bool = False) -> tuple[bool, str]:
        """
        Удаление транспортного средства
        
        Args:
            vehicle_id: ID ТС
            force: Принудительное удаление (игнорировать связанные рейсы)
            
        Returns:
            tuple: (успех, сообщение)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, что ТС существует
                cursor.execute('SELECT number, model FROM vehicles WHERE id = ?', (vehicle_id,))
                vehicle_row = cursor.fetchone()
                
                if not vehicle_row:
                    return False, "Транспортное средство не найдено"
                
                # Проверяем связанные рейсы
                cursor.execute('SELECT COUNT(*) FROM trips WHERE vehicle_id = ?', (vehicle_id,))
                trips_count = cursor.fetchone()[0]
                
                if trips_count > 0 and not force:
                    return False, f"У ТС есть {trips_count} рейсов. Используйте принудительное удаление или сначала удалите рейсы."
                
                # Если принудительное удаление, удаляем связанные рейсы
                if force and trips_count > 0:
                    cursor.execute('DELETE FROM trips WHERE vehicle_id = ?', (vehicle_id,))
                    logger.info(f"Удалено {trips_count} рейсов ТС {vehicle_id}")
                
                # Удаляем ТС
                cursor.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    vehicle_name = f"{vehicle_row['number']} ({vehicle_row['model']})"
                    logger.info(f"ТС {vehicle_name} (ID: {vehicle_id}) удалено")
                    return True, f"ТС {vehicle_name} успешно удалено"
                else:
                    return False, "Ошибка удаления ТС"
                
        except Exception as e:
            logger.error(f"Ошибка удаления ТС {vehicle_id}: {e}")
            return False, f"Ошибка удаления: {str(e)}"
    
    def delete_route(self, route_id: int, force: bool = False) -> tuple[bool, str]:
        """
        Удаление маршрута
        
        Args:
            route_id: ID маршрута
            force: Принудительное удаление (игнорировать связанные рейсы)
            
        Returns:
            tuple: (успех, сообщение)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, что маршрут существует
                cursor.execute('SELECT number, name FROM routes WHERE id = ?', (route_id,))
                route_row = cursor.fetchone()
                
                if not route_row:
                    return False, "Маршрут не найден"
                
                # Проверяем связанные рейсы
                cursor.execute('SELECT COUNT(*) FROM trips WHERE route_id = ?', (route_id,))
                trips_count = cursor.fetchone()[0]
                
                if trips_count > 0 and not force:
                    return False, f"У маршрута есть {trips_count} рейсов. Используйте принудительное удаление или сначала удалите рейсы."
                
                # Если принудительное удаление, удаляем связанные рейсы
                if force and trips_count > 0:
                    cursor.execute('DELETE FROM trips WHERE route_id = ?', (route_id,))
                    logger.info(f"Удалено {trips_count} рейсов маршрута {route_id}")
                
                # Удаляем маршрут
                cursor.execute('DELETE FROM routes WHERE id = ?', (route_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    route_name = f"№{route_row['number']} - {route_row['name']}"
                    logger.info(f"Маршрут {route_name} (ID: {route_id}) удален")
                    return True, f"Маршрут {route_name} успешно удален"
                else:
                    return False, "Ошибка удаления маршрута"
                
        except Exception as e:
            logger.error(f"Ошибка удаления маршрута {route_id}: {e}")
            return False, f"Ошибка удаления: {str(e)}"
    
    def delete_trip(self, trip_id: int, cancel_calendar_event: bool = True) -> tuple[bool, str]:
        """
        Удаление рейса
        
        Args:
            trip_id: ID рейса
            cancel_calendar_event: Отменить событие в календаре
            
        Returns:
            tuple: (успех, сообщение)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем информацию о рейсе
                cursor.execute('''
                    SELECT t.*, u.surname, u.first_name, v.number as vehicle_number, r.number as route_number
                    FROM trips t
                    JOIN users u ON t.user_id = u.id
                    JOIN vehicles v ON t.vehicle_id = v.id
                    JOIN routes r ON t.route_id = r.id
                    WHERE t.id = ?
                ''', (trip_id,))
                
                trip_row = cursor.fetchone()
                
                if not trip_row:
                    return False, "Рейс не найден"
                
                # Если рейс активен (started), предупреждаем
                if trip_row['status'] == 'started':
                    return False, "Нельзя удалить активный рейс. Сначала завершите или отмените его."
                
                calendar_event_id = trip_row['calendar_event_id']
                
                # Удаляем рейс
                cursor.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    # Пытаемся удалить событие из календаря
                    if calendar_event_id and cancel_calendar_event:
                        try:
                            from google_calendar import CalendarIntegration
                            calendar_integration = CalendarIntegration(enabled=True)
                            if calendar_integration.enabled:
                                calendar_integration.delete_trip_event_sync(calendar_event_id)
                                logger.info(f"Событие календаря {calendar_event_id} удалено")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить событие календаря {calendar_event_id}: {e}")
                    
                    trip_info = f"#{trip_row['waybill_number']} ({trip_row['surname']} {trip_row['first_name']})"
                    logger.info(f"Рейс {trip_info} (ID: {trip_id}) удален")
                    return True, f"Рейс {trip_info} успешно удален"
                else:
                    return False, "Ошибка удаления рейса"
                
        except Exception as e:
            logger.error(f"Ошибка удаления рейса {trip_id}: {e}")
            return False, f"Ошибка удаления: {str(e)}"
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение подробной информации о пользователе"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Основная информация о пользователе
                cursor.execute('''
                    SELECT id, surname, first_name, middle_name, role, telegram_id, 
                           is_active, created_at
                    FROM users WHERE id = ?
                ''', (user_id,))
                
                user_row = cursor.fetchone()
                if not user_row:
                    return None
                
                # Статистика рейсов
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_trips,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                        COUNT(CASE WHEN status = 'started' THEN 1 END) as active_trips,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_trips,
                        MAX(trip_date) as last_trip_date
                    FROM trips WHERE user_id = ?
                ''', (user_id,))
                
                stats_row = cursor.fetchone()
                
                return {
                    'id': user_row['id'],
                    'full_name': f"{user_row['surname']} {user_row['first_name']} {user_row['middle_name'] or ''}".strip(),
                    'surname': user_row['surname'],
                    'first_name': user_row['first_name'],
                    'middle_name': user_row['middle_name'] or '',
                    'role': user_row['role'],
                    'telegram_id': user_row['telegram_id'],
                    'is_active': bool(user_row['is_active']),
                    'created_at': user_row['created_at'],
                    'total_trips': stats_row['total_trips'],
                    'completed_trips': stats_row['completed_trips'],
                    'active_trips': stats_row['active_trips'],
                    'cancelled_trips': stats_row['cancelled_trips'],
                    'last_trip_date': stats_row['last_trip_date'],
                    'has_telegram': bool(user_row['telegram_id'])
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
            return None        

# Инициализация базы данных
if __name__ == "__main__":
    db = DatabaseManager()
    print("База данных инициализирована успешно!")
    
    # Создание тестовых данных
    print("\nСоздание тестовых данных...")
    
    # Создание водителей
    driver1_id = db.create_user("Иванов", "Иван", "Иванович", "driver")
    driver2_id = db.create_user("Петров", "Петр", "Петрович", "driver")
    
    # Создание ТС
    vehicle1_id = db.create_vehicle("9745", "ГАЗель Next", 1.5)
    vehicle2_id = db.create_vehicle("8621", "Ford Transit", 2.0)
    
    # Создание маршрутов
    route1_id = db.create_route("13", "Маршрут №13", 2500.0, "Центральный район")
    route2_id = db.create_route("7", "Маршрут №7", 3200.0, "Промышленная зона")
    
    # Создание тестовых рейсов
    trip1_id = db.create_trip(
        user_id=driver1_id,
        vehicle_id=vehicle1_id,
        route_id=route1_id,
        waybill_number="19036101",
        quantity_delivered=1558
    )
    
    trip2_id = db.create_trip(
        user_id=driver2_id,
        vehicle_id=vehicle2_id,
        route_id=route2_id,
        waybill_number="19036102",
        quantity_delivered=2340
    )
    
    print("Тестовые данные созданы успешно!")
    
    # Тест получения отчета
    print("\nТест генерации отчета:")
    trips = db.get_trips_for_report()
    for trip in trips:
        print(f"- {trip['date']}: {trip['driver_name']} - {trip['service_description']} - {trip['total_amount']} руб.")
    
    # Тест статистики
    print("\nТест статистики по водителям:")
    driver_stats = db.get_driver_statistics()
    for stat in driver_stats:
        print(f"- {stat['driver_name']}: {stat['total_trips']} рейсов, {stat['total_revenue']} руб.")