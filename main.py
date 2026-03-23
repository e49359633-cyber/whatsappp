import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Вставь сюда токен твоего бота от @BotFather
BOT_TOKEN = "8640805204:AAEOttLZQOHRVJqer_qThiQ7hs639_0zQ6Q"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- 1. Главное меню (Команда /start) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем нижнюю клавиатуру (Reply)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Сдать ватсап"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🎧 Поддержка"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True, # Делаем кнопки аккуратными
        input_field_placeholder="Выберите действие ниже"
    )
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в нашего бота.", 
        reply_markup=keyboard
    )

# --- 2. Раздел "Профиль" ---
@dp.message(F.text == "👤 Профиль")
async def show_profile(message: types.Message):
    # В будущем здесь можно брать данные из базы данных
    total_numbers = 0 
    
    # Создаем инлайн-кнопку (под сообщением)
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Посмотреть сегодняшние сданные", callback_data="today_stats")]
        ]
    )
    
    text = (
        "<b>👤 Ваш профиль</b>\n\n"
        f"📦 Всего сданных номеров: <b>{total_numbers}</b>"
    )
    
    await message.answer(text, reply_markup=inline_kb, parse_mode="HTML")

# --- 3. Раздел "Сдать ватсап" ---
@dp.message(F.text == "📱 Сдать ватсап")
async def rent_whatsapp(message: types.Message):
    # Создаем инлайн-клавиатуру с тарифами
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ФБХ (1$ - 5 минут)", callback_data="rent_fbx")],
            [InlineKeyboardButton(text="БХ (5$ - 25 минут)", callback_data="rent_bx")],
            [InlineKeyboardButton(text="Холд (9$ - 60 минут)", callback_data="rent_hold")]
        ]
    )
    
    await message.answer("Выберите подходящий тариф для сдачи аккаунта:", reply_markup=inline_kb)

# --- 4. Заглушки для разделов Поддержка и Помощь ---
@dp.message(F.text == "🎧 Поддержка")
async def support_menu(message: types.Message):
    await message.answer("Связь с поддержкой: @твой_юзернейм_саппорта")

@dp.message(F.text == "❓ Помощь")
async def help_menu(message: types.Message):
    await message.answer("Здесь будет инструкция о том, как работает сервис.")

# --- 5. Обработка нажатий на инлайн-кнопки ---
@dp.callback_query(F.data.in_({"rent_fbx", "rent_bx", "rent_hold"}))
async def process_rent_selection(callback: types.CallbackQuery):
    # Убираем часики на кнопке
    await callback.answer()
    
    if callback.data == "rent_fbx":
        await callback.message.answer("Вы выбрали тариф ФБХ. Отправьте номер...")
    elif callback.data == "rent_bx":
        await callback.message.answer("Вы выбрали тариф БХ. Отправьте номер...")
    elif callback.data == "rent_hold":
        await callback.message.answer("Вы выбрали тариф Холд. Отправьте номер...")

@dp.callback_query(F.data == "today_stats")
async def process_today_stats(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Сегодня вы еще не сдавали аккаунты. (Здесь будет список)")

# Запуск бота
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
