import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from gspread import service_account
from aiogram.client.default import DefaultBotProperties

# === CONFIG ===
BOT_TOKEN = "8194076815:AAE8YNo9DNnQGk_E9wUcyU14YgHyF0xIHPo"
GOOGLE_CREDENTIALS_FILE = "google-api.json"
SPREADSHEET_NAME = "mpl_ap"

# === SETUP ===
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# === GOOGLE SHEETS ===
gc = service_account(filename=GOOGLE_CREDENTIALS_FILE)
sheet = gc.open(SPREADSHEET_NAME).worksheet("leads")  # Указываем правильный лист

# === STATES ===
class LeadForm(StatesGroup):
    name = State()
    age = State()
    location = State()
    telegram = State()

# === START ===
@dp.message(F.text.startswith('/start'))
async def start(message: Message, state: FSMContext):
    args = message.text.split()
    webid = args[1] if len(args) > 1 else "unknown"
    await state.update_data(webid=webid)
    await message.answer("Привет! Давай знакомиться. Как тебя зовут?")
    await state.set_state(LeadForm.name)

@dp.message(LeadForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(LeadForm.age)

@dp.message(LeadForm.age)
async def get_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Из какого ты города?")
    await state.set_state(LeadForm.location)

@dp.message(LeadForm.location)
async def get_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Укажи свой Telegram @username")
    await state.set_state(LeadForm.telegram)

@dp.message(LeadForm.telegram)
async def get_telegram(message: Message, state: FSMContext):
    await state.update_data(telegram=message.text)
    data = await state.get_data()

    # Сохраняем в Google Sheets в нужном порядке
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # timestamp
        data["name"],                                  # name
        data["age"],                                   # age
        data["location"],                              # location
        data["telegram"],                              # tg_username
        data["webid"],                                 # webid
        message.from_user.id,                          # tg_user_id
        "pending"                                      # статус по умолчанию
    ])

    await message.answer("Спасибо! Мы скоро свяжемся с тобой ❤️")
    await state.clear()

# === LAUNCH ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
