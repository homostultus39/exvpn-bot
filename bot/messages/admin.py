ADMIN_MENU = """🔐 <b>Админ-панель</b>

Выберите раздел:"""


CLUSTERS_LIST_TEMPLATE = """🌐 <b>Кластеры</b>

Всего: {total}
Активные: {active}

{clusters_list}"""


CLUSTER_INFO_TEMPLATE = """🌐 <b>Кластер: {name}</b>

🆔 ID: <code>{id}</code>
🌍 Endpoint: {endpoint}
📊 Статус: {status}
🔌 Онлайн пиров: {online_peers}/{total_peers}
🐳 Контейнер: {container_status}
🔄 Последний handshake: {last_handshake}"""


CLIENTS_STATS_TEMPLATE = """👥 <b>Клиенты</b>

Всего клиентов: {total}
С активной подпиской: {active}
С ключами: {with_keys}"""


GENERAL_STATS_TEMPLATE = """📊 <b>Общая статистика</b>

👥 Клиенты: {clients_total}
🌐 Кластеры: {clusters_total} (активных: {clusters_active})
🔑 Пиры: {peers_total}
📡 Онлайн: {peers_online}"""


TARIFFS_LIST_TEMPLATE = """💳 <b>Тарифы</b>

Всего: {total}
Активные: {active}

{tariffs_list}"""


TARIFF_INFO_TEMPLATE = """💳 <b>Тариф: {name}</b>

🏷 Код: <code>{code}</code>
📅 Дней: {days}
💰 Цена (RUB): {price_rub}₽
⭐ Цена (Stars): {price_stars}
📊 Статус: {status}
🔢 Порядок: {sort_order}
🆔 ID: <code>{id}</code>"""
