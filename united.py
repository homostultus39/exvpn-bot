import os
import json
import logging
import datetime
import uuid
import asyncio
import tempfile
import sys
import re
import urllib3
import requests
import time
import hashlib
import aiohttp
import uuid as uuidlib
from yookassa import Configuration, Payment
from aiohttp import web
from aiogram.types import WebAppInfo
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.utils.markdown import hcode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# === py3xui ===
from py3xui import Api, Client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
API_TOKEN = "7118899005:AAETG-Z__d4HdUMThgyXhQWEu9fvgZmh9GY"
ADMIN_ID = "5610309045"
PROVIDER_TOKEN = "390540012:LIVE:66312"

# === RUKASSA НАСТРОЙКИ ===
RUKASSA_API_KEY = "1e3983cd8782700e4aac689dfd37d2e9"
RUKASSA_SHOP_ID = "3449"  # Получите в личном кабинете Rukassa
RUKASSA_API_URL = "https://lk.rukassa.pro/api/v1"
RUKASSA_WEBHOOK_URL = "https://payment.exvpn.info/rukassa/webhook"  # Ваш webhook URL

YOOKASSA_SHOP_ID = "1041838"        # ID магазина из личного кабинета
YOOKASSA_SECRET_KEY = "live_e6Cyyt9mg7-QeWL-aeXohBEgdjhfN-mcIMvWyHwR13M"

PRIVACY_POLICY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-PO-RABOTE-S-PERSONALNYMI-DANNYMI-POLZOVATELEJ-03-30"
USER_AGREEMENT_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-Publichnaya-oferta-12-13-3"

TEMP_DIR = tempfile.gettempdir()
PID_FILE = os.path.join(TEMP_DIR, "exvpn-bot.pid")

# === INFERNO VPS API CONFIG ===
VPS_API_BASE = "https://cp.inferno.name/api_client.php"
VPS_CID = "153134"
VPS_API_KEY = "VQ8qtoKnUGihSmiiD64t87iB"

# === FSM ===
class Form(StatesGroup):
    waiting_for_tgid = State()
    waiting_for_days = State()
    waiting_for_server = State()
    waiting_for_broadcast = State()
    waiting_for_sni = State()
    waiting_for_shortid = State()
    waiting_for_tgid_check = State()
    
    # === ПРОМОКОДЫ: АДМИНКА ===
    waiting_for_promo_code = State()
    waiting_for_promo_days = State()
    waiting_for_promo_uses = State()
    waiting_for_promo_date = State()
    waiting_for_promo_delete = State()

    # === ВВОД ПРОМОКОДА: ПОЛЬЗОВАТЕЛЬ + АДМИН ===
    waiting_for_promo_input = State()

# === JSON УТИЛИТЫ ===
def load_users_data():
    logger.info("Загрузка users_data.json")
    try:
        if os.path.exists("users_data.json") and os.path.getsize("users_data.json") > 0:
            with open("users_data.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                data['users'] = set(data.get('users', []))
                data['referrals'] = data.get('referrals', {})
                logger.info(f"users_data.json загружен: {len(data['users'])} пользователей")
                return data
        logger.warning("users_data.json пуст или не существует — создаём новый")
        return {'users': set(), 'referrals': {}}
    except Exception as e:
        logger.error(f"load_users_data error: {e}")
        return {'users': set(), 'referrals': {}}

def save_users_data(data):
    logger.info("Сохранение users_data.json")
    try:
        data_copy = data.copy()
        data_copy['users'] = list(data_copy['users'])
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=4)
            tmp = f.name
        os.replace(tmp, "users_data.json")
        logger.info("users_data.json сохранён")
    except Exception as e:
        logger.error(f"save_users_data error: {e}")

def load_user_data():
    logger.info("Загрузка user_data.json")
    try:
        if os.path.exists("user_data.json") and os.path.getsize("user_data.json") > 0:
            with open("user_data.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                for uid in data:
                    user = data[uid]
                    if "vless_link" in user:
                        user["vless_links"] = {"n": user.pop("vless_link"), "g": ""}
                        user["tariff"] = "dual_server"
                    user.setdefault("vless_links", {"n": "", "g": ""})
                    user.setdefault("tariff", "dual_server")
                    user.setdefault("referrer", None)
                logger.info(f"user_data.json загружен: {len(data)} пользователей")
                return data
        logger.warning("user_data.json пуст или не существует — создаём новый")
        return {}
    except Exception as e:
        logger.error(f"load_user_data error: {e}")
        return {}

def save_user_data(data):
    logger.info("Сохранение user_data.json (через save_json)")
    save_json("user_data.json", data)

def has_user_agreed(user_id: int) -> bool:
    """
    Проверяет, согласился ли пользователь с условиями
    """
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        return False
    return user_data[user_id_str].get("agreed_to_terms", False)

def set_user_agreement(user_id: int):
    """
    Отмечает, что пользователь согласился с условиями
    """
    user_id_str = str(user_id)
    user_data.setdefault(user_id_str, {
        "vless_links": {"n": "", "g": "", "u": ""}, 
        "tariff": "dual_server", 
        "referrer": None
    })
    user_data[user_id_str]["agreed_to_terms"] = True
    user_data[user_id_str]["agreement_date"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_user_data(user_data)
    logger.info(f"[AGREEMENT] Пользователь {user_id} принял условия")

def get_agreement_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для соглашения с условиями
    """
    buttons = [
        [InlineKeyboardButton(
            text="📋 Политика конфиденциальности",
            url=PRIVACY_POLICY_URL
        )],
        [InlineKeyboardButton(
            text="📄 Пользовательское соглашение",
            url=USER_AGREEMENT_URL
        )],
        [InlineKeyboardButton(
            text="✅ Согласен",
            callback_data="agree_to_terms"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_rukassa_sign(shop_id: str, amount: float, order_id: str, api_key: str) -> str:
    """
    Генерация подписи для Rukassa
    """
    sign_string = f"{shop_id}:{amount}:{order_id}:{api_key}"
    return hashlib.md5(sign_string.encode()).hexdigest()

async def create_rukassa_payment(user_id: int, amount: float, days: int) -> dict:
    """
    Создание платежа через Rukassa API
    """
    order_id = f"vpn_{user_id}_{int(time.time())}"
    
    # Данные для отправки
    data = {
        'shop_id': int(RUKASSA_SHOP_ID),
        'order_id': order_id,
        'amount': int(amount),
        'token': RUKASSA_API_KEY,
        'data': json.dumps({"user_id": user_id, "days": days}),
        'user_code': str(user_id),  # ← ДОБАВИЛИ user_code (Telegram ID)
    }
    
    logger.info(f"[RUKASSA] Создание платежа: {order_id}, сумма: {amount}₽, user: {user_id}")
    logger.info(f"[RUKASSA] Payload (без токена): {dict((k, v) for k, v in data.items() if k != 'token')}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{RUKASSA_API_URL}/create",
                data=data,  # form-data
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_text = await response.text()
                logger.info(f"[RUKASSA] Ответ (статус {response.status}): {response_text[:500]}")
                
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"[RUKASSA] JSON ошибка: {e}")
                    return {"success": False, "error": f"Invalid response: {response_text[:200]}"}
                
                # Проверяем ошибку
                if 'error' in result:
                    logger.error(f"[RUKASSA] Ошибка API: {result}")
                    return {"success": False, "error": result.get('message', 'Unknown error')}
                
                # Успех
                if 'url' in result:
                    logger.info(f"[RUKASSA] Платеж создан успешно! URL: {result['url']}")
                    return {
                        "success": True,
                        "url": result['url'],
                        "order_id": order_id,
                        "payment_id": result.get('id'),
                        "hash": result.get('hash')
                    }
                else:
                    logger.error(f"[RUKASSA] Нет URL в ответе: {result}")
                    return {"success": False, "error": "No payment URL"}
                    
    except Exception as e:
        logger.error(f"[RUKASSA] Исключение: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def check_rukassa_payment(order_id: str) -> dict:
    """
    Проверка статуса платежа
    """
    
    payload = {
        "shop_id": RUKASSA_SHOP_ID,
        "order_id": order_id
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{RUKASSA_API_URL}/check",
                data=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                result = await response.json()
                logger.info(f"[RUKASSA] Проверка платежа {order_id}: {result}")
                return result
                
    except Exception as e:
        logger.error(f"[RUKASSA] Ошибка проверки платежа: {e}")
        return {"status": "error", "message": str(e)}

def get_tariffs_keyboard(is_extension: bool = False) -> InlineKeyboardMarkup:
    prefix = "extend_" if is_extension else "buy_"
    tariffs = {
        "30": {"days": 30, "stars": 48, "rub": 90},
        "90": {"days": 90, "stars": 136, "rub": 256},
        "180": {"days": 180, "stars": 266, "rub": 502},
        "360": {"days": 360, "stars": 515, "rub": 972},
    }
    buttons = [
        [InlineKeyboardButton(
            text=f"1 месяц ({tariffs['30']['stars']} ⭐ / {tariffs['30']['rub']} RUB)",
            callback_data=f"{prefix}30"
        )],
        [InlineKeyboardButton(
            text=f"3 месяца ({tariffs['90']['stars']} ⭐ / {tariffs['90']['rub']} RUB)",
            callback_data=f"{prefix}90"
        )],
        [InlineKeyboardButton(
            text=f"6 месяцев ({tariffs['180']['stars']} ⭐ / {tariffs['180']['rub']} RUB)",
            callback_data=f"{prefix}180"
        )],
        [InlineKeyboardButton(
            text=f"12 месяцев ({tariffs['360']['stars']} ⭐ / {tariffs['360']['rub']} RUB)",
            callback_data=f"{prefix}360"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_initial" if not is_extension else "back_to_my_vpn"
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def save_json(filename, data):
    logger.info(f"Сохранение {filename}")
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            tmp = f.name
        os.replace(tmp, filename)
        logger.info(f"{filename} сохранён")
    except Exception as e:
        logger.error(f"save_json error: {e}")

users_data = load_users_data()
def register_user_for_broadcast(user_id: int):
    uid = str(user_id)
    users_data['users'].add(uid)
    save_users_data(users_data)
async def send_newyear_welcome(message: types.Message, user_id: int):
    text = (
        "╔═══════════════════════╗\n"
        "              🎄 ❄️  ExVPN  ❄️  🎄\n"
        "╚═══════════════════════╝\n\n"
        "🎅 С наступающим Новым 2026 годом! 🎆\n\n"
        "✨ Ваш надёжный VPN-сервис ✨\n\n"
        "🌍 Доступные локации:\n"
        "  🇳🇱 Нидерланды\n"
        "  🇩🇪 Германия\n"
        "  🇺🇸 США\n\n"
        "⚡️ Преимущества:\n"
        "  🔥 VLESS Reality + Vision\n"
        "  🛡 Защита от блокировок\n"
        "  🚀 Высокая скорость\n"
        "  💎 Стабильное соединение\n"
        "  💬 Поддержка 24/7\n\n"
        "🎄 Выберите действие ниже: 👇"
    )

    kb = get_initial_keyboard(str(user_id))
    await message.answer(text, reply_markup=kb)
    
user_data = load_user_data()
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    register_user_for_broadcast(user_id)
    
    # ✅ ПРОВЕРЯЕМ, СОГЛАСИЛСЯ ЛИ ПОЛЬЗОВАТЕЛЬ С УСЛОВИЯМИ
    if not has_user_agreed(user_id):
        agreement_text = (
            "╔═══════════════════════╗\n"
            "              🎄 ❄️  ExVPN  ❄️  🎄\n"
            "╚═══════════════════════╝\n\n"
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Перед использованием бота, пожалуйста, "
            "ознакомьтесь с нашими документами:\n\n"
            "📋 <b>Политика конфиденциальности</b>\n"
            "Описывает, как мы работаем с вашими данными\n\n"
            "📄 <b>Пользовательское соглашение</b>\n"
            "Условия использования сервиса ExVPN\n\n"
            "Нажимая кнопку \"✅ Согласен\", вы принимаете "
            "условия обоих документов."
        )
        
        await message.answer(
            agreement_text,
            reply_markup=get_agreement_keyboard()
        )
        return
    
    # Если пользователь уже согласился — показываем основное меню
    await send_newyear_welcome(message, user_id)



# === X3UI API ===
class X3UI:
    def __init__(self):
        logger.info("Инициализация X3UI API")
        self.servers = {
            "n": {
                "name": "Netherlands", 
                "url": "https://38.180.231.73:34421/pZDsE0TOSvHl45G", 
                "user": "Y8NTRap3OH", 
                "pass": "bxKcpqyD9b", 
                "ip": "38.180.231.73",
                "inbounds": [1, 7]  # ← ДОБАВЬ ЭТУ СТРОКУ (список inbound)
            },
            "g": {
                "name": "Germany", 
                "url": "http://5.61.42.197:34421/XKmLaN0pBQ7KqMQ", 
                "user": "2j5bgQ4I7_", 
                "pass": "3Kg_6xQ-ie", 
                "ip": "5.61.42.197",
                "inbounds": [1, 3]  # ← ДОБАВЬ ЭТУ СТРОКУ
            },
            "u": {
                "name": "Usa", 
                "url": "http://38.180.138.121:12091/x84u6c3DW65Pe6ccvH", 
                "user": "Mo9tHvmNfN", 
                "pass": "tNqyj0tqDb", 
                "ip": "38.180.138.121",
                "inbounds": [2, 4]  # ← ДОБАВЬ ЭТУ СТРОКУ
            }
        }
        self.apis = {}
        self.inbound_cache = {}
        # ✅ ПОДКЛЮЧЕНИЕ С RETRY (без timeout)
        for sid, s in self.servers.items():
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"[X3UI] Попытка #{attempt} подключения к {s['name']}...")
                    
                    api = Api(
                        s["url"], 
                        s["user"], 
                        s["pass"], 
                        use_tls_verify=False  # ← Только этот параметр!
                    )
                    
                    api.login()
                    _ = api.inbound.get_list()
                    
                    self.apis[sid] = api
                    logger.info(f"[X3UI] ✅ Логин: {s['name']} (попытка #{attempt})")
                    break
                    
                except Exception as e:
                    logger.error(f"[X3UI] ❌ Ошибка логина {s['name']} (попытка #{attempt}/{max_retries}): {e}")
                    
                    if attempt < max_retries:
                        logger.info(f"[X3UI] Повторная попытка через {retry_delay} сек...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"[X3UI] ❌ Не удалось подключиться к {s['name']} после {max_retries} попыток")
        
        # ←←← УМНЫЙ КЭШ REALITY — ГЛАВНОЕ ИЗМЕНЕНИЕ
        self.last_known_reality = {
            "n": {"pbk": None, "sni": None, "sid": None},
            "g": {"pbk": None, "sni": None, "sid": None},
            "u": {"pbk": None, "sni": None, "sid": None}
        }
        self._load_last_known_reality()

        # ←←← КЛЮЧЕВОЕ: СРАЗУ ПОСЛЕ ЛОГИНА — ПРИНУДИТЕЛЬНО ОБНОВЛЯЕМ КЭШ ИЗ ПАНЕЛЕЙ
        # Это сработает и при первом запуске, и при каждом перезапуске
        logger.info("[REALITY] Принудительное обновление кэша Reality при старте бота...")
        for sid in self.apis:
            try:
                inbound = self.apis[sid].inbound.get_by_id(1)
                reality = inbound.stream_settings.reality_settings

                if isinstance(reality, dict):
                    settings = reality.get("settings", {})
                    pbk = settings.get("publicKey") or reality.get("publicKey")
                    sni_list = reality.get("serverNames") or settings.get("serverNames", [])
                    sid_list = reality.get("shortIds") or settings.get("shortIds", [])
                else:
                    settings = getattr(reality, "settings", {}) if hasattr(reality, "settings") else {}
                    pbk = settings.get("publicKey", getattr(reality, "publicKey", None))
                    sni_list = getattr(reality, "serverNames", []) or settings.get("serverNames", [])
                    sid_list = getattr(reality, "shortIds", []) or settings.get("shortIds", [])

                if pbk and sni_list and sid_list:
                    sni = sni_list[0]
                    shortid = sid_list[0]
                    self.last_known_reality[sid] = {"pbk": pbk, "sni": sni, "sid": shortid}
                    self._save_last_known_reality(sid, pbk, sni_list, sid_list)
                    logger.info(f"[REALITY STARTUP] Кэш обновлён для {sid}: SNI={sni} | ShortID={shortid}")
                else:
                    logger.warning(f"[REALITY STARTUP] Не удалось прочитать Reality для {sid} — будет fallback")
            except Exception as e:
                logger.error(f"[REALITY STARTUP] Ошибка при обновлении кэша для {sid}: {e}")
                self._auto_load_all_inbound_settings()
    
    def _auto_load_all_inbound_settings(self):
        """
        АВТОМАТИЧЕСКИ загружает настройки ВСЕХ inbound со всех серверов.
        Определяет: порт, протокол, Reality, transport и т.д.
        """
        logger.info("[AUTO-LOAD] Начинаю автоматическую загрузку настроек всех inbound...")
    
        for server_id, server in self.servers.items():
            if server_id not in self.apis:
                logger.warning(f"[AUTO-LOAD] Пропускаю {server['name']} — нет подключения")
                continue
        
            api = self.apis[server_id]
        
            for inbound_id in server["inbounds"]:
                try:
                    # Получаем inbound с панели
                    inbound = api.inbound.get_by_id(inbound_id)
                
                    # Извлекаем ВСЕ настройки
                    settings = self._extract_inbound_settings(inbound, server_id)
                
                    # Сохраняем в кэш
                    cache_key = (server_id, inbound_id)
                    self.inbound_cache[cache_key] = settings
                
                    logger.info(
                        f"[AUTO-LOAD] {server['name']} inbound#{inbound_id}: "
                        f"порт={settings['port']}, протокол={settings['protocol']}, "
                        f"Reality={'ДА' if settings['reality'] else 'НЕТ'}"
                    )
                
                except Exception as e:
                    logger.error(
                        f"[AUTO-LOAD] Не удалось загрузить {server['name']} "
                        f"inbound#{inbound_id}: {e}"
                    )
    
        logger.info(f"[AUTO-LOAD] Загружено настроек: {len(self.inbound_cache)} inbound")
    
    def _extract_inbound_settings(self, inbound, server_id):
        """
        Извлекает ВСЕ настройки из inbound: порт, протокол, Reality, transport и т.д.
        Возвращает словарь с настройками.
        """
        settings = {
            "port": inbound.port,
            "protocol": inbound.protocol,
            "remark": inbound.remark,
            "reality": None,
            "transport": "tcp",
            "security": "none",
            "flow": None
        }
        
        # === ОПРЕДЕЛЯЕМ TRANSPORT ===
        if hasattr(inbound, 'stream_settings') and inbound.stream_settings:
            stream = inbound.stream_settings
            settings["transport"] = getattr(stream, "network", "tcp")
            settings["security"] = getattr(stream, "security", "none")
            
            # === REALITY НАСТРОЙКИ ===
            if hasattr(stream, "reality_settings") and stream.reality_settings:
                reality = stream.reality_settings
                
                # Универсальный парсер (dict и object)
                if isinstance(reality, dict):
                    st = reality.get("settings", {})
                    pbk = st.get("publicKey") or reality.get("publicKey")
                    sni_list = reality.get("serverNames") or st.get("serverNames", [])
                    sid_list = reality.get("shortIds") or st.get("shortIds", [])
                else:
                    st = getattr(reality, "settings", {}) if hasattr(reality, "settings") else {}
                    pbk = st.get("publicKey", getattr(reality, "publicKey", None))
                    sni_list = getattr(reality, "serverNames", []) or st.get("serverNames", [])
                    sid_list = getattr(reality, "shortIds", []) or st.get("shortIds", [])
                
                if pbk and sni_list and sid_list:
                    settings["reality"] = {
                        "pbk": pbk,
                        "sni": sni_list[0],
                        "sid": sid_list[0],
                        "fp": "chrome"
                    }
                    settings["security"] = "reality"
                    settings["flow"] = "xtls-rprx-vision"
                    
                    logger.info(
                        f"[REALITY] {self.servers[server_id]['name']} inbound#{inbound.id}: "
                        f"SNI={sni_list[0]}"
                    )
            
            # === TLS НАСТРОЙКИ (если не Reality) ===
            elif hasattr(stream, "tls_settings") and stream.tls_settings:
                settings["security"] = "tls"
                # Можно добавить извлечение SNI для TLS
        
        return settings

    def _find_client_by_email(self, tg_id, server_id, inbound_id=None):
        if server_id not in self.apis: 
            logger.warning(f"[X3UI] Нет API для {server_id}")
            return None, None
        
        api = self.apis[server_id]
        
        # Определяем какие inbound проверять
        if inbound_id:
            inbounds_to_check = [inbound_id]
        else:
            inbounds_to_check = self.servers[server_id]["inbounds"]
        
        # Перебираем все inbound
        for ib_id in inbounds_to_check:
            try:
                inbound = api.inbound.get_by_id(ib_id)
                clients = getattr(inbound.settings, 'clients', [])
                
                # ✅ НОВЫЕ ВОЗМОЖНЫЕ EMAIL (С НОМЕРОМ INBOUND!)
                possible_emails = [
                    f"{tg_id}_{server_id}_ib{ib_id}",
                    f"{tg_id}_n_ib{ib_id}" if server_id == "n" else f"{tg_id}_g_ib{ib_id}",
                    f"{tg_id}_u_ib{ib_id}" if server_id == "u" else f"{tg_id}_{server_id}_ib{ib_id}",
                    f"{tg_id}_trial_ib{ib_id}",
                    # Старый формат (для обратной совместимости)
                    f"{tg_id}_{server_id}",
                    f"{tg_id}_n" if server_id == "n" else f"{tg_id}_g",
                    f"{tg_id}_u" if server_id == "u" else "",
                    f"{tg_id}_trial"
                ]
                
                for c in clients:
                    client_email = getattr(c, 'email', '')
                    if client_email in possible_emails:
                        logger.info(f"[X3UI] Найден клиент: {client_email} на {server_id} inbound#{ib_id}")
                        return c, ib_id
                    
            except Exception as e:
                logger.error(f"[X3UI] Ошибка поиска в {server_id} inbound#{ib_id}: {e}")
        
        logger.info(f"[X3UI] Клиент {tg_id} не найден на {server_id}")
        return None, None

    def _generate_vless_link_from_inbound(self, server_id, client_uuid, email, inbound=None, inbound_id=None):
        """
        Генерирует VLESS ссылку используя настройки из кэша.
        Учитывает transport (tcp/xhttp/grpc/ws) и Reality настройки.
        """
        logger.info(f"[VLESS] Генерация ссылки для {email} @ {server_id}")
        
        # Определяем inbound_id
        if not inbound_id and inbound:
            inbound_id = inbound.id
        elif not inbound_id:
            inbound_id = self.servers[server_id]["inbounds"][0]
        
        # Получаем настройки из кэша
        cache_key = (server_id, inbound_id)
        settings = self.inbound_cache.get(cache_key)
        
        if not settings:
            logger.error(f"[VLESS] НЕТ настроек для {server_id} inbound#{inbound_id} в кэше!")
            return None
        
        # === ПРОВЕРЯЕМ ПРОТОКОЛ ===
        if settings["protocol"] != "vless":
            logger.warning(
                f"[VLESS] inbound#{inbound_id} использует {settings['protocol']}, "
                "генерация VLESS невозможна"
            )
            return None
        
        # === БЕРЁМ НАСТРОЙКИ ИЗ КЭША ===
        ip = self.servers[server_id]["ip"]
        port = settings["port"]
        transport = settings.get("transport", "tcp")  # ← БЕРЁМ TRANSPORT!
        reality = settings.get("reality")
        
        # Если нет Reality — ошибка
        if not reality:
            logger.error(f"[VLESS] inbound#{inbound_id} не имеет Reality настроек!")
            return None
        
        # Генерируем тег
        tg_id = email.split("_")[0]
        tag = f"VPN-{tg_id}_{server_id}_ib{inbound_id}"
        
        # === БАЗОВАЯ ЧАСТЬ ССЫЛКИ ===
        link = f"vless://{client_uuid}@{ip}:{port}"
        
        # === ПАРАМЕТРЫ В ЗАВИСИМОСТИ ОТ TRANSPORT ===
        if transport == "tcp":
            link += f"?type=tcp&encryption=none&security=reality"
            link += f"&pbk={reality['pbk']}&fp={reality['fp']}"
            link += f"&sni={reality['sni']}&sid={reality['sid']}"
            link += f"&spx=%2F&flow={settings.get('flow', 'xtls-rprx-vision')}"
        
        elif transport == "xhttp" or transport == "splithttp":
            link += f"?type=xhttp&encryption=none&security=reality"
            link += f"&pbk={reality['pbk']}&fp={reality['fp']}"
            link += f"&sni={reality['sni']}&sid={reality['sid']}"
            link += f"&path=%2F"  # Можно добавить настраиваемый path
            # НЕТ flow для xhttp!
        
        elif transport == "grpc":
            link += f"?type=grpc&encryption=none&security=reality"
            link += f"&pbk={reality['pbk']}&fp={reality['fp']}"
            link += f"&sni={reality['sni']}&sid={reality['sid']}"
            link += f"&serviceName=grpc"  # Можно сделать настраиваемым
        
        elif transport == "ws":
            link += f"?type=ws&encryption=none&security=reality"
            link += f"&pbk={reality['pbk']}&fp={reality['fp']}"
            link += f"&sni={reality['sni']}&sid={reality['sid']}"
            link += f"&path=%2F"  # Можно сделать настраиваемым
        
        else:
            # Fallback для неизвестных transport
            logger.warning(f"[VLESS] Неизвестный transport: {transport}, использую tcp")
            link += f"?type=tcp&encryption=none&security=reality"
            link += f"&pbk={reality['pbk']}&fp={reality['fp']}"
            link += f"&sni={reality['sni']}&sid={reality['sid']}"
            link += f"&spx=%2F&flow={settings.get('flow', 'xtls-rprx-vision')}"
        
        # Добавляем тег в конец
        link += f"#{tag}"
        
        logger.info(
            f"[VLESS] Сгенерирована ссылка: {tag} | "
            f"порт={port} | transport={transport} | SNI={reality['sni']}"
        )
        return link

    def update_client_expiry(self, tg_id, new_expiry_time):
        """
        Обновляет expiry_time для всех клиентов пользователя БЕЗ пересоздания.
        Метод обновляет клиентов через полное обновление inbound.
        """
        logger.info(f"[UPDATE_EXPIRY] TG:{tg_id} -> {new_expiry_time}")
        
        updated_count = 0
        results = {}
        
        for sid in self.servers:
            if sid not in self.apis:
                results[sid] = "❌ API недоступен"
                continue
            
            api = self.apis[sid]
            inbound_ids = self.servers[sid]["inbounds"]
            server_updated = 0
            
            for inbound_id in inbound_ids:
                try:
                    # Получаем inbound
                    inbound = api.inbound.get_by_id(inbound_id)
                    clients = getattr(inbound.settings, 'clients', [])
                    
                    # Ищем клиента в списке
                    client_found = False
                    for client in clients:
                        client_email = getattr(client, 'email', "")
                        
                        # Проверяем, принадлежит ли клиент этому пользователю
                        possible_emails = [
                            f"{tg_id}_{sid}_ib{inbound_id}",
                            f"{tg_id}_n_ib{inbound_id}" if sid == "n" else f"{tg_id}_g_ib{inbound_id}" if sid == "g" else f"{tg_id}_u_ib{inbound_id}",
                            f"{tg_id}_trial_ib{inbound_id}",
                            f"{tg_id}_{sid}",
                            f"{tg_id}_n" if sid == "n" else f"{tg_id}_g" if sid == "g" else f"{tg_id}_u",
                            f"{tg_id}_trial"
                        ]
                        
                        if client_email in possible_emails:
                            # ✅ ОБНОВЛЯЕМ EXPIRY_TIME
                            old_expiry = getattr(client, 'expiry_time', 0)
                            client.expiry_time = new_expiry_time
                            
                            logger.info(f"[UPDATE_EXPIRY] {client_email} @ {sid} inbound#{inbound_id}: {old_expiry} -> {new_expiry_time}")
                            client_found = True
                            server_updated += 1
                            updated_count += 1
                            break
                    
                    if client_found:
                        # ✅ СОХРАНЯЕМ ОБНОВЛЁННЫЙ INBOUND
                        api.inbound.update(inbound_id, inbound)
                        logger.info(f"[UPDATE_EXPIRY] ✅ Inbound#{inbound_id} на {sid} обновлён")
                        
                except Exception as e:
                    logger.error(f"[UPDATE_EXPIRY] ❌ Ошибка {sid} inbound#{inbound_id}: {e}")
            
            if server_updated > 0:
                results[sid] = f"✅ Продлено ({server_updated} inbound)"
            else:
                results[sid] = "⚠️ Клиент не найден"
        
        logger.info(f"[UPDATE_EXPIRY] Обновлено клиентов: {updated_count}")
        return updated_count > 0, results

    def recreate_without_adding_days(self, tg_id, target_server_id=None):
        """
        Пересоздать клиентов, сохранив текущий expiry_time.
        Дни НЕ добавляются.
        """
        logger.info(f"[VLESS] recreate_without_adding_days: TG:{tg_id}, сервер: {target_server_id}")

        # 1. Берём текущий статус (где есть expiry_time)
        status = self.get_client_status(tg_id)  # используй свою реализацию

        if target_server_id:
            server_ids = [target_server_id]
        else:
            server_ids = list(self.servers.keys())  # например ["n","g","u"]

        old_expiry = None
        for sid in server_ids:
            srv = status.get(sid) or {}
            et = srv.get("expiry_time")
            if isinstance(et, (int, float)) and et > 0:
                old_expiry = int(et)
                break

        # если нет активного срока — реши политику: ошибка или дефолтный срок
        if old_expiry is None:
            logger.warning(f"[VLESS] recreate_without_adding_days: нет expiry_time для TG:{tg_id}")
            # либо вернуть ошибку:
            # return False, {"error": "no_expiry"}, 0
            # либо выдать, допустим, 30 дней:
            return self.sync_and_issue_vless(
                tg_id,
                target_server_id=target_server_id,
                days=30,
                delete_mode=False,
                recreate_mode=False,
                expiry_time=None
            )

        # 2. Пересоздаём с тем же expiry_time
        return self.sync_and_issue_vless(
            tg_id,
            target_server_id=target_server_id,
            days=None,             # не добавляем дни
            delete_mode=False,
            recreate_mode=False,   # важно: не включаем auto +30
            expiry_time=old_expiry # используем старый срок
        )

    def sync_and_issue_vless(self, tg_id, target_server_id=None, days=None, delete_mode=False, recreate_mode=False, expiry_time=None):
        logger.info(f"[VLESS] sync_and_issue_vless: TG:{tg_id}, сервер: {target_server_id}, дней: {days}, delete: {delete_mode}, recreate: {recreate_mode}")
        try:
            user_id = str(tg_id)
            results = {}
            servers = [target_server_id] if target_server_id else self.servers.keys()

            # === РЕЖИМ УДАЛЕНИЯ ===
            if delete_mode:
                logger.info(f"[VLESS] Режим УДАЛЕНИЯ для TG:{tg_id}")
                for sid in servers:
                    if sid not in self.apis:
                        results[sid] = "Нет API"
                        continue

                    api = self.apis[sid]
                    
                    # Получаем все inbound для удаления
                    inbound_ids = self.servers[sid]["inbounds"]
                    deleted_count = 0
                    
                    for work_inbound_id in inbound_ids:
                        client, found_inbound = self._find_client_by_email(tg_id, sid, work_inbound_id)
                        
                        if client and found_inbound:
                            try:
                                inbound = api.inbound.get_by_id(work_inbound_id)
                                api.client.delete(inbound.id, client.id)
                                logger.info(f"[VLESS] Удалён клиент {tg_id}@{sid} из inbound#{work_inbound_id}")
                                deleted_count += 1
                            except Exception as e:
                                logger.error(f"[DELETE] Ошибка удаления из inbound#{work_inbound_id}: {e}")
                    
                    if deleted_count > 0:
                        results[sid] = f"Удалён ({deleted_count} inbound)"
                        if user_id in user_data and "vless_links" in user_data[user_id]:
                            user_data[user_id]["vless_links"][sid] = ""
                    else:
                        results[sid] = "Нет клиента"
                        
                save_json("user_data.json", user_data)
                return True, results, 0

            # === ВЫЧИСЛЯЕМ EXPIRY_TIME ===
            final_expiry = expiry_time
            if final_expiry is None:
                if recreate_mode:
                    final_expiry = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).timestamp() * 1000)
                elif days == 0:
                    final_expiry = 0
                elif days is not None:
                    final_expiry = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).timestamp() * 1000)
                else:
                    final_expiry = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).timestamp() * 1000)

            # === СОЗДАНИЕ/ОБНОВЛЕНИЕ КЛИЕНТОВ ===
            for sid in servers:
                if sid not in self.apis:
                    results[sid] = "Нет API"
                    continue

                api = self.apis[sid]
                
                # ✅ ПОЛУЧАЕМ ВСЕ INBOUND ДЛЯ ЭТОГО СЕРВЕРА
                inbound_ids = self.servers[sid]["inbounds"]
                created_links = []  # Список ссылок для всех inbound
                
                # ✅ СОЗДАЁМ КЛИЕНТОВ НА КАЖДОМ INBOUND
                for work_inbound_id in inbound_ids:
                    logger.info(f"[VLESS] Обработка {sid} inbound#{work_inbound_id}")
                    
                    # Проверяем, есть ли уже клиент
                    client, found_inbound = self._find_client_by_email(tg_id, sid, work_inbound_id)
                    inbound = api.inbound.get_by_id(work_inbound_id)

                    # Удаляем старого клиента, если есть
                    if client and found_inbound:
                        try:
                            old_inbound = api.inbound.get_by_id(found_inbound)
                            api.client.delete(old_inbound.id, client.id)
                            logger.info(f"[FORCE] Удалён старый клиент {tg_id}@{sid} из inbound#{found_inbound}")
                        except Exception as e:
                            logger.error(f"[FORCE] Не удалось удалить старый клиент: {e}")

                    # Генерируем новый UUID
                    uuid_new = str(uuid.uuid4())
                    
                    # === ФОРМИРУЕМ EMAIL С НОМЕРОМ INBOUND (ДЛЯ УНИКАЛЬНОСТИ!) ===
                    old_email = ""
                    if client:
                        old_email = getattr(client, "email", "") or ""

                    # Определяем email с номером inbound
                    if days is not None and days <= 3 and sid == "n":
                        email = f"{tg_id}_trial_ib{work_inbound_id}"
                    elif old_email and "_trial" in old_email:
                        email = f"{tg_id}_trial_ib{work_inbound_id}"
                    elif sid == "n":
                        email = f"{tg_id}_n_ib{work_inbound_id}"
                    elif sid == "g":
                        email = f"{tg_id}_g_ib{work_inbound_id}"
                    elif sid == "u":
                        email = f"{tg_id}_u_ib{work_inbound_id}"
                    else:
                        email = f"{tg_id}_{sid}_ib{work_inbound_id}"
                    
                    # Создаём нового клиента
                    client_new = Client(
                        id=uuid_new, 
                        email=email,  # ← УНИКАЛЬНЫЙ EMAIL!
                        enable=True,
                        expiry_time=final_expiry, 
                        totalGB=0, 
                        limitIp=3,
                        tgId=str(tg_id), 
                        flow="xtls-rprx-vision"
                    )
                    
                    try:
                        api.client.add(inbound.id, [client_new])
                        logger.info(f"[FORCE] Создан новый клиент {email} inbound#{work_inbound_id} expiry_time={final_expiry}")
                    except Exception as e:
                        logger.error(f"[FORCE] Ошибка создания клиента на inbound#{work_inbound_id}: {e}")
                        continue
                    
                    # Генерируем VLESS ссылку
                    inbound = api.inbound.get_by_id(work_inbound_id)
                    link = self._generate_vless_link_from_inbound(sid, uuid_new, email, inbound, work_inbound_id)
                    
                    if link:
                        created_links.append(link)
                        logger.info(f"[VLESS] Создана ссылка для {sid} inbound#{work_inbound_id}")
                
                # === СОХРАНЯЕМ РЕЗУЛЬТАТЫ ===
                if created_links:
                    # Сохраняем первую ссылку в user_data
                    user_data.setdefault(user_id, {
                        "vless_links": {"n": "", "g": "", "u": ""}, 
                        "tariff": "dual_server", 
                        "referrer": None
                    })
                    user_data[user_id]["vless_links"][sid] = created_links[0]
                    
                    # Возвращаем все ссылки через перенос строки
                    results[sid] = "\n\n".join(created_links)
                else:
                    results[sid] = "Ошибка создания"

            save_json("user_data.json", user_data)

            # === ВЫЧИСЛЯЕМ ДНЕЙ ДЛЯ ВЫВОДА ===
            if expiry_time:
                days_out = "по дате"
            elif final_expiry == 0:
                days_out = "Infinity"
            else:
                now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
                days_out = max(1, (final_expiry - now) // (86400 * 1000))

            logger.info(f"[VLESS] Успешно выдано TG:{tg_id}, дней: {days_out}")
            return True, results, days_out
            
        except Exception as e:
            logger.error(f"[VLESS] КРИТ: {e}", exc_info=True)
            return False, f"Ошибка: {e}", 0



    def get_client_status(self, user_id):
        logger.info(f"[STATUS] Проверка статуса для TG:{user_id}")
        status = {}
        now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        user_id_str = str(user_id)

        for sid in self.servers:
            loc = self.servers[sid]['name']
            
            # ✅ ПРОВЕРЯЕМ ВСЕ INBOUND ДЛЯ ЭТОГО СЕРВЕРА
            inbound_ids = self.servers[sid]["inbounds"]
            
            # Собираем информацию со всех inbound
            found_any_client = False
            max_expiry = 0
            any_enabled = False
            first_active_link = ""
            
            for inbound_id in inbound_ids:
                client, found_inbound = self._find_client_by_email(user_id, sid, inbound_id)
                
                if client:
                    found_any_client = True
                    expiry = getattr(client, 'expiry_time', 0) or 0
                    enable = getattr(client, 'enable', False)
                    
                    logger.info(f"[STATUS] {loc} inbound#{inbound_id} | TG:{user_id} | expiry_time={expiry} | enable={enable}")
                    
                    # Запоминаем максимальный expiry
                    if expiry > max_expiry:
                        max_expiry = expiry
                    
                    # Если клиент активен — генерируем ссылку
                    if enable and (expiry == 0 or expiry > now_ms):
                        any_enabled = True
                        
                        # Генерируем ссылку только если ещё не сгенерировали
                        if not first_active_link:
                            try:
                                link = self._generate_vless_link_from_inbound(
                                    sid, 
                                    client.id, 
                                    client.email, 
                                    inbound_id=found_inbound
                                )
                                if link:
                                    first_active_link = link
                            except Exception as e:
                                logger.error(f"[STATUS] Ошибка генерации {sid} inbound#{inbound_id}: {e}")
            
            # ✅ СОХРАНЯЕМ ПЕРВУЮ АКТИВНУЮ ССЫЛКУ В user_data
            if first_active_link:
                user_data.setdefault(user_id_str, {
                    "vless_links": {"n": "", "g": "", "u": ""}, 
                    "tariff": "dual_server", 
                    "referrer": None
                })
                user_data[user_id_str]["vless_links"][sid] = first_active_link
                save_json("user_data.json", user_data)
            
            # ✅ ОПРЕДЕЛЯЕМ СТАТУС СЕРВЕРА
            if not found_any_client:
                status[sid] = {
                    'activ': 'Не зарегистрирован', 
                    'time': '-', 
                    'days_left': 0, 
                    'location': loc
                }
                # Очищаем user_data если клиента нет
                if user_id_str in user_data and user_data[user_id_str]["vless_links"].get(sid):
                    user_data[user_id_str]["vless_links"][sid] = ""
                    save_json("user_data.json", user_data)
            
            elif not any_enabled:
                status[sid] = {
                    'activ': 'Отключен', 
                    'time': '-', 
                    'days_left': 0, 
                    'location': loc
                }
            
            elif max_expiry == 0:
                status[sid] = {
                    'activ': 'Активен', 
                    'time': 'Infinity', 
                    'days_left': -1, 
                    'location': loc
                }
            
            elif max_expiry > now_ms:
                exp_date = datetime.datetime.fromtimestamp(max_expiry / 1000, datetime.timezone.utc)
                days_left = (max_expiry - now_ms) // (86400 * 1000)
                status[sid] = {
                    'activ': 'Активен', 
                    'time': exp_date.strftime('%d.%m.%Y'), 
                    'days_left': days_left, 
                    'location': loc
                }
            
            else:
                status[sid] = {
                    'activ': 'Истёк', 
                    'time': '-', 
                    'days_left': 0, 
                    'location': loc
                }

        return status


        # ИСПРАВЛЕННЫЙ МЕТОД — ПРОДЛЕНИЕ ЧЕРЕЗ ПЕРЕСОЗДАНИЕ КЛИЕНТА
        # === НОВЫЙ extend_vless — правильное продление от текущей даты истечения ===
    def extend_vless(self, tg_id, days):
        """
        Продление подписки (используется для промокодов).
        """
        logger.info(f"[EXTEND] TG:{tg_id} +{days} дней")
        user_id_str = str(tg_id)
        
        # 1. ПОЛУЧАЕМ ТЕКУЩИЙ МАКСИМАЛЬНЫЙ EXPIRY
        status = self.get_client_status(tg_id)
        max_expiry = 0
        now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        
        has_active = False
        for sid in self.servers:
            s = status[sid]
            if s['activ'] in ["Активен", "Истёк"]:
                has_active = True
                inbound_ids = self.servers[sid]["inbounds"]
                for inbound_id in inbound_ids:
                    client, found_inbound = self._find_client_by_email(tg_id, sid, inbound_id)
                    if client and hasattr(client, 'expiry_time'):
                        exp = getattr(client, 'expiry_time', 0) or 0
                        if exp > max_expiry:
                            max_expiry = exp

        if not has_active:
            return False, "❌ Нет клиентов для продления", 0

        # 2. ВЫЧИСЛЯЕМ НОВУЮ ДАТУ
        if max_expiry > now_ms:
            new_expiry = max_expiry + (days * 24 * 60 * 60 * 1000)
        else:
            new_expiry = now_ms + (days * 24 * 60 * 60 * 1000)
        
        new_expiry = int(new_expiry)

        # 3. ОБНОВЛЯЕМ EXPIRY БЕЗ ПЕРЕСОЗДАНИЯ
        success, results = self.update_client_expiry(tg_id, new_expiry)
        
        if success:
            days_left = max(1, (new_expiry - now_ms) // (86400 * 1000))
            
            # Генерируем ссылки
            links = {}
            for sid in self.servers:
                if sid not in self.apis:
                    continue
                
                inbound_ids = self.servers[sid]["inbounds"]
                for inbound_id in inbound_ids:
                    client, found_inbound = self._find_client_by_email(tg_id, sid, inbound_id)
                    if client and sid not in links:
                        try:
                            link = self._generate_vless_link_from_inbound(
                                sid, client.id, client.email, inbound_id=found_inbound
                            )
                            if link:
                                links[sid] = link
                                user_data.setdefault(user_id_str, {
                                    "vless_links": {"n": "", "g": "", "u": ""}, 
                                    "tariff": "dual_server", 
                                    "referrer": None
                                })
                                user_data[user_id_str]["vless_links"][sid] = link
                        except Exception as e:
                            logger.error(f"[EXTEND] Ошибка генерации {sid}: {e}")
            
            save_json("user_data.json", user_data)
            return True, links, days_left
        else:
            return False, results, 0

        
            # === УМНЫЙ FALLBACK ===
    def _load_last_known_reality(self):
        if os.path.exists("last_reality.json"):
            try:
                with open("last_reality.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_known_reality.update(data)
                    logger.info(f"[FALLBACK] Загружены последние Reality-настройки: {data}")
            except Exception as e:
                logger.error(f"[FALLBACK] Ошибка загрузки last_reality.json: {e}")

    def _save_last_known_reality(self, server_id, pbk, sni_list, sid_list):
        if sni_list: sni = sni_list[0]
        else: sni = None
        if sid_list: sid = sid_list[0]
        else: sid = None
        self.last_known_reality[server_id] = {"pbk": pbk, "sni": sni, "sid": sid}
        try:
            with open("last_reality.json", "w", encoding="utf-8") as f:
                json.dump(self.last_known_reality, f, ensure_ascii=False, indent=4)
            logger.info(f"[FALLBACK] Сохранены актуальные Reality для {server_id}: SNI={sni}")
        except Exception as e:
            logger.error(f"[FALLBACK] Не удалось сохранить last_reality.json: {e}")

vpn = X3UI()

# === INFERNO VPS API + СЕРВЕРА + ТАЙМЕРЫ ПЕРЕЗАГРУЗКИ ===
class InfernoVPSAPI:
    def __init__(self):
        logger.info("Инициализация Inferno VPS API")
        self.base_url = VPS_API_BASE
        self.cid = VPS_CID
        self.api_key = VPS_API_KEY
        self.headers = {"Content-Type": "application/json", "X-Key": self.api_key}
        self.servers_for_reboot = {
            "38.180.231.73": "Netherlands",
            "5.61.42.197": "Germany",
            "38.180.138.121": "USA"
        }
        self.reboot_timers = {}

    def _request(self, action, data=None):
        url = f"{self.base_url}?action={action}"
        logger.info(f"[VPS API] Запрос: {action}")
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"[VPS API] Ответ: {result}")
            return result
        except Exception as e:
            logger.error(f"[VPS API] Ошибка {action}: {e}")
            return {"result": "fail", "message": str(e)}

    def get_orders(self):
        data = {"cid": self.cid}
        result = self._request("orders", data)
        return result.get("orders", {})

    def get_vps_status(self, orderid):
        data = {"cid": self.cid, "orderid": orderid}
        return self._request("getinfo", data)

    def reboot_vps(self, orderid):
        data = {"cid": self.cid, "orderid": orderid}
        return self._request("reboot", data)

    def get_pending_invoices(self):
        orders = self.get_orders()
        return {k: v for k, v in orders.items() if v.get("status") == "Pending"}

    def start_reboot_cooldown(self, ip):
        end_time = asyncio.get_event_loop().time() + 60
        self.reboot_timers[ip] = end_time
        logger.info(f"[REBOOT] Кулдаун 60 сек для {ip} до {datetime.datetime.fromtimestamp(end_time)}")

    def is_reboot_cooldown(self, ip):
        end = self.reboot_timers.get(ip)
        if not end: return False
        if asyncio.get_event_loop().time() >= end:
            self.reboot_timers.pop(ip, None)
            logger.info(f"[REBOOT] Кулдаун завершён для {ip}")
            return False
        logger.info(f"[REBOOT] Кулдаун активен для {ip} — ещё {int(end - asyncio.get_event_loop().time())} сек")
        return True

vps_api = InfernoVPSAPI()

# === КЛАВИАТУРЫ ===
def get_initial_keyboard(user_id: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="💳 Купить VPN", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="🌐 Мой VPN", callback_data="my_vpn")],
        [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🎁 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="📖 Инструкция по подключению", url="https://telegra.ph/Kak-podklyuchitsya-k-ExVPN-02-27")],
        [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/ExVPN_support")],
        [InlineKeyboardButton(text="📋 Документы", callback_data="show_documents")]
    ]
    
    if str(user_id) == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выдать VLESS", callback_data="admin_issue_vless")],
        [InlineKeyboardButton(text="Промокоды", callback_data="admin_promocodes_menu")],
        [InlineKeyboardButton(text="Управление пользователями", callback_data="user_management")],
        [InlineKeyboardButton(text="Reality", callback_data="admin_reality")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="Inferno VPS", callback_data="inferno_panel")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_initial")],
        [InlineKeyboardButton(text="Полная чистка email (платные _n/_g, trial → _trial)", callback_data="fix_emails_final")],
    ])

def get_user_management_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить по TG ID", callback_data="delete_by_tgid")],
        [InlineKeyboardButton(text="Продлить по TG ID", callback_data="extend_by_tgid")],
        [InlineKeyboardButton(text="Копировать на другой сервер", callback_data="copy_to_server")],
        [InlineKeyboardButton(text="Удалить полностью", callback_data="delete_full")],
        [InlineKeyboardButton(text="Запись в файл", callback_data="export_inbound_menu")],
        [InlineKeyboardButton(text="Удалить по категории", callback_data="delete_by_category_menu")],
        [InlineKeyboardButton(text="Назад", callback_data="admin")],
    ])

def get_inferno_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VPS Статус", callback_data="vps_full_status")],
        [InlineKeyboardButton(text="Перезагрузка сервера", callback_data="reboot_servers_menu")],
        [InlineKeyboardButton(text="Оплатить Счета VPS", callback_data="vps_pay_invoices")],
        [InlineKeyboardButton(text="Назад", callback_data="admin")],
    ])

# === ПРОМОКОДЫ ===
PROMOFILE = "promocodes.json"


def load_promocodes():
    logger.info("Загрузка promocodes.json")
    if os.path.exists(PROMOFILE) and os.path.getsize(PROMOFILE) > 0:
        try:
            with open(PROMOFILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"promocodes.json загружен: {len(data)} промокодов")
            return data
        except Exception as e:
            logger.error(f"[PROMO] Ошибка чтения {PROMOFILE}: {e}")
    logger.warning("promocodes.json пуст или не найден")
    return {}


def save_promocodes(data: dict):
    logger.info("Сохранение promocodes.json")
    with open(PROMOFILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("promocodes.json сохранён")


def create_promocode(code: str, days: int, uses: int, expiry_date: str | None = None) -> bool:
    code = code.strip().upper()
    data = load_promocodes()

    if code in data:
        logger.warning(f"[PROMO] Промокод {code} уже существует")
        return False

    expiry_ts = None
    if expiry_date and expiry_date.lower() not in ("!", "no"):
        try:
            d = datetime.datetime.strptime(expiry_date, "%d.%m.%Y")
            expiry_ts = int(d.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
        except Exception as e:
            logger.error(f"[PROMO] Ошибка парсинга даты {expiry_date}: {e}")
            return False

    data[code] = {
        "days": days,
        "max_uses": uses,
        "used": 0,
        "used_by": [],          # список TG-ID, которые уже активировали код
        "expiry_date": expiry_date if expiry_date and expiry_date.lower() not in ("!", "no") else None,
        "expiry_ts": expiry_ts,
    }

    save_promocodes(data)
    logger.info(f"[PROMO] Создан промокод {code}: {days} дн., uses={uses}, expiry={expiry_date}")
    return True


def delete_promocode(code: str) -> bool:
    code = code.strip().upper()
    data = load_promocodes()
    if code in data:
        del data[code]
        save_promocodes(data)
        logger.info(f"[PROMO] Промокод {code} удалён")
        return True
    logger.warning(f"[PROMO] Промокод {code} не найден при удалении")
    return False


def list_promocodes() -> str:
    data = load_promocodes()
    if not data:
        return "❌ <b>Промокоды отсутствуют.</b>"

    lines = ["<b>📋 Список промокодов:</b>\n"]
    for code, p in data.items():
        days = p.get("days", 0)
        used = p.get("used", 0)
        max_uses = p.get("max_uses", 0)
        exp = p.get("expiry_date") or "∞"
        uses_text = f"{used}/{max_uses}" if max_uses > 0 else f"{used}"

        lines.append(
            f"<code>{code}</code> — {days} дн.\n"
            f"  использовано: <b>{uses_text}</b>\n"
            f"  истекает: {exp}\n"
        )
    return "\n".join(lines)


def use_promocode(code: str, user_id: int):
    """
    Возвращает:
      None                           – код не найден / истёк / исчерпан
      {'error': 'already_used', ...} – этот юзер уже активировал код
      {'days': N, 'code': CODE, 'remaining': M} – успешная активация
    """
    code = code.strip().upper()
    data = load_promocodes()

    if code not in data:
        logger.info(f"[PROMO] Промокод {code} не найден")
        return None

    promo = data[code]

    # 1) Уже использовал этот код?
    if user_id in promo.get("used_by", []):
        logger.info(f"[PROMO] {code} уже использован TG:{user_id}")
        return {"error": "already_used", "code": code}

    # 2) Проверка срока действия
    expiry_ts = promo.get("expiry_ts")
    if expiry_ts:
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        if now > expiry_ts:
            logger.info(f"[PROMO] Промокод {code} истёк")
            return None

    # 3) Лимит использований
    used = promo.get("used", 0)
    max_uses = promo.get("max_uses", 0)
    if max_uses > 0 and used >= max_uses:
        logger.info(f"[PROMO] Промокод {code} исчерпан")
        return None

    # 4) Фиксируем использование
    promo["used"] = used + 1
    promo.setdefault("used_by", []).append(user_id)
    save_promocodes(data)

    remaining = max_uses - promo["used"] if max_uses > 0 else -1
    logger.info(f"[PROMO] {code} использован TG:{user_id}, осталось: {remaining}")
    return {"days": promo["days"], "code": code, "remaining": remaining}

@dp.callback_query(F.data == "agree_to_terms")
async def agree_handler(c: types.CallbackQuery):
    """
    Обработчик согласия с условиями
    """
    user_id = c.from_user.id
    
    # Сохраняем согласие
    set_user_agreement(user_id)
    
    # Удаляем сообщение с соглашением
    try:
        await c.message.delete()
    except:
        pass
    
    # Показываем приветствие
    welcome_text = (
        "╔═══════════════════════╗\n"
        "              🎄 ❄️  ExVPN  ❄️  🎄\n"
        "╚═══════════════════════╝\n\n"
        "🎅 С наступающим Новым 2026 годом! 🎆\n\n"
        "✨ Ваш надёжный VPN-сервис ✨\n\n"
        "🌍 Доступные локации:\n"
        "  🇳🇱 Нидерланды\n"
        "  🇩🇪 Германия\n"
        "  🇺🇸 США\n\n"
        "⚡️ Преимущества:\n"
        "  🔥 VLESS Reality + Vision\n"
        "  🛡 Защита от блокировок\n"
        "  🚀 Высокая скорость\n"
        "  💎 Стабильное соединение\n"
        "  💬 Поддержка 24/7\n\n"
        "🎄 Выберите действие ниже: 👇"
    )
    
    kb = get_initial_keyboard(str(user_id))
    
    await c.message.answer(
        welcome_text,
        reply_markup=kb
    )
    
    await c.answer("✅ Спасибо! Добро пожаловать в ExVPN!", show_alert=False)

@dp.callback_query(F.data == "show_documents")
async def show_documents_handler(c: types.CallbackQuery):
    """
    Показывает ссылки на политику конфиденциальности и соглашение
    """
    doc_text = (
        "📋 <b>Документы ExVPN</b>\n\n"
        "Ознакомьтесь с нашими документами:\n\n"
        "📄 <b>Политика конфиденциальности</b>\n"
        "Узнайте, как мы защищаем ваши данные\n\n"
        "📄 <b>Пользовательское соглашение</b>\n"
        "Условия использования сервиса"
    )
    
    buttons = [
        [InlineKeyboardButton(
            text="📋 Политика конфиденциальности",
            url=PRIVACY_POLICY_URL
        )],
        [InlineKeyboardButton(
            text="📄 Пользовательское соглашение",
            url=USER_AGREEMENT_URL
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_initial"
        )]
    ]
    
    await c.message.edit_text(
        doc_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

# === ПРОМОКОДЫ: АДМИНКА ===
@dp.callback_query(F.data == "admin_promocodes_menu")
async def admin_promocodes_menu(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)
    logger.info(f"Админ {c.from_user.id} открыл меню промокодов")
    await c.answer()
    kb = [
        [InlineKeyboardButton(text="Создать промокод", callback_data="promo_create")],
        [InlineKeyboardButton(text="Удалить промокод", callback_data="promo_delete")],
        [InlineKeyboardButton(text="Список промокодов", callback_data="promo_list")],
        [InlineKeyboardButton(text="Назад", callback_data="admin")],
    ]
    await c.message.edit_text("<b>Управление промокодами</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "promo_create")
async def promo_create_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    logger.info("Админ начал создание промокода")
    await c.answer()
    await state.set_state(Form.waiting_for_promo_code)
    await c.message.edit_text("Введите <b>промокод</b> (например: EXVPN30):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_promocodes_menu")]]))

@dp.message(Form.waiting_for_promo_code)
async def promo_code_input(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID:
        await state.clear()
        return
    code = m.text.strip().upper()
    if len(code) < 3:
        return await m.reply("Слишком короткий код!")
    await state.update_data(code=code)
    await state.set_state(Form.waiting_for_promo_days)
    await m.reply("Сколько <b>дней</b> дает промокод?\n(например: 30)")

@dp.message(Form.waiting_for_promo_days)
async def promo_days_input(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    try:
        days = int(m.text.strip())
        if days <= 0: raise ValueError
    except:
        return await m.reply("Введите число > 0")
    await state.update_data(days=days)
    await state.set_state(Form.waiting_for_promo_uses)
    await m.reply("Максимум <b>использований</b>?\n(0 = бесконечно)")

@dp.message(Form.waiting_for_promo_uses)
async def promo_uses_input(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    try:
        uses = int(m.text.strip())
        if uses < 0: raise ValueError
    except:
        return await m.reply("Введите число ≥ 0")
    await state.update_data(uses=uses)
    await state.set_state(Form.waiting_for_promo_date)
    await m.reply("До какой даты? (дд.мм.гггг)\nИли <code>нет</code> для бессрочного:")

@dp.message(Form.waiting_for_promo_date)
async def promo_date_input(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    data = await state.get_data()
    date_str = m.text.strip()
    expiry = None if date_str.lower() in ["нет", "no", ""] else date_str
    success = create_promocode(data["code"], data["days"], data["uses"], expiry)
    if success:
        await m.reply(f"Промокод <code>{data['code']}</code> создан!\nДней: {data['days']}\nИсп: 0/{data['uses'] or '∞'}")
    else:
        await m.reply("Ошибка: промокод уже существует!")
    await state.clear()

@dp.callback_query(F.data == "promo_delete")
async def promo_delete_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    logger.info("Админ начал удаление промокода")
    await c.answer()
    await state.set_state(Form.waiting_for_promo_delete)
    await c.message.edit_text("Введите промокод для <b>удаления</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_promocodes_menu")]]))

@dp.message(Form.waiting_for_promo_delete)
async def promo_delete_confirm(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    code = m.text.strip().upper()
    if delete_promocode(code):
        await m.reply(f"Промокод <code>{code}</code> удалён.")
    else:
        await m.reply("Промокод не найден.")
    await state.clear()

@dp.callback_query(F.data == "promo_list")
async def promo_list(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID: return
    logger.info("Админ запросил список промокодов")
    await c.answer()
    text = list_promocodes()
    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_promocodes_menu")]]))

# === ВВОД ПРОМОКОДА: ПОЛЬЗОВАТЕЛЬ + АДМИН ===
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_start(c: types.CallbackQuery, state: FSMContext):
    is_admin = str(c.from_user.id) == ADMIN_ID
    logger.info(f"{'Админ' if is_admin else 'Пользователь'} {c.from_user.id} открыл ввод промокода")
    await c.answer()
    await state.set_state(Form.waiting_for_promo_input)
    back_cb = "admin" if is_admin else "back_to_initial"
    await c.message.edit_text(
        "Введите промокод:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data=back_cb)]
        ])
    )

@dp.message(Form.waiting_for_promo_input)
async def process_promo_input(m: types.Message, state: FSMContext):
    code = m.text.strip().upper()
    is_admin = str(m.from_user.id) == ADMIN_ID
    back_kb = get_admin_keyboard() if is_admin else get_initial_keyboard(str(m.from_user.id))
    
    result = use_promocode(code, m.from_user.id)
    
    # ❌ ПРОМОКОД НЕДЕЙСТВИТЕЛЕН
    if not result:
        await m.reply(
            f"❌ Промокод <code>{code}</code> не найден, истёк или закончились активации.",
            reply_markup=back_kb
        )
        logger.info(f"[PROMO] Неверный промокод: {code}, TG:{m.from_user.id}")
        await state.clear()
        return
    
    # ❌ УЖЕ ИСПОЛЬЗОВАН
    if result.get("error") == "already_used":
        await m.reply(
            f"⚠️ <b>Вы уже использовали промокод <code>{result['code']}</code></b>\n\n"
            f"Каждый промокод можно активировать только один раз.",
            reply_markup=back_kb
        )
        logger.info(f"[PROMO] Повторное использование {code} TG:{m.from_user.id}")
        await state.clear()
        return
    
    # ✅ ПРОВЕРЯЕМ: ЕСТЬ ЛИ У ПОЛЬЗОВАТЕЛЯ ПОДПИСКА?
    status = vpn.get_client_status(m.from_user.id)
    has_subscription = False
    
    for sid in vpn.servers:
        if status[sid]['activ'] in ["Активен", "Истёк"]:
            has_subscription = True
            break
    
    # ✅ ЕСЛИ ПОДПИСКИ НЕТ → СОЗДАЁМ НОВУЮ
    if not has_subscription:
        logger.info(f"[PROMO] {code} создаёт новую подписку для TG:{m.from_user.id}")
        
        success, results, days_left = vpn.sync_and_issue_vless(
            m.from_user.id, 
            days=result['days']
        )
        
        if success:
            expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=result['days'])
            
            text = f"🎉 <b>Промокод <code>{result['code']}</code> активирован!</b>\n\n"
            text += f"🎁 Вы получили <b>{result['days']} дней</b> доступа\n"
            text += f"📅 <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}\n\n"
            text += "<b>🔑 Ваши ключи:</b>\n\n"
            
            for sid, link in results.items():
                if isinstance(link, str) and link.startswith("vless://"):
                    # Берём только первую ссылку (если их несколько)
                    first_link = link.split("\n\n")[0] if "\n\n" in link else link
                    text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
            
            text += "📱 <i>Используйте приложения:</i>\n"
            text += "• Nekobox (Android/iOS)\n"
            text += "• v2rayNG (Android)\n"
            text += "• Streisand (iOS)"
            
            await m.reply(text, reply_markup=back_kb)
            logger.info(f"[PROMO] {result['code']} создал подписку: {result['days']} дн. TG:{m.from_user.id}")
        else:
            await m.reply(
                f"❌ Ошибка при создании подписки.\n\n"
                f"Обратитесь в поддержку: @ExVPNsupport",
                reply_markup=back_kb
            )
    
    # ✅ ЕСЛИ ПОДПИСКА ЕСТЬ → ПРОДЛЕВАЕМ
    else:
        logger.info(f"[PROMO] {code} продлевает подписку для TG:{m.from_user.id}")
        
        success, links, days_left = vpn.extend_vless(m.from_user.id, result['days'])
        
        if success:
            now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
            expiry_date = datetime.datetime.fromtimestamp(
                (now_ms + days_left * 86400 * 1000) / 1000, 
                datetime.timezone.utc
            )
            
            text = f"✅ <b>Промокод <code>{result['code']}</code> активирован!</b>\n\n"
            text += f"🎁 Добавлено <b>+{result['days']} дней</b>\n"
            text += f"📅 <b>Подписка продлена до:</b> {expiry_date.strftime('%d.%m.%Y')}\n\n"
            text += f"⏳ <b>Осталось дней:</b> {days_left}\n\n"
            text += "🔑 Ваши ключи остались прежними (UUID не изменился)"
            
            await m.reply(text, reply_markup=back_kb)
            logger.info(f"[PROMO] {result['code']} продлил подписку: +{result['days']} дн. TG:{m.from_user.id}")
        else:
            await m.reply(
                f"❌ Ошибка при продлении подписки.\n\n"
                f"Обратитесь в поддержку: @ExVPNsupport",
                reply_markup=back_kb
            )
    
    await state.clear()


# === СТАРТ ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    register_user_for_broadcast(user_id)
    await send_newyear_welcome(message, user_id)


# === РЕФЕРАЛЬНАЯ ===
@dp.callback_query(F.data == "referral_program")
async def referral_program(c: types.CallbackQuery):
    uid = str(c.from_user.id)
    refs = users_data['referrals'].get(uid, [])
    paid_refs = sum(1 for ref in refs if user_data.get(ref, {}).get("tariff") != "dual_server")
    bonus_days = paid_refs * 7
    ref_link = f"https://t.me/VPnEX_testbot?start=ref_{uid}"
    text = (
        f"<b>Реферальная программа</b>\n\n"
        f"Приглашай — <b>7 дней бесплатно</b> за каждого оплатившего!\n\n"
        f"Твоя ссылка:\n{hcode(ref_link)}\n\n"
        f"<b>Статистика:</b>\n"
        f"• Приглашено: <b>{len(refs)}</b>\n"
        f"• Оплатили: <b>{paid_refs}</b>\n"
        f"• Бонус: <b>{bonus_days} дней</b>\n"
    )
    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_to_initial")]]))

# === ОПЛАТА ===
# === РАБОЧАЯ КНОПКА "КУПИТЬ VPN" ===
@dp.callback_query(F.data == "buy_vpn")
async def buy_vpn_menu(c: types.CallbackQuery):
    text = "🎄 <b>Выберите тариф</b> 🎄\n\n"
    text += "💎 <b>Что входит:</b>\n"
    text += "• 🇳🇱 🇩🇪 🇺🇸 Три страны\n"
    text += "• ⚡️ VLESS Reality + Vision\n"
    text += "• 🛡 100% обход блокировок\n"
    text += "• 💬 Поддержка 24/7\n\n"
    text += "⭐ <b>ОПЛАТА ЗВЁЗДАМИ ИЛИ РУБЛЯМИ</b>"

    kb = get_tariffs_keyboard(is_extension=False)
    kb.inline_keyboard.insert(4, [InlineKeyboardButton(
        text="🎁 Смотреть рекламу (бесплатный день)",
        web_app=WebAppInfo(url="https://miniapp.exvpn.info/")
    )])

    await c.message.edit_text(text, reply_markup=kb)


# === ВЫБОР СПОСОБА ОПЛАТЫ (Stars/Rukassa/YooMoney) ===
@dp.callback_query(F.data.startswith("buy_"))
async def select_payment_method(c: types.CallbackQuery):
    """
    Показывает меню выбора способа оплаты
    """
    period = c.data.replace("buy_", "")
    
    if period == "vpn":
        # Если пришло "buy_vpn" — показываем список тарифов
        text = "💳 <b>Выберите тариф</b>\n\n"
        text += "⭐️ Telegram Stars\n"
        text += "💳 Rukassa (крипто)\n"
        text += "💳 ЮKassa (карты/СБП)\n"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 месяц", callback_data="buy_30")],
            [InlineKeyboardButton(text="3 месяца", callback_data="buy_90")],
            [InlineKeyboardButton(text="6 месяцев", callback_data="buy_180")],
            [InlineKeyboardButton(text="12 месяцев", callback_data="buy_360")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_initial")],
        ])
        await c.message.edit_text(text, reply_markup=kb)
        return
    
    tariffs = {
        "30": {"days": 30, "stars": 48, "rub": 90},
        "90": {"days": 90, "stars": 136, "rub": 256},
        "180": {"days": 180, "stars": 266, "rub": 502},
        "360": {"days": 360, "stars": 515, "rub": 972},
    }
    
    if period not in tariffs:
        return await c.answer("❌ Неверный тариф", show_alert=True)
    
    tariff = tariffs[period]
    days = tariff["days"]
    stars = tariff["stars"]
    rub = tariff["rub"]
    
    period_name = "1 месяц" if days == 30 else f"{days//30} месяца" if days in [90, 180] else f"{days//30} месяцев"
    
    text = (
        f"💳 <b>Выберите способ оплаты</b>\n\n"
        f"📦 Тариф: <b>{period_name} ({days} дней)</b>\n\n"
        f"⭐️ <b>Telegram Stars:</b> {stars} ⭐\n"
        f"   Быстрая оплата\n\n"
        f"🔵 <b>Rukassa:</b> {rub}₽\n"
        f"   Криптовалюта\n\n"
        f"🟡 <b>YooMoney:</b> {rub}₽\n"
        f"   Карты, СБП, кошелёк"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐️ Stars ({stars} ⭐)",
            callback_data=f"pay_stars_{period}"
        )],
        [InlineKeyboardButton(
            text=f"🔵 Rukassa ({rub}₽)",
            callback_data=f"pay_rub_{period}"
        )],
        [InlineKeyboardButton(
            text=f"💳 ЮKassa ({rub}₽)",
            callback_data=f"pay_yookassa_{period}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_vpn")]
    ])
    
    await c.message.edit_text(text, reply_markup=kb)
    await c.answer()

# === ВЫБОР ТАРИФА И ОТПРАВКА ИНВОЙСА ===
@dp.callback_query(F.data.startswith(("pay_rub_", "pay_stars_")))
async def payment_handler(c: types.CallbackQuery):
    uid = str(c.from_user.id)

    # === ОПЛАТА РУБЛЯМИ ЧЕРЕЗ ПРОВАЙДЕРА ===
    if c.data.startswith("pay_rub_"):
        period = c.data.split("_")[-1]
        tariffs = {
            "30": {"days": 30, "price": 90},
            "90": {"days": 90, "price": 256},
            "180": {"days": 180, "price": 502},
            "360": {"days": 360, "price": 972},
        }
        tariff = tariffs[period]
        
        # Создаем платеж через Rukassa
        payment = await create_rukassa_payment(
            user_id=c.from_user.id,
            amount=tariff["price"],
            days=tariff["days"]
        )
        
        if payment.get("success"):
            # Сохраняем pending платеж
            user_data.setdefault(uid, {
                "vless_links": {"n": "", "g": "", "u": ""},
                "tariff": "dual_server",
                "referrer": None
            })
            user_data[uid]["pending_payment"] = {
                "order_id": payment["order_id"],
                "days": tariff["days"],
                "amount": tariff["price"],
                "timestamp": int(time.time())
            }
            save_user_data(user_data)
            
            # Отправляем ссылку на оплату
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить {tariff['price']}₽",
                    url=payment["url"]
                )],
                [InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"check_ruk_{payment['order_id']}"
                )],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_vpn")]
            ])
            
            await c.message.answer(
                f"💳 <b>Оплата {tariff['days']} дней</b>\n\n"
                f"💰 Сумма: <b>{tariff['price']}₽</b>\n\n"
                f"1️⃣ Нажмите \"💳 Оплатить\"\n"
                f"2️⃣ Оплатите через СБП\n"
                f"3️⃣ Нажмите \"✅ Я оплатил\"\n\n"
                f"🆔 Заказ: <code>{payment['order_id']}</code>",
                reply_markup=kb
            )
            await c.answer()
        else:
            await c.answer("❌ Ошибка создания платежа", show_alert=True)
        
        return  # ← ВАЖНО! Выходим здесь


    # === ОПЛАТА ЗВЁЗДАМИ ЧЕРЕЗ TELEGRAM STARS (XTR) ===
    if c.data.startswith("pay_stars_"):
        period = c.data.split("_")[-1]  # 30, 90, 180, 360
        tariffs = {
            "30": {"days": 30, "stars": 48},
            "90": {"days": 90, "stars": 136},
            "180": {"days": 180, "stars": 266},
            "360": {"days": 360, "stars": 515},
        }
        tariff = tariffs[period]

        # ВАЖНО: НИКАКИХ проверок user["stars"] — баланс хранит Telegram
        await bot.send_invoice(
            chat_id=c.from_user.id,
            title=f"ExVPN+ • {tariff['days']} дней",
            description="🇳🇱 🇩🇪 🇺🇸 Доступ ко всем серверам\n⚡️ VLESS Reality + Vision\n🛡 Обход блокировок • Поддержка 24/7",
            payload=f"vpn_stars_{tariff['days']}_{c.from_user.id}",  # новый формат: vpn_stars_{days}_{user}
            provider_token="",       # для Stars токен должен быть ПУСТОЙ, а поле вообще можно не передавать[web:13][web:35]
            currency="XTR",          # валюта Stars[web:4][web:26]
            prices=[LabeledPrice(label=f"{tariff['days']} дней", amount=tariff['stars'])],
            start_parameter="buy_vpn",
            need_name=False,
            need_phone_number=False,
            need_shipping_address=False,
            is_flexible=False,
        )

        await c.answer("⭐ Счёт в звёздах выставлен ↓")


# === ПРЕДПРОВЕРКА ===
@dp.pre_checkout_query()
async def pre_checkout_query(query: types.PreCheckoutQuery):
    """
    Telegram требует ответ в течение 10 секунд
    ПРОВАЙДЕР заблокирует платёж если не ответить
    """
    logger.info(f"📍 PRE-CHECKOUT | TG:{query.from_user.id} | Payload:{query.invoice_payload}")
    try:
        await bot.answer_pre_checkout_query(query.id, ok=True)
        logger.info(f"✅ PRE-CHECKOUT OK | TG:{query.from_user.id}")
    except Exception as e:
        logger.error(f"❌ PRE-CHECKOUT ERROR | TG:{query.from_user.id} | Error: {e}")
        try:
            await bot.answer_pre_checkout_query(
                query.id, 
                ok=False, 
                error_message=str(e)[:100]
            )
        except:
            pass

# === УСПЕШНАЯ ОПЛАТА (ГЛАВНОЕ!) ===
@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """
    Обработчик успешной оплаты через Telegram Stars.
    Автоматически продлевает существующую подписку или создаёт новую.
    """
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    user_id_str = str(user_id)
    
    logger.info(f"[PAYMENT] Успешная оплата! TG:{user_id} Payload:{payload}")
    
    # === ПАРСИНГ PAYLOAD ===
    if not payload.startswith("vpn_"):
        logger.warning(f"[PAYMENT] Неверный payload: {payload}")
        await message.answer("❌ Ошибка обработки платежа. Обратитесь в поддержку: @ExVPNsupport")
        return
    
    parts = payload.split("_")
    try:
        if "stars" in payload:
            # Формат: vpn_stars_30_123456789
            days = int(parts[2])
            parsed_user_id = int(parts[3])
            currency = "XTR"
            logger.info(f"[PAYMENT] STARS оплата: {days} дней для TG:{parsed_user_id} (Stars)")
        else:
            # Формат: vpn_1_123456789 (где 1 = месяцы)
            months = int(parts[1])
            parsed_user_id = int(parts[2])
            days = months * 30
            currency = "RUB"
            logger.info(f"[PAYMENT] RUB оплата: {months} месяцев = {days} дней для TG:{parsed_user_id}")
    except (ValueError, IndexError) as e:
        logger.error(f"[PAYMENT] Ошибка парсинга payload: {payload} | Error: {e}")
        await message.answer("❌ Ошибка обработки платежа. Обратитесь в поддержку: @ExVPNsupport")
        return
    
    # === ПРОВЕРЯЕМ СТАТУС VPN У ПОЛЬЗОВАТЕЛЯ ===
    status = vpn.get_client_status(parsed_user_id)
    has_subscription = False
    
    for sid in vpn.servers:
        if status[sid]['activ'] in ['Активен', 'Infinity']:
            has_subscription = True
            logger.info(f"✅ У пользователя TG:{parsed_user_id} есть активная подписка на {sid}")
            break
    
    # === ЕСЛИ ЕСТЬ ПОДПИСКА → ПРОДЛЕВАЕМ ===
    if has_subscription:
        logger.info(f"[PAYMENT] Продление подписки TG:{parsed_user_id} на {days} дней")
        success, links, days_left = vpn.extend_vless(parsed_user_id, days)
        
        if success:
            expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days_left)
            
            text = f"✅ <b>Оплата успешна!</b>\n\n"
            text += f"🎁 Подписка продлена на <b>+{days} дней</b>\n"
            text += f"📅 Действует до: {expiry_date.strftime('%d.%m.%Y')}\n\n"
            text += f"⏳ Осталось дней: {days_left}"
            
            await message.answer(text, reply_markup=get_initial_keyboard(user_id_str))
        else:
            await message.answer("❌ Ошибка продления. Обратитесь в поддержку: @ExVPNsupport")
    
    # === ЕСЛИ ПОДПИСКИ НЕТ → СОЗДАЁМ НОВУЮ ===
    else:
        logger.info(f"[PAYMENT] Создание новой подписки TG:{parsed_user_id} на {days} дней")
        success, results, days_left = vpn.sync_and_issue_vless(parsed_user_id, days=days)
        
        if success:
            expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
            
            text = f"🎉 <b>Оплата успешна!</b>\n\n"
            text += f"🎁 Вы получили <b>{days} дней</b> доступа\n"
            text += f"📅 Действует до: {expiry_date.strftime('%d.%m.%Y')}\n\n"
            text += "<b>🔑 Ваши ключи:</b>\n\n"
            
            for sid, link in results.items():
                if isinstance(link, str) and link.startswith("vless://"):
                    first_link = link.split("\n\n")[0] if "\n\n" in link else link
                    text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
            
            text += "📱 <i>Используйте приложения:</i>\n"
            text += "• Nekobox (Android/iOS)\n"
            text += "• v2rayNG (Android)\n"
            text += "• Streisand (iOS)"
            
            await message.answer(text, reply_markup=get_initial_keyboard(user_id_str))
        else:
            await message.answer("❌ Ошибка активации. Обратитесь в поддержку: @ExVPNsupport")


@dp.callback_query(F.data.startswith("check_ruk_"))
async def check_rukassa_payment(c: types.CallbackQuery):
    order_id = c.data.replace("check_ruk_", "")
    uid = str(c.from_user.id)
    
    pending = user_data.get(uid, {}).get("pending_payment", {})
    if pending.get("order_id") != order_id:
        await c.answer("❌ Платеж не найден", show_alert=True)
        return
    
    await c.answer("⏳ Проверяем...", show_alert=False)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{RUKASSA_API_URL}/check",
                json={"shop_id": RUKASSA_SHOP_ID, "order_id": order_id}
            ) as response:
                status = await response.json()
    except:
        await c.answer("❌ Ошибка проверки", show_alert=True)
        return
    
    if status.get("status") == "PAID":
        days = pending["days"]
        success, results, _ = vpn.sync_and_issue_vless(c.from_user.id, days=days)
        
        if success:
            del user_data[uid]["pending_payment"]
            save_user_data(user_data)
            
            await c.message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Подписка на {days} дней активирована.\n"
                f"Используйте /start"
            )
        else:
            await c.answer("❌ Ошибка активации", show_alert=True)
    elif status.get("status") == "WAITING":
        await c.answer("⏳ Оплата не поступила", show_alert=True)
    else:
        await c.answer("❌ Платеж отменен", show_alert=True)

# === YOOKASSA API ===
def init_yookassa():
    """Инициализация YooKassa при старте бота"""
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    logger.info("[YOOKASSA] Конфигурация установлена")

async def create_yookassa_payment(user_id: int, amount: float, days: int) -> dict:
    """
    Создание платежа через YooKassa API с чеком
    """
    try:
        order_id = f"vpn_{user_id}_{int(time.time())}"
        idempotence_key = str(uuidlib.uuid4())
        
        logger.info(f"[YOOKASSA] Создание платежа: {order_id}, сумма: {amount}₽")
        
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/VPnEXtest_bot"
            },
            "capture": True,
            "description": f"Оплата VPN подписки на {days} дней",
            "metadata": {
                "user_id": user_id,
                "days": days,
                "order_id": order_id
            },
            # ✅ ДОБАВЛЯЕМ ЧЕК (обязательно для РФ!)
            "receipt": {
                "customer": {
                    "email": f"{user_id}@telegram.user"  # Email для чека
                },
                "items": [
                    {
                        "description": f"VPN подписка ExVPN на {days} дней",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1,  # НДС не облагается
                        "payment_mode": "full_prepayment",  # Полная предоплата
                        "payment_subject": "service"  # Услуга
                    }
                ]
            }
        }, idempotence_key)
        
        logger.info(f"[YOOKASSA] Платеж создан! ID: {payment.id}")
        
        return {
            "success": True,
            "url": payment.confirmation.confirmation_url,
            "order_id": order_id,
            "payment_id": payment.id
        }
        
    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def check_yookassa_payment(payment_id: str) -> dict:
    """Проверка статуса платежа YooKassa"""
    try:
        payment = Payment.find_one(payment_id)
        logger.info(f"[YOOKASSA] Проверка {payment_id}: {payment.status}")
        
        if payment.status == "succeeded":
            return {
                "status": "PAID",
                "amount": float(payment.amount.value),
                "payment_id": payment.id
            }
        elif payment.status in ["pending", "waiting_for_capture"]:
            return {"status": "WAITING"}
        else:
            return {"status": "FAILED"}
            
    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка: {e}")
        return {"status": "ERROR", "message": str(e)}

# === МОЙ VPN ===
@dp.callback_query(F.data == "my_vpn")
async def my_vpn(c: types.CallbackQuery):
    user_id = str(c.from_user.id)
    status = vpn.get_client_status(int(user_id))
    
    # ✅ ПРОВЕРЯЕМ, ЕСТЬ ЛИ ХОТЯ БЫ ОДИН АКТИВНЫЙ КЛИЕНТ
    has_any_client = False
    for sid in vpn.servers:
        s = status[sid]
        if s['activ'] == "Активен":
            has_any_client = True
            break
    
    # ❌ ЕСЛИ НЕТ НИ ОДНОГО АКТИВНОГО — НЕ ПОКАЗЫВАЕМ ССЫЛКИ!
    if not has_any_client:
        text = "🎄 <b>Мой VPN</b>\n\n"
        text += "❌ <b>У вас нет активной подписки</b>\n\n"
        text += "🎁 Чтобы получить доступ к VPN, выберите тариф:"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить VPN", callback_data="buy_vpn")],
            [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_initial")],
        ])
        
        try:
            await c.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "not modified" not in str(e).lower():
                logger.error(f"[MY_VPN] edit_text error: {e}")
        return
    
    # ✅ ЕСЛИ ЕСТЬ АКТИВНЫЕ КЛИЕНТЫ — ПОКАЗЫВАЕМ КНОПКИ СТРАН
    text = "🎄✨ <b>Мой VPN</b> ✨🎄\n\n"
    
    # Получаем дату окончания подписки (максимальную среди всех серверов)
    max_expiry = 0
    
    for sid in vpn.servers:
        s = status[sid]
        if s['activ'] == "Активен":
            # Ищем максимальный expiry_time
            inbound_ids = vpn.servers[sid]["inbounds"]
            for inbound_id in inbound_ids:
                client, found_inbound = vpn._find_client_by_email(int(user_id), sid, inbound_id)
                if client:
                    expiry = getattr(client, 'expiry_time', 0) or 0
                    if expiry > max_expiry:
                        max_expiry = expiry
    
    # Показываем дату окончания подписки
    if max_expiry > 0:
        expiry_date = datetime.datetime.fromtimestamp(max_expiry / 1000, datetime.timezone.utc)
        now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        days_left = (max_expiry - now_ms) // (86400 * 1000)
        
        if days_left > 1:
            text += f"📅 <b>Подписка действует до:</b> {expiry_date.strftime('%d.%m.%Y')}\n"
            text += f"⏳ <b>Осталось дней:</b> {days_left}\n\n"
        elif days_left == 1:
            text += f"📅 <b>Подписка действует до:</b> {expiry_date.strftime('%d.%m.%Y')}\n"
            text += f"⚠️ <b>Осталось: 1 день!</b>\n\n"
        else:
            text += f"🔴 <b>Подписка истекает сегодня!</b>\n\n"
    elif max_expiry == 0:
        text += "♾️ <b>Бессрочная подписка</b>\n\n"
    
    text += "🌍 <b>Выберите страну для просмотра ключей:</b>"
    
    # 🎄 КНОПКИ СТРАН
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇳🇱 Нидерланды", callback_data="show_server_n")],
        [InlineKeyboardButton(text="🇩🇪 Германия", callback_data="show_server_g")],
        [InlineKeyboardButton(text="🇺🇸 США", callback_data="show_server_u")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_vpn"),
         InlineKeyboardButton(text="♻️ Пересоздать", callback_data="recreate_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_initial")],
    ])
    
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            logger.error(f"[MY_VPN] edit_text error: {e}")

@dp.callback_query(F.data.startswith("show_server_"))
async def show_server_keys(c: types.CallbackQuery):
    """
    Показывает ключи для выбранной страны.
    Формат: show_server_n / show_server_g / show_server_u
    """
    sid = c.data.split("_")[2]  # n, g или u
    user_id = str(c.from_user.id)
    
    if sid not in vpn.servers:
        await c.answer("❌ Неизвестный сервер", show_alert=True)
        return
    
    # Проверяем статус клиента
    status = vpn.get_client_status(int(user_id))
    s = status[sid]
    
    if s['activ'] != "Активен":
        await c.answer(f"❌ {vpn.servers[sid]['name']}: {s['activ']}", show_alert=True)
        return
    
    # Формируем заголовок
    flag = "🇳🇱" if sid == "n" else "🇩🇪" if sid == "g" else "🇺🇸"
    name = vpn.servers[sid]["name"]
    
    text = f"{flag} <b>{name}</b>\n\n"
    
    # Получаем дату окончания
    inbound_ids = vpn.servers[sid]["inbounds"]
    max_expiry = 0
    
    for inbound_id in inbound_ids:
        client, found_inbound = vpn._find_client_by_email(int(user_id), sid, inbound_id)
        if client:
            expiry = getattr(client, 'expiry_time', 0) or 0
            if expiry > max_expiry:
                max_expiry = expiry
    
    # Показываем срок действия
    if max_expiry > 0:
        expiry_date = datetime.datetime.fromtimestamp(max_expiry / 1000, datetime.timezone.utc)
        now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        days_left = (max_expiry - now_ms) // (86400 * 1000)
        
        text += f"📅 <b>До:</b> {expiry_date.strftime('%d.%m.%Y')}\n"
        text += f"⏳ <b>Осталось:</b> {days_left} дн.\n\n"
    elif max_expiry == 0:
        text += "♾️ <b>Бессрочная подписка</b>\n\n"
    
    # Получаем ВСЕ ключи (TCP и xhttp)
    links = {"tcp": [], "xhttp": []}
    
    for inbound_id in inbound_ids:
        client, found_inbound = vpn._find_client_by_email(int(user_id), sid, inbound_id)
        
        if client:
            try:
                link = vpn._generate_vless_link_from_inbound(
                    sid, 
                    client.id, 
                    client.email, 
                    inbound_id=found_inbound
                )
                
                if link:
                    # Определяем тип транспорта
                    cache_key = (sid, found_inbound)
                    settings = vpn.inbound_cache.get(cache_key, {})
                    transport = settings.get("transport", "tcp")
                    
                    if transport == "tcp":
                        links["tcp"].append(link)
                    elif transport in ["xhttp", "splithttp"]:
                        links["xhttp"].append(link)
                    else:
                        links["tcp"].append(link)  # fallback
            except Exception as e:
                logger.error(f"[SHOW_SERVER] Ошибка генерации ссылки для {sid} inbound#{inbound_id}: {e}")
    
    # Показываем ключи
    if links["tcp"]:
        text += "🔵 <b>TLS (Vision):</b>\n"
        for link in links["tcp"]:
            text += f"{hcode(link)}\n"
        text += "\n"
    
    if links["xhttp"]:
        text += "🟣 <b>xhttp:</b>\n"
        for link in links["xhttp"]:
            text += f"{hcode(link)}\n"
        text += "\n"
    
    if not links["tcp"] and not links["xhttp"]:
        text += "❌ <b>Нет доступных ключей</b>\n\n"
    
    text += "📱 <i>Используйте приложения:</i>\n"
    text += "• Nekobox (PC)\n"
    text += "• v2rayNG (Android/iOS)"
    
    # Кнопка "Назад"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К списку стран", callback_data="my_vpn")],
    ])
    
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            logger.error(f"[SHOW_SERVER] edit_text error: {e}")

# === ПЕРЕСОЗДАНИЕ ===
@dp.callback_query(F.data == "recreate_all")
async def recreate_all(c: types.CallbackQuery):
    user_id = str(c.from_user.id)

    # ✅ МОМЕНТАЛЬНЫЙ ОТВЕТ, ЧТОБЫ НЕ ПРОТУХ CALLBACK
    await c.answer("🔄 Проверяем статус подписки...", show_alert=False)

    # ✅ ПРОВЕРЯЕМ, ЕСТЬ ЛИ ХОТЯ БЫ ОДИН АКТИВНЫЙ КЛИЕНТ
    status = vpn.get_client_status(int(user_id))
    has_any_client = False
    for sid in vpn.servers:
        s = status[sid]
        if s['activ'] == "Активен":
            has_any_client = True
            break

    if not has_any_client:
        text = "❌ <b>Пересоздать ключи</b>\n\n"
        text += "У вас нет активной подписки!\n"
        text += "Сначала оплатите тариф или введите промокод.\n\n"
        text += "💳 <b>Выберите действие:</b>"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить VPN", callback_data="buy_vpn")],
            [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_initial")],
        ])

        await c.message.edit_text(text, reply_markup=kb)
        return

    # ✅ СООБЩАЕМ, ЧТО НАЧАЛОСЬ ПЕРЕСОЗДАНИЕ (ЧЕРЕЗ СООБЩЕНИЕ, НЕ ЧЕРЕЗ answer)
    await c.message.answer("🔄 Пересоздаём ключи, подождите...")

    # ✅ ПЕРЕСОЗДАЁМ БЕЗ ДОБАВКИ ДНЕЙ (используем старый expiry_time)
    success, results, _ = vpn.recreate_without_adding_days(c.from_user.id)

    if success:
        # тут УЖЕ НЕ ИСПОЛЬЗУЕМ c.answer, только сообщения
        await c.message.answer("✅ Ключи пересозданы!")
        await my_vpn(c)  # редирект на "Мой VPN"
    else:
        text = f"❌ <b>Ошибка пересоздания:</b>\n\n<pre>{results}</pre>"
        await c.message.edit_text(text, reply_markup=get_initial_keyboard(user_id))


# === АДМИНКА: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===
# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ — ВСЕ ЗАГЛУШКИ ЗАМЕНЕНЫ НА РАБОЧИЕ ФУНКЦИИ ===

@dp.callback_query(F.data == "user_management")
async def user_management_menu(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)
    await c.answer()
    await c.message.edit_text(
        "<b>Управление пользователями</b>\n\n"
        "Выберите действие:",
        reply_markup=get_user_management_keyboard()
    )


# ——— УДАЛЕНИЕ ПО TG ID ———
@dp.callback_query(F.data == "delete_by_tgid")
async def delete_by_tgid_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    await state.set_state(Form.waiting_for_tgid_check)
    await c.message.edit_text(
        "Введите Telegram ID пользователя для <b>удаления</b> его аккаунтов на всех серверах:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="user_management")]])
    )

@dp.message(Form.waiting_for_tgid_check)
async def delete_by_tgid_confirm(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID:
        await state.clear()
        return
    
    try:
        tg_id = int(m.text.strip())
    except:
        return await m.reply("❌ Неверный TG ID")
    
    # Удаляем со ВСЕХ серверов и ВСЕХ inbound
    success, results, _ = vpn.sync_and_issue_vless(tg_id, delete_mode=True)
    
    if success:
        text = f"✅ Пользователь <code>{tg_id}</code> удалён:\n\n"
        for sid, res in results.items():
            text += f"• {vpn.servers[sid]['name']}: {res}\n"
        
        # Очищаем user_data.json
        uid = str(tg_id)
        if uid in user_data:
            user_data[uid]["vless_links"] = {"n": "", "g": "", "u": ""}
            save_json("user_data.json", user_data)
    else:
        text = f"❌ Ошибка: {results}"
    
    await m.reply(text, reply_markup=get_user_management_keyboard())
    await state.clear()



# ——— ПРОДЛЕНИЕ ПО TG ID ———
@dp.callback_query(F.data == "extend_by_tgid")
async def extend_by_tgid_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    await state.set_state(Form.waiting_for_tgid_check)
    await c.message.edit_text(
        "Введите Telegram ID и через пробел количество дней для продления\n"
        "Пример: <code>123456789 30</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="user_management")]])
    )

@dp.message(Form.waiting_for_tgid_check)
async def extend_by_tgid_process(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID:
        await state.clear()
        return

    parts = m.text.strip().split()
    if len(parts) != 2:
        return await m.reply("Формат: TG_ID дни")

    try:
        tg_id = int(parts[0])
        days = int(parts[1])
        if days <= 0: raise ValueError
    except:
        return await m.reply("Ошибка в данных")

    success, results, days_left = vpn.extend_vless(tg_id, days)

    if success:
        text = f"Успешно продлено +{days} дней пользователю <code>{tg_id}</code>\n\n"
        for sid, link in results.items():
            if link and link.startswith("vless://"):
                text += f"<b>{vpn.servers[sid]['name']}:</b>\n{hcode(link)}\n\n"
        text += f"Осталось дней: <b>{days_left}</b>"
    else:
        text = f"Ошибка продления: {results}"

    await m.reply(text, reply_markup=get_user_management_keyboard())
    await state.clear()


# ——— КОПИРОВАНИЕ НА ДРУГОЙ СЕРВЕР (уже было в прошлом ответе) ———
@dp.callback_query(F.data == "copy_to_server")
async def copy_to_server_menu(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)

    await c.answer()
    kb = [
        [InlineKeyboardButton(text="NL → DE (все активные)", callback_data="copy_n_to_g")],
        [InlineKeyboardButton(text="DE → NL (все активные)", callback_data="copy_g_to_n")],
        [InlineKeyboardButton(text="Назад", callback_data="user_management")],
    ]
    await c.message.edit_text(
        "<b>Копирование пользователей между серверами</b>\n\n"
        "Выберите направление:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("copy_"))
async def perform_copy(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID: return

    mapping = {
        "copy_n_to_g": ("n", "g"),
        "copy_g_to_n": ("g", "n"),
    }
    direction = c.data
    if direction not in mapping:
        await c.message.edit_text("Неизвестное направление", reply_markup=get_user_management_keyboard())
        return

    from_sid, to_sid = mapping[direction]
    await c.message.edit_text(f"Копирую активных пользователей\n{vpn.servers[from_sid]['name']} → {vpn.servers[to_sid]['name']}\n\nНачинаю...")

    active_tg_ids = vpn.get_all_active_clients(from_sid)
    if not active_tg_ids:
        await c.message.edit_text("Нет активных пользователей на исходном сервере.", reply_markup=get_user_management_keyboard())
        return

    success, result = vpn.copy_clients_between_servers(from_sid, to_sid, user_filter=active_tg_ids)

    text = f"<b>Копирование завершено</b>\n\n{result}\n\n"
    text += f"Откуда: <b>{vpn.servers[from_sid]['name']}</b>\n"
    text += f"Куда:   <b>{vpn.servers[to_sid]['name']}</b>\n"
    text += f"Всего активных: <b>{len(active_tg_ids)}</b>"

    await c.message.edit_text(text, reply_markup=get_user_management_keyboard())


# ——— ПОЛНОЕ УДАЛЕНИЕ (из всех inbound + из user_data.json) ———
@dp.callback_query(F.data == "delete_full")
async def delete_full_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    await state.set_state(Form.waiting_for_tgid_check)
    await c.message.edit_text(
        "Введите TG ID для <b>полного удаления</b> (все серверы + запись в user_data.json):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="user_management")]])
    )

@dp.message(Form.waiting_for_tgid_check)
async def delete_full_process(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID:
        await state.clear()
        return
    try:
        tg_id = int(m.text.strip())
    except:
        return await m.reply("Некорректный ID")

    # Удаляем с серверов
    vpn.sync_and_issue_vless(tg_id, delete_mode=True)
    # Удаляем из базы
    uid = str(tg_id)
    user_data.pop(uid, None)
    save_json("user_data.json", user_data)

    await m.reply(f"Пользователь {tg_id} полностью удалён из всех серверов и базы данных.", 
                  reply_markup=get_user_management_keyboard())
    await state.clear()


# ——— ЭКСПОРТ INBOUND В ФАЙЛ ———
@dp.callback_query(F.data == "export_inbound_menu")
async def export_inbound_menu(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID: return
    await c.answer()
    kb = [
        [InlineKeyboardButton(text="Netherlands", callback_data="export_n")],
        [InlineKeyboardButton(text="Germany", callback_data="export_g")],
        [InlineKeyboardButton(text="Назад", callback_data="user_management")],
    ]
    await c.message.edit_text("Выберите сервер для экспорта inbound в файл:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("export_"))
async def export_inbound(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID: return
    sid = c.data.split("_")[-1]
    if sid not in vpn.apis:
        return await c.message.edit_text("Сервер недоступен")

    try:
        inbound = vpn.apis[sid].inbound.get_by_id(1)
        clients = getattr(inbound.settings, 'clients', [])
        lines = []
        for client in clients:
            email = getattr(client, 'email', '')
            if "_" in email:
                tg_id = email.split("_")[0]
                exp = getattr(client, 'expiry_time', 0) or 0
                exp_str = "∞" if exp == 0 else datetime.datetime.fromtimestamp(exp/1000, datetime.timezone.utc).strftime('%d.%m.%Y')
                lines.append(f"{tg_id} | {exp_str} | {client.id}")
        
        text = "\n".join(lines) if lines else "Пусто"
        filename = f"inbound_{vpn.servers[sid]['name']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)
        
        await bot.send_document(c.from_user.id, types.FSInputFile(filename),
                               caption=f"Экспорт inbound {vpn.servers[sid]['name']}\nВсего: {len(lines)}")
        os.remove(filename)
    except Exception as e:
        await c.message.edit_text(f"Ошибка экспорта: {e}")

    await c.message.edit_reply_markup(reply_markup=get_user_management_keyboard())

@dp.callback_query(F.data.in_({"delete_by_tgid", "extend_by_tgid", "copy_to_server", "delete_full", "export_inbound_menu", "delete_by_category_menu"}))
async def user_management_stub(c: types.CallbackQuery):
    action = {
        "delete_by_tgid": "Удаление по TG ID",
        "extend_by_tgid": "Продление по TG ID",
        "copy_to_server": "Копирование на сервер",
        "delete_full": "Полное удаление",
        "export_inbound_menu": "Экспорт в файл",
        "delete_by_category_menu": "Удаление по категории"
    }[c.data]
    await c.answer()
    await c.message.edit_text(
        f"<b>{action}</b>\n\n"
        "Функция в разработке.\n"
        "Скоро будет доступна.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="user_management")]
        ])
    )

# === АДМИНКА: ВЫДАЧА VLESS ===
@dp.callback_query(F.data == "admin_issue_vless")
async def admin_issue_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа")
    await state.set_state(Form.waiting_for_tgid)
    await c.message.delete()
    await bot.send_message(c.from_user.id, "Введите Telegram ID:\n\n/cancel — отмена", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_admin")]]))

@dp.message(Form.waiting_for_tgid)
async def admin_issue_tgid(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    try:
        tg_id = int(m.text.strip())
        if tg_id <= 0: raise ValueError
        await state.update_data(tg_id=tg_id)
        await state.set_state(Form.waiting_for_days)
        await m.reply(
            "Сколько дней?\n\n"
            "• `30` — 30 дней\n"
            "• `0` — пересоздать\n"
            "• `00` — бесконечность\n"
            "• `-1` — удалить\n"
            "• `29.03.2026` — до даты\n\n"
            "/cancel — отмена",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_admin")]])
        )
    except:
        await m.reply("Ошибка: введите ID")

@dp.message(Command("reload_inbound"))
async def reload_inbound(m: types.Message):
    if str(m.from_user.id) != ADMIN_ID: return
    vpn._auto_load_all_inbound_settings()
    await m.reply("Настройки inbound обновлены!")

@dp.message(Form.waiting_for_days)
async def admin_issue_days(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    try:
        text = m.text.strip()
        days = None
        delete_mode = False
        recreate_mode = False
        expiry_time = None

        date_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', text)
        if date_match:
            d, month, y = map(int, date_match.groups())
            target_date = datetime.datetime(y, month, d, tzinfo=datetime.timezone.utc)
            expiry_time = int(target_date.timestamp() * 1000)
            await state.update_data(expiry_time=expiry_time)
            await state.set_state(Form.waiting_for_server)
            kb = [[InlineKeyboardButton(text=vpn.servers[s]["name"], callback_data=f"issue_srv_{s}")] for s in vpn.servers]
            kb.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_admin")])
            await m.reply(f"Выдать до <b>{target_date.strftime('%d.%m.%Y')}</b>\nВыберите сервер:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            return

        if text == "00":
            days = 0
        elif text == "0":
            recreate_mode = True
        elif text == "-1":
            delete_mode = True
        else:
            days = int(text)
            if days <= 0:
                raise ValueError

        await state.update_data(days=days, delete_mode=delete_mode, recreate_mode=recreate_mode, expiry_time=expiry_time)
        await state.set_state(Form.waiting_for_server)
        kb = [[InlineKeyboardButton(text=vpn.servers[s]["name"], callback_data=f"issue_srv_{s}")] for s in vpn.servers]
        kb.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_admin")])

        if delete_mode:
            msg = "<b>УДАЛЕНИЕ VLESS</b>"
        elif recreate_mode:
            msg = "<b>ПЕРЕСОЗДАТЬ VLESS</b>"
        elif days == 0:
            msg = "<b>БЕСКОНЕЧНОСТЬ</b>"
        else:
            msg = f"Выдать на <b>{days} дней</b>"

        await m.reply(f"{msg}\nВыберите сервер:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    except:
        await m.reply("Ошибка ввода! Примеры: 30, 00, 0, -1, 29.03.2026")

@dp.callback_query(F.data == "cancel_admin")
async def cancel_admin(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Отменено.", reply_markup=get_admin_keyboard())

@dp.message(Command("cancel"))
async def cancel_fsm(m: types.Message, state: FSMContext):
    await state.clear()
    await m.reply("Отменено.", reply_markup=get_initial_keyboard(str(m.from_user.id)))

@dp.callback_query(F.data.startswith("issue_srv_"))
async def admin_issue_server(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    sid = c.data.split("_")[-1]
    data = await state.get_data()
    tg_id = data["tg_id"]
    days = data.get("days")
    delete_mode = data.get("delete_mode", False)
    recreate_mode = data.get("recreate_mode", False)
    expiry_time = data.get("expiry_time")

    kb = [
        [InlineKeyboardButton(text="Только этот", callback_data=f"issue_confirm_{sid}")],
        [InlineKeyboardButton(text="На всех", callback_data=f"issue_all_{tg_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_admin")]
    ]

    if delete_mode:
        await c.message.edit_text(f"Удалить у `{tg_id}` на **{vpn.servers[sid]['name']}**?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif recreate_mode:
        await c.message.edit_text(f"Пересоздать у `{tg_id}` на **{vpn.servers[sid]['name']}**?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif expiry_time:
        date_str = datetime.datetime.fromtimestamp(expiry_time / 1000).strftime('%d.%m.%Y')
        await c.message.edit_text(f"Выдать до **{date_str}** на **{vpn.servers[sid]['name']}**?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif days == 0:
        await c.message.edit_text(f"Infinity VLESS у `{tg_id}` на **{vpn.servers[sid]['name']}**?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await c.message.edit_text(f"Выдать на <b>{days} дней</b> на **{vpn.servers[sid]['name']}**?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("issue_confirm_"))
async def admin_issue_confirm(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    sid = c.data.split("_")[-1]
    data = await state.get_data()
    tg_id = data["tg_id"]
    days = data.get("days")
    delete_mode = data.get("delete_mode", False)
    recreate_mode = data.get("recreate_mode", False)
    expiry_time = data.get("expiry_time")

    success, results, days_out = vpn.sync_and_issue_vless(
        tg_id, target_server_id=sid, days=days, delete_mode=delete_mode,
        recreate_mode=recreate_mode, expiry_time=expiry_time
    )
    if success:
        link = results.get(sid, "")
        if delete_mode:
            text = f"VLESS удалён на **{vpn.servers[sid]['name']}**"
        elif recreate_mode:
            text = f"VLESS **пересоздан** на **{vpn.servers[sid]['name']}**\n{hcode(link)}"
        elif days == 0:
            text = f"Infinity VLESS выдан на **{vpn.servers[sid]['name']}**\n{hcode(link)}"
        elif expiry_time:
            date_str = datetime.datetime.fromtimestamp(expiry_time / 1000).strftime('%d.%m.%Y')
            text = f"VLESS выдан до **{date_str}**\n{hcode(link)}"
        else:
            text = f"VLESS выдан на **{days} дней**!\n{hcode(link)}"
    else:
        text = f"<b>ОШИБКА:</b> {results}"
    await c.message.edit_text(text, reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data.startswith("issue_all"))
async def admin_issue_all(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID:
        return
    
    tg_id = int(c.data.split("-")[1])
    data = await state.get_data()
    
    days = data.get("days")
    delete_mode = data.get("delete_mode", False)
    recreate_mode = data.get("recreate_mode", False)
    expiry_time = data.get("expiry_time")
    
    # Выдаём на ВСЕ серверы
    success, results, days_out = vpn.sync_and_issue_vless(
        tg_id, 
        days=days, 
        delete_mode=delete_mode, 
        recreate_mode=recreate_mode, 
        expiry_time=expiry_time
    )
    
    if success:
        if delete_mode:
            text = "✅ VLESS удалён со всех серверов!"
        elif recreate_mode:
            text = "✅ VLESS пересозданы на всех серверах!\n\n"
            for sid, link in results.items():
                # Если несколько ссылок — покажем только первую
                first_link = link.split("\n\n")[0] if "\n\n" in link else link
                text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
        elif expiry_time:
            date_str = datetime.datetime.fromtimestamp(expiry_time / 1000).strftime("%d.%m.%Y")
            text = f"✅ VLESS выдан до {date_str}!\n\n"
            for sid, link in results.items():
                first_link = link.split("\n\n")[0] if "\n\n" in link else link
                text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
        elif days == 0:
            text = "✅ Infinity VLESS выдан!\n\n"
            for sid, link in results.items():
                first_link = link.split("\n\n")[0] if "\n\n" in link else link
                text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
        else:
            text = f"✅ VLESS выдан на <b>{days} дней</b>!\n\n"
            for sid, link in results.items():
                first_link = link.split("\n\n")[0] if "\n\n" in link else link
                text += f"<b>{vpn.servers[sid]['name']}</b>\n{hcode(first_link)}\n\n"
            
            # Показываем дату окончания
            expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
            text += f"📅 <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}"
    else:
        text = f"❌ <b>Ошибка:</b> {results}"
    
    await c.message.edit_text(text, reply_markup=get_admin_keyboard())
    await state.clear()


# === REALITY НАСТРОЙКИ ===
@dp.callback_query(F.data == "admin_reality")
async def admin_show_reality(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)

    await c.answer()
    text = "<b>Reality Settings:</b>\n\n"
    updated = False

    for sid, api in vpn.apis.items():
        server_name = vpn.servers[sid]["name"]
        try:
            inbound = api.inbound.get_by_id(1)
            reality = inbound.stream_settings.reality_settings

            # ←←← УНИВЕРСАЛЬНЫЙ ПАРСЕР (2025+ и старые версии)
            if isinstance(reality, dict):
                settings = reality.get("settings", {})
                pbk = settings.get("publicKey") or reality.get("publicKey")
                sni_list = reality.get("serverNames") or settings.get("serverNames", [])
                sid_list = reality.get("shortIds") or settings.get("shortIds", [])
            else:
                settings = getattr(reality, "settings", {}) if hasattr(reality, "settings") else {}
                pbk = settings.get("publicKey", getattr(reality, "publicKey", None))
                sni_list = getattr(reality, "serverNames", []) or settings.get("serverNames", [])
                sid_list = getattr(reality, "shortIds", []) or settings.get("shortIds", [])

            if not pbk:
                raise ValueError("Public Key не найден")

            sni = sni_list[0] if sni_list else "—"
            short_id = sid_list[0] if sid_list else "—"

            text += f"<b>{server_name}:</b>\n"
            text += f"PK: <code>{pbk}</code>\n"
            text += f"SNI: <code>{sni}</code>\n"
            text += f"ShortID: <code>{short_id}</code>\n\n"

            # ←←← Авто-обновление кэша
            cache = vpn.last_known_reality.get(sid, {})
            if cache.get("pbk") != pbk or cache.get("sni") != sni or cache.get("sid") != short_id:
                vpn.last_known_reality[sid] = {"pbk": pbk, "sni": sni, "sid": short_id}
                vpn._save_last_known_reality(sid, pbk, sni_list, sid_list)
                updated = True
                logger.info(f"[REALITY] Кэш обновлён для {server_name}")

        except Exception as e:
            logger.error(f"[REALITY ADMIN] Ошибка {server_name}: {e}")
            text += f"<b>{server_name}:</b> <code>Ошибка получения</code>\n\n"

    if updated:
        text += "\n<i>Кэш Reality автоматически обновлён</i>"

    # ←←← Добавь клавиатуру с выбором сервера (если у тебя её нет)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Netherlands", callback_data="set_reality_n")],
        [InlineKeyboardButton(text="Germany", callback_data="set_reality_g")],
        [InlineKeyboardButton(text="Назад", callback_data="admin")],
    ])

    await c.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("set_reality_"))
async def set_reality_server(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return
    sid = c.data.split("_")[-1]
    await state.update_data(server_id=sid)
    await state.set_state(Form.waiting_for_sni)
    await c.message.edit_text(f"<b>Настройка: {vpn.servers[sid]['name']}</b>\n\nSNI (через запятую):\n<code>google.com</code>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_reality")]]))

@dp.message(Form.waiting_for_sni)
async def set_reality_sni(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    sni = [x.strip() for x in m.text.split(",") if x.strip()]
    if not sni: return await m.reply("Ошибка: введите SNI")
    await state.update_data(sni=sni)
    await state.set_state(Form.waiting_for_shortid)
    await m.reply("ShortID (hex, 6–8):\n<code>a1b2c3</code>")

@dp.message(Form.waiting_for_shortid)
async def set_reality_shortid(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    shortids = [x.strip() for x in m.text.split(",") if x.strip()]
    if not all(6 <= len(s) <= 8 and all(c in "0123456789abcdefABCDEF" for c in s) for s in shortids):
        return await m.reply("Ошибка: 6–8 hex")
    data = await state.get_data()
    sid = data["server_id"]
    sni = data["sni"]
    api = vpn.apis[sid]
    try:
        inbound = api.inbound.get_by_id(1)
        if not hasattr(inbound.stream_settings, "reality_settings"):
            await m.reply("Reality не включён на этом инбаунде!")
            await state.clear()
            return
        
        # ←←← ФИКС: УНИВЕРСАЛЬНАЯ ЛОГИКА ДЛЯ СТАРОЙ/НОВОЙ СТРУКТУРЫ 3x-ui (2025+)
        reality = inbound.stream_settings.reality_settings
        
        # Определяем структуру: dict (новая) или объект с .settings (старая)
        if isinstance(reality, dict):
            # НОВАЯ СТРУКТУРА: прямой dict с ключами 'publicKey', 'serverNames', etc.
            logger.info(f"[REALITY FIX] Новая структура dict на {sid}")
            reality['serverNames'] = sni
            reality['shortIds'] = shortids
        else:
            # СТАРАЯ СТРУКТУРА: объект с .settings (dict внутри)
            if hasattr(reality, 'settings') and isinstance(reality.settings, dict):
                logger.info(f"[REALITY FIX] Старая структура .settings на {sid}")
                reality.settings['serverNames'] = sni
                reality.settings['shortIds'] = shortids
            else:
                # Если ни то, ни другое — fallback на прямые атрибуты
                logger.warning(f"[REALITY FIX] Неизвестная структура на {sid} — используем прямые атрибуты")
                setattr(reality, 'serverNames', sni)
                setattr(reality, 'shortIds', shortids)
        
        # ОБНОВЛЯЕМ Reality на сервере
        api.inbound.update(inbound_id=1, inbound=inbound)
        logger.info(f"[REALITY] Успешно обновлены настройки Reality на сервере {sid}: SNI={sni}, ShortID={shortids}")
        
        await m.reply(
            f"Reality успешно обновлён на сервере <b>{vpn.servers[sid]['name']}</b>!\n\n"
            f"SNI: <code>{', '.join(sni)}</code>\n"
            f"ShortID: <code>{', '.join(shortids)}</code>\n\n"
            f"Пересоздаю VLESS-соединения у <b>всех пользователей</b>..."
        )
        
        # === ВОЛШЕБНАЯ ЧАСТЬ: ПЕРЕСОЗДАНИЕ ВСЕХ КЛИЕНТОВ НА ЭТОМ СЕРВЕРЕ ===
        all_users = [uid for uid in user_data.keys() if uid.isdigit()]
        total = len(all_users)
        success_count = 0
        failed = []
        for i, uid_str in enumerate(all_users, 1):
            tg_id = int(uid_str)
            try:
                # Получаем текущий expiry_time (чтобы не сбросить срок!)
                client = vpn._find_client_by_email(tg_id, sid)
                current_expiry = 0
                if client and hasattr(client, 'expiry_time'):
                    current_expiry = getattr(client, 'expiry_time', 0) or 0
                # Если клиент был включён и срок не истёк — сохраняем его
                now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
                if current_expiry > now:
                    expiry_to_set = current_expiry
                else:
                    expiry_to_set = current_expiry  # fallback: +30 дней
                # Пересоздаём только на нужном сервере с сохранением срока
                ok, results, _ = vpn.sync_and_issue_vless(
                    tg_id=tg_id,
                    target_server_id=sid,
                    expiry_time=expiry_to_set  # ← сохраняем старый срок!
                )
                if ok and isinstance(results.get(sid), str):
                    success_count += 1
                else:
                    failed.append(uid_str)
            except Exception as e:
                logger.error(f"[REALITY SYNC] Ошибка для TG:{tg_id} на {sid}: {e}")
                failed.append(uid_str)
            # Небольшая задержка, чтобы не убить панель
            if i % 10 == 0:
                await asyncio.sleep(1)
        
        summary = (
            f"Готово!\n\n"
            f"Сервер: <b>{vpn.servers[sid]['name']}</b>\n"
            f"Обновлено пользователей: <b>{success_count}/{total}</b>\n"
        )
        if failed:
            summary += f"Не удалось обновить: {len(failed)} чел.\n"
        await m.reply(summary + "\nВсе активные пользователи получили новые VLESS-ссылки с актуальными Reality-настройками!")
        
    except Exception as e:
        logger.error(f"[REALITY] Критическая ошибка при обновлении: {e}", exc_info=True)
        await m.reply(f"Ошибка при обновлении Reality: {e}")
    await state.clear()

# === РАССЫЛКА ===
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(c: types.CallbackQuery, state: FSMContext):
    if str(c.from_user.id) != ADMIN_ID: return await c.answer("Нет доступа")
    await state.set_state(Form.waiting_for_broadcast)
    await c.message.edit_text("Введите текст рассылки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin")]]))

@dp.message(Form.waiting_for_broadcast)
async def admin_broadcast_send(m: types.Message, state: FSMContext):
    if str(m.from_user.id) != ADMIN_ID: return
    text = m.text
    users = users_data['users']
    success = 0
    for uid in users:
        try:
            await bot.send_message(int(uid), text)
            success += 1
        except:
            pass
    await m.reply(f"Рассылка отправлена {success}/{len(users)} пользователям.", reply_markup=get_admin_keyboard())
    await state.clear()

# === INFERNO PANEL ===
@dp.callback_query(F.data == "inferno_panel")
async def inferno_panel(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа")
    await c.message.edit_text("<b>Inferno VPS — Управление</b>", reply_markup=get_inferno_panel())

# === АДМИН ПАНЕЛЬ ===
@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа")
    await c.message.edit_text("Админ-панель", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "back_to_initial")
async def back_to_initial(c: types.CallbackQuery):
    user_id = c.from_user.id
    register_user_for_broadcast(user_id)
    await send_newyear_welcome(c.message, user_id)

@dp.callback_query(F.data == "fix_emails_final")
async def fix_emails_final(c: types.CallbackQuery):
    if str(c.from_user.id) != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)

    await c.answer()
    msg = await c.message.edit_text(
        "Запуск полной чистки email...\n\n"
        "Платные → <code>_n</code> / <code>_g</code>\n"
        "Trial → <code>_trial</code>\n\n"
        "Идёт обработка...",
        reply_markup=None
    )

    total_n = total_g = total_trial = 0
    errors = []

    for sid, server in vpn.servers.items():
        api = vpn.apis.get(sid)
        if not api:
            errors.append(f"{server['name']}: нет API")
            continue

        try:
            inbound = api.inbound.get_by_id(1)
            if not inbound:
                errors.append(f"{server['name']}: нет inbound")
                continue

            # Делаем копию настроек
            settings = inbound.settings
            clients = getattr(settings, "clients", [])

            changed = False
            new_clients = []

            for client in clients:
                old_email = getattr(client, "email", "") or ""
                uuid_str = client.id

                # Уже правильный email — оставляем как есть
                if re.match(r"^\d+_(n|g|trial)$", old_email):
                    new_clients.append(client)
                    continue

                # === Находим TG ID ===
                real_tgid = None
                for uid, data in user_data.items():
                    link_n = data.get("vless_links", {}).get("n", "")
                    link_g = data.get("vless_links", {}).get("g", "")
                    if uuid_str in link_n or uuid_str in link_g:
                        real_tgid = int(uid)
                        break
                if not real_tgid and old_email:
                    m = re.search(r"\d{7,}", old_email)
                    if m:
                        real_tgid = int(m.group(0))

                if not real_tgid:
                    new_clients.append(client)
                    continue

                # === Новый email ===
                if sid == "n":
                    expiry = getattr(client, "expiry_time", 0) or 0
                    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
                    days_left = 99999 if expiry == 0 else (expiry / 1000 - now) / 86400
                    is_trial = days_left <= 3 or "trial" in old_email.lower()
                    new_email = f"{real_tgid}_trial" if is_trial else f"{real_tgid}_n"
                    if is_trial:
                        total_trial += 1
                    else:
                        total_n += 1
                else:
                    new_email = f"{real_tgid}_g"
                    total_g += 1

                # Меняем только email, всё остальное оставляем
                client.email = new_email
                new_clients.append(client)
                changed = True

            # === ЕСЛИ БЫЛИ ИЗМЕНЕНИЯ — ПЕРЕЗАПИСЫВАЕМ ВЕСЬ INBOUND ===
            if changed:
                try:
                    # Полностью заменяем список клиентов
                    settings.clients = new_clients
                    api.inbound.update(inbound_id=1, inbound=inbound)
                    logger.info(f"[FIX_EMAILS] {server['name']}: обновлено {len(new_clients)} клиентов через inbound.update()")
                    await msg.edit_text(
                        msg.text + f"\n\n<b>{server['name']}</b>\n"
                        f"Успешно очищено email у всех клиентов!"
                    )
                except Exception as e:
                    errors.append(f"{server['name']}: {str(e)}")
                    logger.error(f"[FIX_EMAILS] Не удалось перезаписать inbound на {server['name']}: {e}", exc_info=True)
            else:
                await msg.edit_text(msg.text + f"\n\n{server['name']}: всё уже чисто")

            await asyncio.sleep(1.5)

        except Exception as e:
            errors.append(f"{server['name']}: {str(e)}")
            logger.error(f"[FIX_EMAILS] Ошибка на {server['name']}: {e}", exc_info=True)

    # === ИТОГ ===
    final = "<b>ГОТОВО! Email полностью очищены</b>\n\n"
    final += f"Netherlands (_n): <b>{total_n}</b>\n"
    final += f"Germany (_g): <b>{total_g}</b>\n"
    final += f"Trial пользователи: <b>{total_trial}</b>\n\n"
    final += "Формат теперь:\n"
    final += "<code>123456789_n</code>\n"
    final += "<code>123456789_g</code>\n"
    final += "<code>123456789_trial</code>"

    if errors:
        final += "\n\n<b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors)

    await msg.edit_text(final, reply_markup=get_admin_keyboard())
    logger.info(f"[FIX_EMAILS] Полная чистка завершена: _n={total_n}, _g={total_g}, _trial={total_trial}")

@dp.callback_query(F.data.startswith("pay_yookassa_"))
async def payment_yookassa_handler(c: types.CallbackQuery):
    """Обработчик оплаты через YooKassa"""
    period = c.data.split("_")[-1]
    
    tariffs = {
        "30": {"days": 30, "price": 90},
        "90": {"days": 90, "price": 256},
        "180": {"days": 180, "price": 502},
        "360": {"days": 360, "price": 972},
    }
    
    tariff = tariffs[period]
    uid = str(c.from_user.id)
    
    payment = await create_yookassa_payment(
        user_id=c.from_user.id,
        amount=tariff["price"],
        days=tariff["days"]
    )
    
    if payment.get("success"):
        user_data.setdefault(uid, {
            "vless_links": {"n": "", "g": "", "u": ""},
            "tariff": "dual_server",
            "referrer": None
        })
        user_data[uid]["pending_yookassa"] = {
            "payment_id": payment["payment_id"],
            "order_id": payment["order_id"],
            "days": tariff["days"],
            "amount": tariff["price"],
            "timestamp": int(time.time())
        }
        save_user_data(user_data)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Оплатить {tariff['price']}₽",
                url=payment["url"]
            )],
            [InlineKeyboardButton(
                text="✅ Проверить оплату",
                callback_data=f"check_yookassa_{payment['payment_id']}"
            )],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_{period}")]
        ])
        
        text = (
            f"💳 <b>Оплата через ЮKassa</b>\n\n"
            f"📦 Тариф: <b>{tariff['days']} дней</b>\n"
            f"💰 Сумма: <b>{tariff['price']}₽</b>\n\n"
            f"<b>Способы оплаты:</b>\n"
            f"💳 Банковские карты\n"
            f"📱 СБП\n"
            f"💰 ЮMoney кошелёк\n"
            f"🏦 Сбербанк Онлайн\n\n"
            f"<b>Инструкция:</b>\n"
            f"1️⃣ Нажмите \"Оплатить\"\n"
            f"2️⃣ Выберите способ оплаты\n"
            f"3️⃣ Завершите оплату\n"
            f"4️⃣ Нажмите \"Проверить оплату\"\n\n"
            f"🆔 <code>{payment['order_id']}</code>"
        )
        
        await c.message.answer(text, reply_markup=kb)
        await c.answer()
    else:
        await c.answer("❌ Ошибка создания платежа", show_alert=True)

@dp.callback_query(F.data.startswith("check_yookassa_"))
async def check_yookassa_handler(c: types.CallbackQuery):
    """Проверка оплаты YooKassa"""
    payment_id = c.data.replace("check_yookassa_", "")
    uid = str(c.from_user.id)
    
    pending = user_data.get(uid, {}).get("pending_yookassa", {})
    
    if pending.get("payment_id") != payment_id:
        return await c.answer("❌ Платеж не найден", show_alert=True)
    
    await c.answer("⏳ Проверяем...", show_alert=False)
    
    status = await check_yookassa_payment(payment_id)
    
    if status.get("status") == "PAID":
        days = pending["days"]
        success, results, _ = vpn.sync_and_issue_vless(c.from_user.id, days=days)
        
        if success:
            del user_data[uid]["pending_yookassa"]
            save_user_data(user_data)
            
            await c.message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Подписка на {days} дней активирована.\n"
                f"Используйте /start"
            )
        else:
            await c.answer("❌ Ошибка выдачи VPN", show_alert=True)
    elif status.get("status") == "WAITING":
        await c.answer("⏳ Платеж не завершен", show_alert=True)
    else:
        await c.answer("❌ Ошибка проверки", show_alert=True)

@dp.message()
async def any_message(message: types.Message):
    user_id = message.from_user.id
    register_user_for_broadcast(user_id)
    await send_newyear_welcome(message, user_id)

async def rukassa_webhook(request):
    """Webhook от Rukassa"""
    try:
        # Получаем данные из POST
        data = await request.post()
        
        # Получаем подпись из заголовка
        signature = request.headers.get('Signature', '')
        
        order_id = data.get("order_id")
        amount = data.get("amount")
        in_amount = data.get("in_amount")
        status = data.get("status")
        payment_id = data.get("id")
        created = data.get("createdDateTime")
        custom_data = data.get("data", "{}")
        
        logger.info(f"[RUKASSA WEBHOOK] ID:{payment_id}, Order:{order_id}, Status:{status}")
        
        # Проверка подписи HMAC SHA256
        expected_sign = hashlib.sha256(
            f"{payment_id}|{created}|{amount}".encode() + 
            RUKASSA_API_KEY.encode()
        ).hexdigest()
        
        # ВАЖНО: Rukassa использует HMAC, а не обычный hash
        import hmac
        expected_sign = hmac.new(
            RUKASSA_API_KEY.encode(),
            f"{payment_id}|{created}|{amount}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.info(f"[RUKASSA WEBHOOK] Signature: {signature}, Expected: {expected_sign}")
        
        if signature != expected_sign:
            logger.error(f"[RUKASSA WEBHOOK] Неверная подпись!")
            return web.Response(text="ERROR SIGN")
        
        # Проверка суммы
        if float(in_amount) < float(amount):
            logger.error(f"[RUKASSA WEBHOOK] Недостаточная сумма")
            return web.Response(text="ERROR AMOUNT")
        
        if status == "PAID":
            # Парсим данные
            import html
            payment_data = json.loads(html.unescape(custom_data))
            user_id = payment_data["user_id"]
            days = payment_data["days"]
            
            # Выдаем VPN
            success, _, _ = vpn.sync_and_issue_vless(user_id, days=days)
            
            if success:
                # Очищаем pending
                uid = str(user_id)
                if uid in user_data and "pending_payment" in user_data[uid]:
                    del user_data[uid]["pending_payment"]
                    save_user_data(user_data)
                
                # Уведомляем пользователя
                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>Оплата подтверждена!</b>\n\n"
                        f"Подписка на {days} дней активирована.\n"
                        f"Используйте /start"
                    )
                except:
                    pass
                
                logger.info(f"[RUKASSA WEBHOOK] VPN выдан: {order_id}")
                return web.Response(text="OK")
        
        return web.Response(text="OK")
        
    except Exception as e:
        logger.error(f"[RUKASSA WEBHOOK] Ошибка: {e}", exc_info=True)
        return web.Response(text="ERROR")


async def start_webhook():
    app = web.Application()
    app.router.add_post('/rukassa/webhook', rukassa_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

# === ЗАПУСК ===
async def main():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old = f.read().strip()
            if old:
                os.kill(int(old), 0)
                logger.warning(f"Бот уже запущен (PID {old})")
                sys.exit(1)
        except:
            os.remove(PID_FILE)

    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
        init_yookassa()
    logger.info("united.py 16.12.2025 | RUKASSA + YOOKASSA + STARS")
    
    try:
        # Запускаем webhook сервер для Rukassa
        asyncio.create_task(start_webhook())
        logger.info("[RUKASSA] Webhook сервер запущен")
        
        # Запускаем бота
        await dp.start_polling(bot)
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

if __name__ == "__main__":
    asyncio.run(main())