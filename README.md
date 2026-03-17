# VK Blackjack Bot

**VK-бот** для игры в блэкджек в групповых беседах. Микросервисная архитектура на Python 3.12 + aiohttp.

---

## Архитектура

```
VK Long Poll API
      │
      ▼
  [poller] ──► RabbitMQ: vk_updates ──► [game] ──► RabbitMQ: vk_outgoing ──► [mailbox] ──► VK API
                                             │
                                          PostgreSQL
                                             │
                                         [admin] ──► REST API
```

| Сервис | Роль |
|---|---|
| **poller** | Опрашивает VK Long Poll API, публикует обновления в RabbitMQ очередь `vk_updates` |
| **game** | Потребляет `vk_updates`, выполняет логику блэкджека, публикует ответы в `vk_outgoing` |
| **mailbox** | Потребляет `vk_outgoing`, отправляет сообщения через VK API `messages.send` |
| **admin** | aiohttp REST API для администрирования (настройки, статистика) |

---

## Технологии

- **Python 3.12**, **aiohttp** — асинхронный веб-фреймворк
- **SQLAlchemy** (async) + **asyncpg** + **PostgreSQL** — база данных
- **aio-pika** + **RabbitMQ** — очередь сообщений между сервисами
- **Pydantic** — валидация схем сообщений и запросов
- **Alembic** — миграции базы данных
- **Docker Compose** — оркестрация всех сервисов
- **Ruff** — форматирование и линтинг кода
- **pytest** + **pytest-aiohttp** — тесты

---

## Структура проекта

```
kts_kp/
├── docker-compose.yml
├── .env.example
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│
├── shared/                     # Pip-пакет kts_shared, общий для всех сервисов
│   ├── base/base_accessor.py   # BaseAccessor с connect/disconnect
│   ├── db/database.py          # Database (engine + sessionmaker)
│   ├── models/
│   │   ├── admin.py            # Admin
│   │   └── game.py             # Game, Player, GamePlayer, GameRound, GameSettings
│   └── rabbit/schemas.py       # Pydantic-схемы для очередей RabbitMQ
│
├── services/
│   ├── poller/                 # VK Long Poll → RabbitMQ
│   ├── game/                   # Логика блэкджека
│   ├── mailbox/                # RabbitMQ → VK API
│   └── admin/                  # REST API для администраторов
│
└── tests/
    ├── game/                   # Тесты логики и аксессоров
    └── admin/                  # Тесты вью и аксессоров
```

---

## Быстрый старт

### Требования

- Docker и Docker Compose
- Python 3.12 (для локальной разработки)

### Запуск

1. Скопируйте конфиг и заполните значения:

```sh
cp etc/config.yaml.example etc/config.yaml
```

2. Скопируйте `.env.example` и заполните:

```sh
cp .env.example .env
```

3. Запустите все сервисы:

```sh
docker compose up --build
```

Это автоматически запустит миграции и поднимет все сервисы.

---

## Локальная разработка

### Установка зависимостей

```sh
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# или .venv\Scripts\activate.bat   # Windows

pip install -r requirements.txt
```

### Запуск только инфраструктуры

```sh
docker compose up -d postgres rabbitmq
```

### Миграции

```sh
python -m alembic upgrade head
```

### Форматирование и линтинг

```sh
ruff format
ruff check --fix
```

### Проверка (как в CI)

```sh
ruff format --check && ruff check --no-fix
```

### Тесты

```sh
pytest
```

---

## Игровой процесс

1. Пользователь пишет `/start` в беседе — открывается лобби на 10 секунд с кнопкой **[ВСТУПИТЬ]**
2. Игроки нажимают кнопку, чтобы вступить в игру
3. После таймера (минимум 2 игрока) начинается раунд:
   - Каждому и дилеру раздаётся по 2 карты (одна карта дилера скрыта)
   - Игроки по очереди выбирают **[ЕЩЁ]** или **[СТОП]**
4. После всех игроков дилер добирает карты до 17+
5. Определяются победители, обновляются балансы
6. Игра продолжается до тех пор, пока кто-то не достигнет целевого баланса или не останется один игрок

### Настройки игры (по умолчанию)

| Параметр | Значение |
|---|---|
| Начальный баланс | 100 |
| Целевой баланс | 500 |
| Ставка за раунд | 10 |

---

## Admin API

Сервис `admin` доступен на порту `8080`.

| Метод | Путь | Авторизация | Описание |
|---|---|---|---|
| POST | `/admin.login` | Нет | Вход, создание сессии |
| GET | `/admin.current` | Да | Текущий администратор |
| POST | `/admin.logout` | Да | Выход |
| GET | `/settings.list` | Да | Список настроек чатов |
| POST | `/settings.update` | Да | Обновление настроек чата |
| GET | `/stats.games` | Да | Статистика игр |
| GET | `/stats.players` | Да | Таблица лидеров |

---

## Рабочий процесс разработки

Ветки создаются по фичам согласно `PLAN.md`:

```sh
git checkout dev
git checkout -b feature/<номер>-<название>
# разработка...
ruff format && ruff check --fix
pytest
git push origin feature/<номер>-<название>
# создать Pull Request в dev
```

---

## Конфигурация

Единый файл `etc/config.yaml` для всех сервисов (не включён в git).

- **Разработка:** путь к конфигу берётся относительно `main.py` каждого сервиса
- **Docker:** конфиг монтируется через `CONFIGPATH=/srv/etc/config.yaml`

Пример конфига: `etc/config.yaml.example`
