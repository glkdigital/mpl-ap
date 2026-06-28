import asyncio
import os
import csv
import aiohttp
import gspread
import json
from flask import Flask

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import types
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from gspread import authorize
from keep_alive import keep_alive

keep_alive() 


# === CONFIG ===
BOT_TOKEN = ""
SURVEY_BOT_USERNAME = "MyPleasuresAnketa_bot"
SUPPORT_USERNAME = "@glk341"
PARTNER_CHANNEL_URL = "https://t.me/+W0wll7wwAxw0OGJi"
GOOGLE_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzlmJciHpSWM_D0XllohjeDRxqP3FiyOO8jkz6AZx__NO8UUH-6VVsK7kQbgjpNkcQZ/exec"
TRACKING_FILE = "webid_tracking.csv"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

class WalletForm(StatesGroup):
    wallet = State()

# Получаем JSON из переменной окружения
creds_json = os.getenv("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

# Создаём объект Credentials
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

# Авторизация
gc = authorize(credentials)
sheet = gc.open("mpl_ap").worksheet("webmasters")

# === Меню ===
@dp.message(Command("start"))
async def start(message: Message):
    await show_main_menu(message)

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Трек-ссылка", callback_data="track_link")],
        [InlineKeyboardButton(text="📂 Материалы", callback_data="materials")],
        [InlineKeyboardButton(text="💰 Выплата", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])

async def show_main_menu(message: Message):
    image = FSInputFile("images/menu.png")
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=image,
        caption="<b>Добро пожаловать в бот партнёрской программы MyPleasures Partners!</b>\nВыбери нужный раздел:",
        reply_markup=get_main_menu()
    )

# === Трекинг WebID ===
def get_or_create_webid(user_id: int) -> str:
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[1] == str(user_id):
                    return row[0]
    webid = os.urandom(4).hex()
    with open(TRACKING_FILE, "a") as f:
        writer = csv.writer(f)
        writer.writerow([webid, user_id])
    return webid

# === Разделы ===
@dp.callback_query(F.data == "track_link")
async def handle_track_link(callback: types.CallbackQuery):
    webid = get_or_create_webid(callback.from_user.id)
    link = f"https://t.me/{SURVEY_BOT_USERNAME}?start={webid}"
    image = FSInputFile("images/link.png")
    await bot.send_photo(
        chat_id=callback.from_user.id,
        photo=image,
        caption=f"🔗 Твоя трек-ссылка: <code>{link}</code>\n\nПоддержка — {SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )

@dp.callback_query(F.data == "materials")
async def handle_materials(callback: types.CallbackQuery):
    image = FSInputFile("images/materials.png")
    await bot.send_photo(
        chat_id=callback.from_user.id,
        photo=image,
        caption=f"📂 В этом разделе: идеи, креативы и актуальные новости по партнёрке.\n\nПодключайся 👉 <a href=\"{PARTNER_CHANNEL_URL}\">Канал ПП</a>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )
    
    
# === Кошелёк вебмастера ===

@dp.callback_query(F.data == "withdraw")
async def handle_withdraw(callback: types.CallbackQuery):
    image = FSInputFile("images/withdraw.png")
    await bot.send_photo(
        chat_id=callback.from_user.id,
        photo=image,
        caption="💰 Здесь ты можешь сохранить или заменить кошелёк USDT (TRC20) и запросить выплату.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Ввести/заменить кошелёк", callback_data="wallet_input")],
            [InlineKeyboardButton(text="💼 Мой кошелёк", callback_data="my_wallet")],
            [InlineKeyboardButton(text="📤 Запросить выплату", callback_data="request_payout")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )

@dp.callback_query(F.data == "wallet_input")
async def wallet_input(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(WalletForm.wallet)
    await bot.send_message(callback.from_user.id, "Введите номер своего кошелька:")

@dp.message(WalletForm.wallet)
async def save_wallet(message: types.Message, state: FSMContext):
    wallet = message.text
    user_id = str(message.from_user.id)
    rows = []
    found = False

    # 1. Сохраняем/обновляем в CSV
    if os.path.exists("wallets.csv"):
        with open("wallets.csv", mode="r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] == user_id:
                    rows.append([user_id, wallet])
                    found = True
                else:
                    rows.append(row)

    if not found:
        rows.append([user_id, wallet])

    with open("wallets.csv", mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    # 2. Сохраняем/обновляем в Google Таблице
    try:
        data = sheet.get_all_values()
        header = data[0]
        user_id_col = header.index("user_id") + 1
        wallet_col = header.index("wallet") + 1
        username_col = header.index("username") + 1

        found_in_sheet = False
        for i, row in enumerate(data[1:], start=2):
            if row and row[user_id_col - 1] == user_id:
                sheet.update_cell(i, wallet_col, wallet)
                found_in_sheet = True
                break

        if not found_in_sheet:
            sheet.append_row([
                user_id,
                message.from_user.username or "",
                "",  # webid
                wallet
            ])

    except Exception as e:
        await message.answer(f"⚠️ Не удалось обновить Google Таблицу: {e}")

    await message.answer("✅ Кошелёк сохранён.")
    await state.clear()

@dp.callback_query(F.data == "my_wallet")
async def show_my_wallet(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    wallet = None

    try:
        data = sheet.get_all_values()
        header = data[0]
        user_id_col = header.index("user_id")
        wallet_col = header.index("wallet")

        for row in data[1:]:
            if row and row[user_id_col] == user_id:
                wallet = row[wallet_col]
                break

    except Exception as e:
        await bot.send_message(callback.from_user.id, f"❌ Ошибка при обращении к Google Таблице:\n<code>{e}</code>")
        return

    if wallet:
        await bot.send_message(callback.from_user.id, f"💼 Твой текущий кошелёк:\n<code>{wallet}</code>")
    else:
        await bot.send_message(callback.from_user.id, "⚠️ У тебя ещё не сохранён кошелёк.")
        
@dp.callback_query(F.data == "request_payout")
async def request_payout(callback: types.CallbackQuery):
    await bot.send_message(callback.from_user.id, "📤 Запрос отправлен. Мы свяжемся с тобой при ближайшей выплате!")


# === Статистика ===
@dp.callback_query(F.data == "stats")
async def handle_stats(callback: types.CallbackQuery):
    webid = get_or_create_webid(callback.from_user.id)
    url = f"{GOOGLE_APPS_SCRIPT_URL}?webid={webid}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total = data.get("total", 0)
                    pending = data.get("pending", 0)
                    approved = data.get("approved", 0)
                    rejected = data.get("rejected", 0)

                    image = FSInputFile("images/stats.png")
                    caption = (
                        "📊 <b>Твоя статистика:</b>\n\n"
                        f"👥 Всего лидов: <b>{total}</b>\n"
                        f"🟡 Ожидают: <b>{pending}</b>\n"
                        f"🟢 Апрув: <b>{approved}</b>\n"
                        f"🔴 Отклонено: <b>{rejected}</b>"
                    )
                    await bot.send_photo(
                        chat_id=callback.from_user.id,
                        photo=image,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
                        ])
                    )
                else:
                    await callback.message.answer("❌ Ошибка получения статистики.")
    except Exception as e:
        await callback.message.answer("⚠️ Не удалось подключиться к серверу статистики.")

@dp.callback_query(F.data == "back")
async def handle_back(callback: types.CallbackQuery):
    await show_main_menu(callback.message)

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
