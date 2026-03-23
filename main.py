import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ===================== НАСТРОЙКИ =====================
TOKEN = "8640805204:AAEOttLZQOHRVJqer_qThiQ7hs639_0zQ6Q"          # ← Замени на токен от @BotFather
ADMIN_ID = 8209617821               # ← ТВОЙ Telegram ID (узнай у @userinfobot)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== ХРАНИЛИЩА (для теста) =====================
pending_rentals = []      # очередь заявок
active_rentals = {}       # активные аренды {rental_id: dict}
user_stats = {}           # {user_id: {"rented_count": int, "today": list}}
users = set()             # все пользователи для рассылки
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
        [InlineKeyboardButton(text="Сдать WhatsApp", callback_data="start_rent")],
        [InlineKeyboardButton(text="Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="Помощь", callback_data="help")],
    ])

def tariff_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="FBX 1$ — 5 минут", callback_data="tariff_fbx")],
        [InlineKeyboardButton(text="BH 5-25 минут", callback_data="tariff_bh")],
        [InlineKeyboardButton(text="HOLD 9-60 минут", callback_data="tariff_hold")],
    ])

# ===================== ХЕНДЛЕРЫ =====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    users.add(message.from_user.id)
    await message.answer(
        "👋 Привет! Добро пожаловать в бот аренды WhatsApp аккаунтов.\n"
        "Выберите действие ниже:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "start_rent")
async def start_rent(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите тариф:", reply_markup=tariff_menu())

@dp.callback_query(F.data.startswith("tariff_"))
async def choose_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff_code = callback.data.split("_")[1]
    tariff_name = {
        "fbx": "FBX 1$ — 5 минут",
        "bh": "BH 5-25 минут",
        "hold": "HOLD 9-60 минут"
    }.get(tariff_code, "Неизвестно")

    await state.update_data(tariff=tariff_name)
    await callback.message.edit_text(
        "Введите номер телефона для сдачи в аренду\n"
        "в формате: +77064170162"
    )
    await state.set_state(RentForm.waiting_phone)

@dp.message(RentForm.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Номер должен начинаться с +")
        return

    data = await state.get_data()
    tariff = data.get("tariff", "Неизвестно")

    global rental_counter
    rental_counter += 1
    rental_id = rental_counter

    pending_rentals.append({
        "id": rental_id,
        "user_id": message.from_user.id,
        "username": message.from_user.username or "no_username",
        "phone": phone,
        "tariff": tariff
    })

    position = len(pending_rentals)
    await message.answer(
        f"✅ Заявка принята!\n"
        f"📍 Ваша очередь: {position}\n"
        f"📱 Номер: {phone}\n"
        f"💰 Тариф: {tariff}"
    )

    # Уведомление админу
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Брать аренду", callback_data=f"take_{rental_id}")]
    ])
    await bot.send_message(
        ADMIN_ID,
        f"🔥 НОВАЯ ЗАЯВКА!\n"
        f"👤 @{message.from_user.username or 'no_username'}\n"
        f"📱 Номер: {phone}\n"
        f"💰 Тариф: {tariff}\n"
        f"📍 Очередь: {position}",
        reply_markup=admin_kb
    )
    await state.clear()

# ===================== ВЗЯТЬ АРЕНДУ =====================
@dp.callback_query(F.data.startswith("take_"))
async def take_rental(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Только админ!")
        return

    rental_id = int(callback.data.split("_")[1])
    rental = next((r for r in pending_rentals if r["id"] == rental_id), None)
    if not rental:
        await callback.answer("Заявка уже взята")
        return

    pending_rentals.remove(rental)
    active_rentals[rental_id] = rental

    # Уведомляем клиента
    await bot.send_message(
        rental["user_id"],
        f"📱 Ваш номер {rental['phone']} взят оператором!"
    )

    # Кнопки управления у админа
    control_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить фото кода", callback_data=f"send_photo_{rental_id}")],
        [InlineKeyboardButton(text="Повтор кода", callback_data=f"repeat_{rental_id}")],
        [InlineKeyboardButton(text="Встал", callback_data=f"installed_{rental_id}")],
    ])

    await callback.message.edit_text(
        f"✅ Номер {rental['phone']} взят в работу!\n"
        f"Управление арендой:",
        reply_markup=control_kb
    )
    await callback.answer("Взято!")

# ===================== КНОПКИ УПРАВЛЕНИЯ АРЕНДОЙ =====================
@dp.callback_query(F.data.startswith("repeat_"))
async def repeat_code(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    rental_id = int(callback.data.split("_")[1])
    rental = active_rentals.get(rental_id)
    if rental:
        await bot.send_message(rental["user_id"], "🔄 Оператор просит повторить код!")
        await callback.answer("Запрос отправлен")

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

        await bot.send_message(rental["user_id"], "✅ Аренда завершена! Номер 'встал'.")
        await callback.message.edit_text("✅ Аренда помечена как 'Встал'")
        await callback.answer("Готово")

@dp.callback_query(F.data.startswith("send_photo_"))
async def request_photo(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    rental_id = int(callback.data.split("_")[1])
    await state.update_data(rental_id=rental_id)
    await callback.message.edit_text("📸 Отправьте фото кода (просто фото в чат)")
    await state.set_state(AdminActions.waiting_for_photo)

@dp.message(AdminActions.waiting_for_photo, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    data = await state.get_data()
    rental_id = data.get("rental_id")
    rental = active_rentals.get(rental_id)
    if rental:
        photo_id = message.photo[-1].file_id
        await bot.send_photo(
            rental["user_id"],
            photo_id,
            caption="📸 Фото кода от оператора"
        )
        await message.answer("✅ Фото успешно отправлено владельцу номера!")
    await state.clear()

# ===================== ПРОФИЛЬ =====================
@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    uid = callback.from_user.id
    stats = user_stats.get(uid, {"rented_count": 0, "today": []})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть сегодняшние сданные", callback_data="today_rentals")]
    ])
    await callback.message.edit_text(
        f"👤 Ваш профиль\n\n"
        f"Сдано номеров всего: <b>{stats['rented_count']}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "today_rentals")
async def show_today(callback: types.CallbackQuery):
    uid = callback.from_user.id
    stats = user_stats.get(uid, {"today": []})
    if stats["today"]:
        text = "📅 Сегодняшние сданные WhatsApp:\n" + "\n".join([f"• {p}" for p in stats["today"]])
    else:
        text = "📅 Сегодня ничего не сдано"
    await callback.message.edit_text(text)

# ===================== ПОДДЕРЖКА И ПОМОЩЬ =====================
@dp.callback_query(F.data == "support")
async def support(callback: types.CallbackQuery):
    await callback.message.edit_text("🛟 Поддержка: пишите @ваш_админ_ник или в этот чат")

@dp.callback_query(F.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ Помощь:\n"
        "• Сдать WhatsApp — сдаёте номер в аренду\n"
        "• После выбора тарифа вводите номер\n"
        "• Ожидаете оператора\n"
        "• В профиле — статистика"
    )

# ===================== АДМИН ПАНЕЛЬ =====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рассылка всем клиентам", callback_data="broadcast")],
        [InlineKeyboardButton(text="Список очереди", callback_data="list_queue")],
    ])
    await message.answer("🛠 Главная админ-панель", reply_markup=kb)

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.edit_text("✉️ Отправьте текст (или фото/видео) для рассылки всем:")
    await state.set_state(BroadcastState.waiting_message)

@dp.message(BroadcastState.waiting_message)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    count = 0
    for uid in list(users):
        try:
            await message.copy_to(uid)   # копирует текст/фото/всё
            count += 1
        except:
            pass
    await message.answer(f"✅ Рассылка завершена! Отправлено: {count}")
    await state.clear()

@dp.callback_query(F.data == "list_queue")
async def list_queue(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    if not pending_rentals:
        await callback.message.edit_text("Очередь пуста")
        return
    text = "📋 Очередь заявок:\n\n"
    for r in pending_rentals:
        text += f"ID {r['id']}: @{r['username']} | {r['phone']} | {r['tariff']}\n"
    await callback.message.edit_text(text)

# ===================== ЗАПУСК =====================
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
