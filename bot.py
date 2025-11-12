import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, List
import pytz  # <-- Импортируем pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os  # <-- Импортируем os для переменных окружения

# ========================
# КОНФИГУРАЦИЯ (из переменных окружения)
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("Ошибка: Переменная окружения BOT_TOKEN не установлена.")
    exit(1)

try:
    YOUR_CHAT_ID = int(os.getenv("YOUR_CHAT_ID", 0))
    if YOUR_CHAT_ID == 0:
        print("Ошибка: Переменная окружения YOUR_CHAT_ID не установлена или равна 0.")
        exit(1)
except ValueError:
    print("Ошибка: YOUR_CHAT_ID должен быть числом.")
    exit(1)

# Список вопросов (10 шт)
QUESTIONS = [
    "Сколько раз ты улыбался?",
    "Сколько улыбок видел вокруг?",
    "Были ли негативные мысли?",
    "Сколько раз ты солгал, даже в самой что ни на есть мелочи — себе или другим?",
    "Какая осанка у тебя прямо сейчас? И да – на окружающих тоже глянь, ради интереса.",
    "Видел ли счастливых людей?",
    "В каком настроении ты провёл этот час?",
    "Сколько минут в прошедшем часе тебе было хорошо и спокойно?",
    "За прошедший час: благодарил ли ты кого-нибудь искренне, от души? Благодарили ли тебя?",
    "Читал ли, видел ли, слышал ли за прошедший час негативные новости или сплетни?"
]

# Список ссылок на цитаты (из файла)
try:
    with open('цитаты в картинках_ссылки.txt', 'r', encoding='utf-8') as f:
        QUOTE_IMAGES = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print("Файл 'цитаты в картинках_ссылки.txt' не найден. Убедитесь, что он находится в той же папке, что и bot.py.")
    exit(1)

# ========================
# ХРАНИЛИЩЕ ДАННЫХ (в памяти, для старта с ноутбука)
# ========================
# Словарь для хранения информации о пользователях
users = {}  # {user_id: {start_hour, end_hour, used_quotes_today, last_action_day, message_count}}

# ========================
# ИНИЦИАЛИЗАЦИЯ
# ========================
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=session, parse_mode=ParseMode.HTML)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# ========================
# ХЭНДЛЕРЫ
# ========================
class UserState(StatesGroup):
    setting_hours = State()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    kb = ReplyKeyboardRemove()
    await message.answer(
        "Привет! Я бот-наблюдатель от Артёма Волкова.\n"
        "Укажи интервал времени (по МСК), когда хочешь получать напоминания.\n"
        "Формат: ЧЧ-ЧЧ (например: 9-20)",
        reply_markup=kb
    )
    await state.set_state(UserState.setting_hours)

@dp.message(UserState.setting_hours)
async def process_hours(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    try:
        start_str, end_str = text.split('-')
        start_hour = int(start_str.strip())
        end_hour = int(end_str.strip())
        if not (0 <= start_hour < 24 and 0 <= end_hour <= 24 and start_hour < end_hour):
            raise ValueError

        users[user_id] = {
            'start_hour': start_hour,
            'end_hour': end_hour,
            'used_quotes_today': set(),
            'last_action_day': datetime.now(pytz.timezone("Europe/Moscow")).date(), # <-- Используем МСК
            'message_count': 0
        }
        await message.answer(
            f"Отлично! Буду присылать напоминания с {start_hour}:00 до {end_hour}:00 по МСК.\n"
            "Сегодня же — в ближайший час."
        )
        await state.clear()

        # Попробуем отправить первое сообщение, если сейчас подходящее время (по МСК)
        now_msk = datetime.now(pytz.timezone("Europe/Moscow"))
        current_hour_msk = now_msk.hour

        if start_hour <= current_hour_msk < end_hour:
            await send_hourly_message(user_id)

    except ValueError:
        await message.answer("Неверный формат. Пример: 9-20")

@dp.message()
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = message.text.strip().lower()
    if user_id not in users:
        await message.answer("Для начала настрой интервал, отправив /start")
        return

    # Обработка ответов на CTA
    if text == "да":
        # Продлеваем на завтра
        users[user_id]['last_action_day'] = datetime.now(pytz.timezone("Europe/Moscow")).date() # <-- Используем МСК
        users[user_id]['message_count'] += 1
        await message.answer("Отлично! Завтра напомню в то же время.")

        # Проверка на 3-й день
        if users[user_id]['message_count'] >= 3:
            kb = ReplyKeyboardBuilder()
            kb.button(text="Поговорить с Артёмом")
            kb.button(text="Просто остаться в рассылке")
            await message.answer(
                "Ты уже 3 дня с нами! Хочешь обсудить, как перейти к следующему шагу?",
                reply_markup=kb.as_markup(resize_keyboard=True)
            )
    elif text == "нет":
        if user_id in users:
            del users[user_id]
        await message.answer("Спасибо за участие! Если захочешь вернуться — просто напиши /start.")
    elif text == "поговорить с артёмом":
        await message.answer("Отлично! Напиши Артёму в Telegram: @aawolf_1979")
        if user_id in users:
            del users[user_id]
    elif text == "просто остаться в рассылке":
        await message.answer("Продолжаю присылать напоминания. Увидимся завтра!")
        # Сбросим счётчик, если нужно, чтобы 3 дня считались заново
        users[user_id]['message_count'] = 0

# ========================
# ФУНКЦИИ РАССЫЛКИ
# ========================
async def send_hourly_message(user_id: int):
    if user_id not in users:
        return
    user_data = users[user_id]

    # Выбираем случайный вопрос
    question = random.choice(QUESTIONS)

    # Выбираем случайную цитату, не использованную сегодня
    available_quotes = [q for q in QUOTE_IMAGES if q not in user_data['used_quotes_today']]
    if not available_quotes:
        available_quotes = QUOTE_IMAGES  # Если всё использовано — сброс
    quote = random.choice(available_quotes)
    user_data['used_quotes_today'].add(quote)

    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=quote,
            caption=question
        )
    except Exception as e:
        print(f"Ошибка отправки {user_id}: {e}")

    # Проверяем, последний ли это час (по МСК)
    now_msk = datetime.now(pytz.timezone("Europe/Moscow")) # <-- Используем МСК
    if now_msk.hour == user_data['end_hour'] - 1:
        kb = ReplyKeyboardBuilder()
        kb.button(text="Да")
        kb.button(text="Нет")
        await bot.send_message(
            chat_id=user_id,
            text="Завтра в это же время?",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )

async def send_log_to_owner():
    """Отправка лога владельцу каждый час в 10 минут по МСК"""
    total_users = len(users)
    now_msk = datetime.now(pytz.timezone("Europe/Moscow")) # <-- Используем МСК
    await bot.send_message(
        chat_id=YOUR_CHAT_ID,
        text=f"📊 Лог бота-наблюдателя:\n"
             f"Всего активных: {total_users}\n"
             f"Время: {now_msk.strftime('%Y-%m-%d %H:%M')} МСК"
    )

# ========================
# ПЛАНИРОВЩИК
# ========================
async def schedule_hourly_messages():
    """Планирует рассылку каждому пользователю в его интервал (по МСК)"""
    now_msk = datetime.now(pytz.timezone("Europe/Moscow")) # <-- Используем МСК
    current_hour_msk = now_msk.hour
    for user_id, data in list(users.items()):  # Используем list(), чтобы избежать RuntimeError при изменении словаря
        if data['start_hour'] <= current_hour_msk < data['end_hour']: # <-- Сравниваем с МСК
            await send_hourly_message(user_id)

async def reset_daily_quotes():
    """Сбрасывает использованные цитаты каждую ночь (по МСК)"""
    # Эта функция не зависит от часа, но дата тоже берётся по МСК
    pass # Логика сброса не зависит от часа, просто очищаем множества

async def main():
    # Запуск планировщика
    # Отправка лога каждый час в 10 минут
    scheduler.add_job(send_log_to_owner, CronTrigger(minute=10))
    # Отправка сообщений каждый час в 05 минут
    scheduler.add_job(schedule_hourly_messages, CronTrigger(minute=5))
    # Сброс цитат в полночь (по МСК)
    scheduler.add_job(reset_daily_quotes, CronTrigger(hour=0, minute=0))

    scheduler.start()
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
