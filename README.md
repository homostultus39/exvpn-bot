# ExVPN Bot

Telegram-бот для продажи VPN-подписок и выдачи ключей через панели `3x-ui`.

## Что делает проект

- регистрирует пользователей Telegram и хранит их состояние в PostgreSQL;
- продает и продлевает подписки через `Telegram Stars` и `YooKassa`;
- выдает ключи для обычных регионов и для режима white-list;
- синхронизирует срок действия ключей с панелями `3x-ui`;
- автоматически снимает просроченных пользователей с панелей по расписанию;
- дает администратору интерфейс для управления кластерами, тарифами, промокодами, рассылками и обращениями.

## Реальная архитектура

Проект не использует `Central API`. Текущая архитектура выглядит так:

- [bot/main.py](/home/limpizz/Projects/exvpn-bot-1/bot/main.py) - entrypoint, миграции, сидинг, запуск polling и scheduler.
- [bot/routers](/home/limpizz/Projects/exvpn-bot-1/bot/routers) - Telegram-роутеры и пользовательские сценарии.
- [bot/routers/admin](/home/limpizz/Projects/exvpn-bot-1/bot/routers/admin) - админские сценарии и FSM-формы.
- [bot/database/models.py](/home/limpizz/Projects/exvpn-bot-1/bot/database/models.py) - SQLAlchemy-модели.
- [bot/database/management/operations](/home/limpizz/Projects/exvpn-bot-1/bot/database/management/operations) - слой операций над БД и доменной логики.
- [bot/core/xray_panel_client.py](/home/limpizz/Projects/exvpn-bot-1/bot/core/xray_panel_client.py) - адаптер к `py3xui` и панелям `3x-ui`.
- [bot/scheduler/subscription_expiry.py](/home/limpizz/Projects/exvpn-bot-1/bot/scheduler/subscription_expiry.py) - фоновая обработка истекших подписок.
- [bot/keyboards](/home/limpizz/Projects/exvpn-bot-1/bot/keyboards) - inline/reply keyboards.
- [bot/messages](/home/limpizz/Projects/exvpn-bot-1/bot/messages) - шаблоны текстов.
- [migrations](/home/limpizz/Projects/exvpn-bot-1/migrations) - Alembic-миграции.

## Основные сущности

- `UserModel` - пользователь Telegram, подписка, trial, referrer, admin flag.
- `ClusterModel` - одна панель `3x-ui`.
- `PeerModel` - выданный ключ пользователя на конкретной панели.
- `TariffModel` - тарифы и их цены.
- `PendingPaymentModel` - ожидающие платежи.
- `PromoCodeModel` и `PromoCodeUsageModel` - промокоды и их использования.
- `ReportModel` - обращения в поддержку.

## Как устроена работа с 3x-ui

Каждая панель хранится в таблице `clusters`.

Для каждой панели сохраняются:

- `public_name`
- `endpoint`
- `username`
- `encrypted_password`
- `is_whitelist_gateway`
- `region_code`

Важно: `endpoint` должен содержать полный `Access URL`, включая `WebBasePath`.

Корректный пример:

```text
https://93.177.116.96:29635/eCLrpzIQQM4MJZ1EvG
```

Некорректный пример:

```text
https://93.177.116.96:29635
```

Если у панели self-signed сертификат, включите `XRAY_SKIP_SSL_VERIFY=true`.

## Технологии

- Python 3.14
- aiogram 3
- SQLAlchemy 2 async
- PostgreSQL
- Alembic
- APScheduler
- py3xui
- YooKassa SDK

## Переменные окружения

Минимально необходимые переменные:

```env
API_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
TIMEZONE=Europe/Moscow

PASSWORD_ENCRYPTION_KEY=base64_encoded_16_byte_key
XRAY_SKIP_SSL_VERIFY=true

PRIVACY_POLICY_URL=https://example.com/privacy
USER_AGREEMENT_URL=https://example.com/agreement

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=exvpn_bot
POSTGRES_USER=bot
POSTGRES_PASSWORD=secret

YOOKASSA_SHOP_ID=shop_id
YOOKASSA_SECRET_KEY=secret_key
```

`PASSWORD_ENCRYPTION_KEY` нужен для шифрования паролей панелей в БД.

Сгенерировать ключ можно так:

```bash
python -c "from Crypto.Random import get_random_bytes; import base64; print(base64.b64encode(get_random_bytes(16)).decode())"
```

## Запуск локально

1. Установить зависимости:

```bash
poetry install
```

2. Убедиться, что PostgreSQL доступен и `.env` заполнен.

3. Запустить бота:

```bash
poetry run python -m bot.main
```

## Запуск через Docker Compose

```bash
docker compose up -d --build
```

Сервисы:

- `postgres`
- `exvpn-bot`

## Что делает scheduler

Scheduler запускается каждый час и:

- находит пользователей с истекшей подпиской;
- удаляет их клиентов с панелей `3x-ui`;
- удаляет связанные `peers` из БД;
- переводит пользователя в статус `expired`.

## Админские возможности

- управление кластерами `3x-ui`;
- регистрация клиентов вручную;
- управление тарифами;
- просмотр статистики;
- создание и удаление промокодов;
- массовые рассылки;
- обработка обращений пользователей.

## Ограничения и замечания

- тестов в репозитории пока нет;
- состояние tracked-сообщений хранится в памяти и теряется при рестарте;
- для нестабильных или self-signed панелей рекомендуется отключение TLS verify через `XRAY_SKIP_SSL_VERIFY`.

## Полезные файлы

- [bot/core/xray_panel_client.py](/home/limpizz/Projects/exvpn-bot-1/bot/core/xray_panel_client.py)
- [bot/database/management/operations/user.py](/home/limpizz/Projects/exvpn-bot-1/bot/database/management/operations/user.py)
- [bot/database/management/operations/peer.py](/home/limpizz/Projects/exvpn-bot-1/bot/database/management/operations/peer.py)
- [bot/routers/keys.py](/home/limpizz/Projects/exvpn-bot-1/bot/routers/keys.py)
- [bot/routers/subscription.py](/home/limpizz/Projects/exvpn-bot-1/bot/routers/subscription.py)
