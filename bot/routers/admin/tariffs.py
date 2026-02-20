from uuid import UUID
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.management.dependencies import get_api_client
from bot.entities.tariff.repository import TariffRepository
from bot.entities.tariff.service import TariffService
from bot.entities.tariff.models import CreateTariffRequest, UpdateTariffRequest
from bot.middlewares.admin import AdminMiddleware
from bot.keyboards.admin import (
    get_tariffs_keyboard, get_tariff_actions_keyboard,
    get_tariff_edit_keyboard, get_admin_menu_keyboard, get_fsm_keyboard
)
from bot.messages.admin import TARIFFS_LIST_TEMPLATE, TARIFF_INFO_TEMPLATE
from bot.management.logger import configure_logger

router = Router()
logger = configure_logger("ADMIN_TARIFFS", "red")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

_FIELD_LABELS = {
    "name": "Название",
    "days": "Количество дней",
    "price_rub": "Цена в рублях",
    "price_stars": "Цена в звёздах",
    "sort_order": "Порядок сортировки",
    "is_active": "Активен (да/нет)",
}


class TariffStates(StatesGroup):
    create_code = State()
    create_name = State()
    create_days = State()
    create_price_rub = State()
    create_price_stars = State()
    create_sort_order = State()

    edit_choice = State()
    edit_value = State()


# ─── Cancel for create FSM ────────────────────────────────────────────────────

@router.message(StateFilter(TariffStates), F.text == "❌ Отмена")
async def cancel_tariff_create(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Операция отменена.", reply_markup=get_admin_menu_keyboard())


# ─── Tariff list ─────────────────────────────────────────────────────────────

@router.message(F.text == "💳 Тарифы")
async def tariffs_list_handler(message: Message):
    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            tariffs = await tariff_service.get_all_tariffs()

            active_count = sum(1 for t in tariffs if t.is_active)

            tariffs_list = ""
            for tariff in sorted(tariffs, key=lambda t: t.sort_order):
                status_emoji = "✅" if tariff.is_active else "❌"
                tariffs_list += f"{status_emoji} <b>{tariff.name}</b> ({tariff.code})\n"
                tariffs_list += f"   {tariff.days} дней | {tariff.price_rub}₽ | {tariff.price_stars}⭐\n\n"

            text = TARIFFS_LIST_TEMPLATE.format(
                total=len(tariffs),
                active=active_count,
                tariffs_list=tariffs_list
            )

            await message.answer(text, reply_markup=get_tariffs_keyboard(tariffs))

    except Exception as e:
        logger.error(f"Error in tariffs_list_handler: {e}")
        await message.answer("❌ Произошла ошибка при загрузке тарифов")


# ─── Tariff card ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_tariff_view_"))
async def tariff_info_handler(callback: CallbackQuery):
    tariff_id = callback.data.removeprefix("admin_tariff_view_")

    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            tariff = await tariff_service.get_tariff(UUID(tariff_id))

            status = "✅ Активен" if tariff.is_active else "❌ Неактивен"

            text = TARIFF_INFO_TEMPLATE.format(
                name=tariff.name,
                code=tariff.code,
                days=tariff.days,
                price_rub=tariff.price_rub,
                price_stars=tariff.price_stars,
                status=status,
                sort_order=tariff.sort_order,
                id=tariff.id
            )

            await callback.message.edit_text(text, reply_markup=get_tariff_actions_keyboard(str(tariff.id)))
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in tariff_info_handler: {e}")
        await callback.answer("❌ Ошибка при загрузке информации", show_alert=True)


# ─── Tariff delete ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_tariff_delete_"))
async def tariff_delete_handler(callback: CallbackQuery):
    tariff_id = callback.data.removeprefix("admin_tariff_delete_")

    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            await tariff_service.delete_tariff(UUID(tariff_id))

            await callback.answer("✅ Тариф удалён", show_alert=True)
            await callback.message.delete()
            logger.info(f"Tariff {tariff_id} deleted by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error in tariff_delete_handler: {e}")
        await callback.answer("❌ Ошибка при удалении тарифа", show_alert=True)


# ─── Tariff edit ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_tariff_edit_"))
async def tariff_edit_start(callback: CallbackQuery, state: FSMContext):
    tariff_id = callback.data.removeprefix("admin_tariff_edit_")
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(TariffStates.edit_choice)

    await callback.message.edit_text(
        "✏️ <b>Редактирование тарифа</b>\n\nВыберите поле для изменения:",
        reply_markup=get_tariff_edit_keyboard(tariff_id)
    )
    await callback.answer()


@router.callback_query(TariffStates.edit_choice, F.data.startswith("tef:"))
async def tariff_edit_field_chosen(callback: CallbackQuery, state: FSMContext):
    field = callback.data.removeprefix("tef:")
    label = _FIELD_LABELS.get(field, field)
    await state.update_data(edit_field=field)
    await state.set_state(TariffStates.edit_value)

    hint = " (введите да/нет)" if field == "is_active" else ""
    await callback.message.edit_text(
        f"✏️ Введите новое значение для <b>{label}</b>{hint}:",
    )
    await callback.answer()


@router.message(TariffStates.edit_value)
async def tariff_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    tariff_id = data["tariff_id"]
    field = data["edit_field"]
    raw = message.text.strip()

    try:
        if field in ("days", "price_rub", "price_stars", "sort_order"):
            value = int(raw)
        elif field == "is_active":
            if raw.lower() in ("да", "yes", "true", "1"):
                value = True
            elif raw.lower() in ("нет", "no", "false", "0"):
                value = False
            else:
                await message.answer("❌ Введите «да» или «нет»:")
                return
        else:
            value = raw

        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            update_request = UpdateTariffRequest(**{field: value})
            tariff = await tariff_service.update_tariff(UUID(tariff_id), update_request)

        await state.clear()

        status = "✅ Активен" if tariff.is_active else "❌ Неактивен"
        text = TARIFF_INFO_TEMPLATE.format(
            name=tariff.name,
            code=tariff.code,
            days=tariff.days,
            price_rub=tariff.price_rub,
            price_stars=tariff.price_stars,
            status=status,
            sort_order=tariff.sort_order,
            id=tariff.id
        )
        await message.answer(text, reply_markup=get_tariff_actions_keyboard(str(tariff.id)))
        logger.info(f"Tariff {tariff_id} field '{field}' updated by admin {message.from_user.id}")

    except ValueError:
        await message.answer("❌ Некорректное значение. Попробуйте ещё раз:")
    except Exception as e:
        logger.error(f"Error updating tariff: {e}")
        await message.answer("❌ Ошибка при обновлении тарифа")
        await state.clear()


# ─── Navigation ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_tariffs_back")
async def tariffs_back_handler(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_tariffs_refresh")
async def tariffs_refresh_handler(callback: CallbackQuery):
    try:
        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)
            tariffs = await tariff_service.get_all_tariffs()

            active_count = sum(1 for t in tariffs if t.is_active)

            tariffs_list = ""
            for tariff in sorted(tariffs, key=lambda t: t.sort_order):
                status_emoji = "✅" if tariff.is_active else "❌"
                tariffs_list += f"{status_emoji} <b>{tariff.name}</b> ({tariff.code})\n"
                tariffs_list += f"   {tariff.days} дней | {tariff.price_rub}₽ | {tariff.price_stars}⭐\n\n"

            text = TARIFFS_LIST_TEMPLATE.format(
                total=len(tariffs),
                active=active_count,
                tariffs_list=tariffs_list
            )

            await callback.message.edit_text(text, reply_markup=get_tariffs_keyboard(tariffs))
            await callback.answer("✅ Обновлено")

    except Exception as e:
        logger.error(f"Error in tariffs_refresh_handler: {e}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)


# ─── Create tariff FSM ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_create_tariff")
async def create_tariff_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💳 <b>Создание нового тарифа</b>\n\n"
        "Введите код тарифа (например: 30, 90, 180):"
    )
    await state.set_state(TariffStates.create_code)
    await callback.answer()


@router.message(TariffStates.create_code)
async def create_tariff_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Введите название тарифа:", reply_markup=get_fsm_keyboard(back=False))
    await state.set_state(TariffStates.create_name)


@router.message(TariffStates.create_name)
async def create_tariff_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите количество дней:", reply_markup=get_fsm_keyboard(back=True))
    await state.set_state(TariffStates.create_days)


@router.message(TariffStates.create_days, F.text == "◀️ Назад")
async def create_tariff_days_back(message: Message, state: FSMContext):
    await message.answer("Введите название тарифа:", reply_markup=get_fsm_keyboard(back=False))
    await state.set_state(TariffStates.create_name)


@router.message(TariffStates.create_days)
async def create_tariff_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        await state.update_data(days=days)
        await message.answer("Введите цену в рублях:", reply_markup=get_fsm_keyboard(back=True))
        await state.set_state(TariffStates.create_price_rub)
    except ValueError:
        await message.answer("❌ Некорректное значение. Введите число:")


@router.message(TariffStates.create_price_rub, F.text == "◀️ Назад")
async def create_tariff_price_rub_back(message: Message, state: FSMContext):
    await message.answer("Введите количество дней:", reply_markup=get_fsm_keyboard(back=True))
    await state.set_state(TariffStates.create_days)


@router.message(TariffStates.create_price_rub)
async def create_tariff_price_rub(message: Message, state: FSMContext):
    try:
        price_rub = int(message.text.strip())
        await state.update_data(price_rub=price_rub)
        await message.answer("Введите цену в звёздах Telegram:", reply_markup=get_fsm_keyboard(back=True))
        await state.set_state(TariffStates.create_price_stars)
    except ValueError:
        await message.answer("❌ Некорректное значение. Введите число:")


@router.message(TariffStates.create_price_stars, F.text == "◀️ Назад")
async def create_tariff_price_stars_back(message: Message, state: FSMContext):
    await message.answer("Введите цену в рублях:", reply_markup=get_fsm_keyboard(back=True))
    await state.set_state(TariffStates.create_price_rub)


@router.message(TariffStates.create_price_stars)
async def create_tariff_price_stars(message: Message, state: FSMContext):
    try:
        price_stars = int(message.text.strip())
        await state.update_data(price_stars=price_stars)
        await message.answer(
            "Введите порядковый номер для сортировки (0 = первый):",
            reply_markup=get_fsm_keyboard(back=True)
        )
        await state.set_state(TariffStates.create_sort_order)
    except ValueError:
        await message.answer("❌ Некорректное значение. Введите число:")


@router.message(TariffStates.create_sort_order, F.text == "◀️ Назад")
async def create_tariff_sort_order_back(message: Message, state: FSMContext):
    await message.answer("Введите цену в звёздах Telegram:", reply_markup=get_fsm_keyboard(back=True))
    await state.set_state(TariffStates.create_price_stars)


@router.message(TariffStates.create_sort_order)
async def create_tariff_finish(message: Message, state: FSMContext):
    try:
        sort_order = int(message.text.strip())
        data = await state.get_data()

        api_client = get_api_client()
        async with api_client:
            tariff_repo = TariffRepository(api_client)
            tariff_service = TariffService(tariff_repo)

            request = CreateTariffRequest(
                code=data['code'],
                name=data['name'],
                days=data['days'],
                price_rub=data['price_rub'],
                price_stars=data['price_stars'],
                is_active=True,
                sort_order=sort_order
            )

            tariff = await tariff_service.create_tariff(request)

            await message.answer(
                f"✅ Тариф <b>{tariff.name}</b> успешно создан!\n\n"
                f"Код: {tariff.code}\n"
                f"Дней: {tariff.days}\n"
                f"Цена: {tariff.price_rub}₽ / {tariff.price_stars}⭐",
                reply_markup=get_admin_menu_keyboard()
            )
            logger.info(f"Tariff {tariff.code} created by admin {message.from_user.id}")

        await state.clear()

    except ValueError:
        await message.answer("❌ Некорректное значение. Введите число:")
    except Exception as e:
        logger.error(f"Error creating tariff: {e}")
        await message.answer("❌ Ошибка при создании тарифа", reply_markup=get_admin_menu_keyboard())
        await state.clear()
