import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ===================== НАСТРОЙКИ =====================
TOKEN = ""               # ← Вставь свой настоящий токен сюда
ADMIN_ID = 8209617821                       # ← Твой Telegram ID
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== ХРАНИЛИЩА (для теста) =====================
pending_rentals = []                        # очередь заявок
active_rentals = {}                         # активные аренды {rental_id: dict}
user_stats = {}                             # {user_id: {"rented_count": int, "today": list}}
users = set()                               # все пользователи для рассылки
rental_counter = 0

# ===================== СОСТОЯНИЯ =====================
class RentForm(StatesGroup):
    waiting_phone = State()

class AdminActions(StatesGroup):
    waiting_for_photo = State()

class BroadcastState(StatesGroup):
    waiting_message = State()

# ===================== КЛАВИАТУРЫ =====================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Сдать WhatsApp в аренду", callback_data="start_rent")],
        [InlineKeyboardButton(text="👤 Мой профиль",            callback_data="profile")],
        [InlineKeyboardButton(text="🆘 Поддержка",              callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ Помощь / FAQ",           callback_data="help")],
    ])


def tariff_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="FBX — 1$ / 5 минут",   callback_data="tariff_fbx")],
        [InlineKeyboardButton(text="BH  — 5–25 минут",     callback_data="tariff_bh")],
        [InlineKeyboardButton(text="HOLD — 9–60 минут",    callback_data="tariff_hold")],
        [InlineKeyboardButton(text="← Назад в главное меню", callback_data="back_to_main")],
    ])


def rental_control_keyboard(rental_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить фото кода",     callback_data=f"send_photo_{rental_id}")],
        [InlineKeyboardButton(text="🔄 Запросить повтор кода",    callback_data=f"repeat_{rental_id}")],
        [InlineKeyboardButton(text="✅ Встал / Завершено",        callback_data=f"installed_{rental_id}")],
        [InlineKeyboardButton(text="❌ Отменить эту аренду",      callback_data=f"cancel_rental_{rental_id}")],
    ])


CANCEL_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
])


# ===================== ХЕНДЛЕРЫ =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    users.add(message.from_user.id)
    await message.answer(
        "👋 Добро пожаловать в бот аренды WhatsApp-аккаунтов!\n"
        "Выберите действие ниже:",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "start_rent")
async def start_rent(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите тариф аренды:",
        reply_markup=tariff_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "👋 Вы в главном меню. Выберите действие:",
        reply_markup=main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("tariff_"))
async def choose_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff_code = callback.data.split("_")[1]
    tariff_name = {
        "fbx":   "FBX — 1$ / 5 минут",
        "bh":    "BH — 5–25 минут",
        "hold":  "HOLD — 9–60 минут"
    }.get(tariff_code, "Неизвестный тариф")

    await state.update_data(tariff=tariff_name)
    await callback.message.edit_text(
        f"Вы выбрали тариф: <b>{tariff_name}</b>\n\n"
        "Введите номер телефона в международном формате:\n"
        "Пример: +77001234567",
        reply_markup=CANCEL_KB,
        parse_mode="HTML"
    )
    await state.set_state(RentForm.waiting_phone)
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено.\nЧто делаем дальше?",
        reply_markup=main_menu()
    )
    await callback.answer("Отменено")


@dp.message(RentForm.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer("❌ Номер должен начинаться с + и содержать минимум 10 символов", reply_markup=CANCEL_KB)
        return

    data = await state.get_data()
    tariff = data.get("tariff", "—")

    global rental_counter
    rental_counter += 1
    rental_id = rental_counter

    pending_rentals.append({
        "id": rental_id,
        "user_id": message.from_user.id,
        "username": message.from_user.username or "без имени",
        "phone": phone,
        "tariff": tariff
    })

    position = len(pending_rentals)

    await message.answer(
        f"✅ Заявка принята!\n"
        f"Ваша позиция в очереди: {position}\n"
        f"Номер: {phone}\n"
        f"Тариф: {tariff}\n\n"
        "Ожидайте, скоро оператор свяжется.",
        reply_markup=main_menu()
    )

    # Уведомление админу
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Взять в работу", callback_data=f"take_{rental_id}")]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"🔥 НОВАЯ ЗАЯВКА #{rental_id}\n"
        f"👤 @{message.from_user.username or 'без имени'}  [{message.from_user.id}]\n"
        f"📱 {phone}\n"
        f"💰 {tariff}\n"
        f"📍 Позиция в очереди: {position}",
        reply_markup=admin_kb
    )

    await state.clear()


# ===================== ВЗЯТЬ АРЕНДУ =====================
@dp.callback_query(F.data.startswith("take_"))
async def take_rental(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только администратор может брать заявки", show_alert=True)
        return

    try:
        rental_id = int(callback.data.split("_")[1])
    except:
        await callback.answer("Ошибка в данных заявки", show_alert=True)
        return

    rental = next((r for r in pending_rentals if r["id"] == rental_id), None)
    if not rental:
        await callback.answer("Заявка уже взята или удалена", show_alert=True)
        return

    pending_rentals.remove(rental)
    active_rentals[rental_id] = rental

    await bot.send_message(
        rental["user_id"],
        f"📱 Ваш номер {rental['phone']} взят в работу оператором!\nОжидайте дальнейших инструкций."
    )

    control_kb = rental_control_keyboard(rental_id)

    await callback.message.edit_text(
        f"✅ Взят номер {rental['phone']} (ID {rental_id})\n"
        f"Тариф: {rental['tariff']}\n\n"
        f"Управление:",
        reply_markup=control_kb
    )
    await callback.answer("Взято в работу")


# ===================== УПРАВЛЕНИЕ АРЕНДОЙ =====================
@dp.callback_query(F.data.startswith("repeat_"))
async def repeat_code(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    rental_id = int(callback.data.split("_")[1])
    rental = active_rentals.get(rental_id)
    if rental:
        await bot.send_message(rental["user_id"], "🔄 Оператор просит повторить код подтверждения!")
        await callback.answer("Запрос повтора отправлен клиенту")


@dp.callback_query(F.data.startswith("installed_"))
async def mark_installed(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    rental_id = int(callback.data.split("_")[1])
    rental = active_rentals.pop(rental_id, None)
    if rental:
        uid = rental["user_id"]
        if uid not in user_stats:
            user_stats[uid] = {"rented_count": 0, "today": []}
        user_stats[uid]["rented_count"] += 1
        user_stats[uid]["today"].append(rental["phone"])

        await bot.send_message(rental["user_id"], "✅ Аренда успешно завершена! Номер встал.")
        await callback.message.edit_text(f"✅ Аренда {rental['phone']} помечена как завершённая")
        await callback.answer("Готово")


@dp.callback_query(F.data.startswith("send_photo_"))
async def request_photo(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    rental_id = int(callback.data.split("_")[2])
    await state.update_data(rental_id=rental_id)
    await callback.message.edit_text("📸 Отправьте фото с кодом в этот чат")
    await state.set_state(AdminActions.waiting_for_photo)
    await callback.answer()


@dp.message(AdminActions.waiting_for_photo, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return

    data = await state.get_data()
    rental_id = data.get("rental_id")
    rental = active_rentals.get(rental_id)

    if rental and message.photo:
        photo_id = message.photo[-1].file_id
        await bot.send_photo(
            rental["user_id"],
            photo_id,
            caption="📸 Фото кода от оператора"
        )
        await message.answer("Фото успешно отправлено владельцу номера!")
    
    await state.clear()


@dp.callback_query(F.data.startswith("cancel_rental_"))
async def cancel_rental(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    rental_id = int(callback.data.split("_")[2])
    rental = active_rentals.pop(rental_id, None)
    
    if rental:
        await bot.send_message(
            rental["user_id"],
            "⚠️ Аренда вашего номера была отменена оператором."
        )
        await callback.message.edit_text(
            f"Аренда {rental['phone']} (ID {rental_id}) отменена.",
            reply_markup=None
        )
        await callback.answer("Аренда отменена")
    else:
        await callback.answer("Аренда уже завершена или не найдена")


# ===================== ПРОФИЛЬ =====================
@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    uid = callback.from_user.id
    stats = user_stats.get(uid, {"rented_count": 0, "today": []})
    
    text = (
        "👤 <b>Ваш профиль</b>\n\n"
        f"Всего сдано номеров: <b>{stats['rented_count']}</b>\n"
        f"Сегодня сдано: <b>{len(stats['today'])}</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Посмотреть сегодняшние номера", callback_data="today_rentals")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")],
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "today_rentals")
async def show_today(callback: types.CallbackQuery):
    uid = callback.from_user.id
    stats = user_stats.get(uid, {"today": []})
    
    if stats["today"]:
        text = "📅 Сегодня сданы номера:\n" + "\n".join([f"• {p}" for p in stats["today"]])
    else:
        text = "📅 Сегодня вы ничего не сдавали"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад в профиль", callback_data="profile")],
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== ПОДДЕРЖКА И ПОМОЩЬ =====================
@dp.callback_query(F.data == "support")
async def support(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🛟 Поддержка:\nПишите прямо сюда или @ваш_ник_админа",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")]
        ])
    )


@dp.callback_query(F.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ Краткая справка:\n\n"
        "• «Сдать WhatsApp» → выбираете тариф → вводите номер\n"
        "• Ожидаете, пока оператор возьмёт заявку\n"
        "• Получаете код → отправляете его оператору\n"
        "• После успешной установки получаете оплату\n\n"
        "По всем вопросам — в поддержку.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")]
        ])
    )


# ===================== ЗАПУСК =====================
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
