# 🚛 Система автоматизации экспедирования

Комплексная система для управления автопарком, отслеживания рейсов и автоматизации документооборота в логистических компаниях.
<img width="1650" alt="Снимок экрана 2025-06-07 в 15 56 29" src="https://github.com/user-attachments/assets/603f3035-f591-4d84-bac5-144e9290a645" />

## 📋 Возможности

### 🌐 Веб-интерфейс
- **Панель управления** с аналитикой и статистикой
- **Управление водителями** - создание, редактирование, управление паролями
- **Управление автопарком** - добавление и настройка транспортных средств
- **Настройка маршрутов** - создание маршрутов с ценообразованием
- **Система отчетности** - Excel-отчеты, аналитика, графики
- **Управление рейсами** - мониторинг активных поездок

### 🤖 Telegram Bot
- **Авторизация водителей** через фамилию и пароль
- **Создание рейсов** с выбором ТС, маршрута и количества товара
- **Отслеживание времени** - точное время начала и окончания поездок
- **Уведомления** о статусе рейсов
- **Личная статистика** водителя

### 📅 Google Calendar интеграция
- **Автоматическое создание событий** при начале рейса
- **Обновление в реальном времени** с фактическим временем поездки
- **Цветовое кодирование** статусов рейсов
- **Подробная информация** в описании событий

## 🏗️ Архитектура

```
expedition-system/
├── main.py              # Точка входа в систему
├── database.py          # Модель данных и работа с SQLite
├── web_app.py          # FastAPI веб-приложение
├── telegram_bot.py     # Telegram Bot на aiogram
├── google_calendar.py  # Интеграция с Google Calendar API
├── templates/          # HTML шаблоны
├── static/            # CSS, JS, изображения
├── requirements.txt   # Зависимости Python
├── credentials.json   # Credentials для Google API
└── .env              # Переменные окружения
```

## 🚀 Быстрый запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/expedition-system.git
cd expedition-system
```

### 2. Установка зависимостей
```bash
# Автоматическая установка
python main.py --install

# Или вручную
pip install -r requirements.txt
```

### 3. Настройка переменных окружения
```bash
# Создание файла .env
python main.py --create-env

# Отредактируйте .env файл и добавьте:
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 4. Запуск системы
```bash
python main.py
```

После запуска:
- 🌐 **Веб-интерфейс**: http://localhost:8000
- 👤 **Логин**: admin
- 🔑 **Пароль**: admin123

## ⚙️ Настройка компонентов

### 🤖 Telegram Bot

1. Создайте бота у [@BotFather](https://t.me/BotFather)
2. Получите токен
3. Добавьте токен в `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 📅 Google Calendar

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Google Calendar API
4. Создайте OAuth 2.0 credentials (Desktop Application)
5. Скачайте файл как `credentials.json`
6. Поместите файл в корневую директорию проекта

Подробные инструкции:
```bash
python main.py --setup-calendar
```

## 📊 Функционал

### Для администраторов
- ✅ Управление водителями и паролями
- ✅ Настройка автопарка и маршрутов
- ✅ Мониторинг всех рейсов в реальном времени
- ✅ Генерация Excel-отчетов
- ✅ Аналитика и статистика
- ✅ Интеграция с Google Calendar

### Для водителей
- ✅ Простая авторизация через Telegram
- ✅ Создание рейсов за несколько кликов
- ✅ Отслеживание времени поездок
- ✅ Просмотр личной статистики
- ✅ Автоматическое добавление в календарь

## 🔧 Технологии

### Backend
- **Python 3.8+**
- **FastAPI** - современный веб-фреймворк
- **SQLite** - легкая база данных
- **aiogram 3.x** - асинхронный Telegram Bot API
- **Jinja2** - шаблонизатор

### Frontend
- **Bootstrap 5** - адаптивный UI
- **Chart.js** - графики и диаграммы
- **Font Awesome** - иконки

### Интеграции
- **Google Calendar API** - синхронизация событий
- **OpenPyXL** - генерация Excel отчетов

## 📁 Структура базы данных

```sql
-- Пользователи (водители и администраторы)
users (id, surname, first_name, middle_name, password_hash, role, telegram_id, is_active, created_at)

-- Транспортные средства
vehicles (id, number, model, capacity, is_active, created_at)

-- Маршруты с ценообразованием
routes (id, number, name, price, description, is_active, created_at)

-- Рейсы с отслеживанием времени
trips (id, user_id, vehicle_id, route_id, waybill_number, quantity_delivered, 
       trip_date, status, started_at, completed_at, calendar_event_id, created_at)
```

## 📈 Отчеты и аналитика

### Доступные отчеты
- 📊 **Сводный отчет по рейсам** - полная информация для бухгалтерии
- 👨‍💼 **Статистика по водителям** - производительность и доходы
- 🚛 **Анализ автопарка** - использование транспортных средств
- 🗺️ **Эффективность маршрутов** - доходность направлений

### Форматы экспорта
- 📄 **Excel** - совместимость с 1С и другими системами
- 📊 **JSON API** - интеграция с внешними системами

## 🔒 Безопасность

- 🔐 **Хеширование паролей** с солью (PBKDF2)
- 🎭 **Ролевая модель** (администраторы/водители)
- 🔒 **HTTP Basic Auth** для веб-интерфейса
- 🛡️ **Валидация данных** на всех уровнях

## 🌟 Расширения

### Планируемые функции
- 📱 PWA мобильное приложение
- 🗺️ GPS трекинг маршрутов
- 💰 Интеграция с 1С
- 📧 Email уведомления
- 📊 Расширенная аналитика
- 🔄 API для внешних систем

## 🤝 Участие в разработке

1. Форкните репозиторий
2. Создайте ветку для новой функции (`git checkout -b feature/AmazingFeature`)
3. Зафиксируйте изменения (`git commit -m 'Add some AmazingFeature'`)
4. Отправьте в ветку (`git push origin feature/AmazingFeature`)
5. Создайте Pull Request

## 📝 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 📞 Поддержка

При возникновении вопросов или проблем:

- 📧 **Email**: support@expedition-system.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/expedition-system/issues)
- 📖 **Wiki**: [Документация](https://github.com/yourusername/expedition-system/wiki)

## 🎯 Статус проекта

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/badge/build-passing-green.svg)

---

⭐ **Поставьте звезду если проект вам полезен!**
