ADMIN_MENU = """🔐 <b>Админ-панель</b>

Выберите раздел:"""


CLUSTERS_LIST_TEMPLATE = """🌐 <b>Кластеры</b>

Всего: {total}

{clusters_list}"""


CLUSTER_INFO_TEMPLATE = """🌐 <b>Кластер: {name}</b>

🆔 ID: <code>{id}</code>
🌍 Endpoint: {endpoint}
🔌 Количество пиров: {total_peers}"""


CLIENTS_STATS_TEMPLATE = """👥 <b>Клиенты</b>

Всего клиентов: {total}
С активной подпиской: {active}
С ключами: {with_keys}"""


GENERAL_STATS_TEMPLATE = """📊 <b>Общая статистика</b>

👥 Клиенты: {clients_total}
🌐 Кластеры: {clusters_total} (активных: {clusters_active})
🔑 Пиры: {peers_total}
📡 Онлайн: {peers_online}"""


GLOBAL_STATS_TEMPLATE = """📊 <b>Общая статистика</b>

🌐 Кластеры: {clusters_total} (активных: {clusters_active}, неактивных: {clusters_inactive})

👥 Клиенты: {clients_total}
   ✅ Активных: {clients_active}
   🔰 Пробных: {clients_trial}
   ❌ Истёкших: {clients_expired}

🔑 Пиры: {peers_total} (онлайн: {peers_online})
   📱 AmneziaVPN: {peers_amnezia_vpn}
   🔒 AmneziaWG: {peers_amnezia_wg}

📶 Трафик:
   ⬇️ Получено: {rx}
   ⬆️ Отправлено: {tx}"""


CLUSTER_STATS_TEMPLATE = """🌐 <b>Статистика кластера: {cluster_name}</b>

📊 Статус: {status}
🐳 Контейнер: {container_status}
🔗 Протокол: {protocol}

👥 Клиентов: {clients_total}

🔑 Пиров: {peers_total} (онлайн: {peers_online})
   📱 AmneziaVPN: {peers_amnezia_vpn}
   🔒 AmneziaWG: {peers_amnezia_wg}

📶 Трафик:
   ⬇️ Получено: {rx}
   ⬆️ Отправлено: {tx}"""


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
