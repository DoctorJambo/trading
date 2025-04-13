import asyncio
import websockets
import logging
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from PIL import Image
from io import BytesIO
import datetime
import os

# Токен Telegram та Chat ID (заховано у змінні середовища)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Статус бота
bot_active = False
session_id = os.getenv('SESSION_ID')  # Зберігається у змінних середовища
user_agent = "Mozilla/5.0 (Android 13; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0"

wss_url = "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket"

def analyze_market(data):
    """Аналізує ринок за даними."""
    if "trend:up" in data:
        return "ВГОРУ"
    elif "trend:down" in data:
        return "ВНИЗ"
    return None

def get_screenshot():
    """Отримує скріншот із сервера."""
    try:
        screenshot_url = "https://api.pocketoption.com/chart_screenshot/pair_id_here"
        headers = {"User-Agent": user_agent, "Cookie": f"session_id={session_id}"}
        response = requests.get(screenshot_url, headers=headers)
        response.raise_for_status()  # Перевірка статусу відповіді
        return BytesIO(response.content)
    except requests.RequestException as e:
        logging.error(f"Помилка HTTP: {e}")
        return None

async def send_signal_to_telegram(signal_text):
    """Надсилає сигнал у Telegram."""
    screenshot = get_screenshot()
    if screenshot:
        image = Image.open(screenshot)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        keyboard = [
            [InlineKeyboardButton("Викл. бота", callback_data="stop"),
             InlineKeyboardButton("Вкл. бота", callback_data="start")]
        ]
        markup = InlineKeyboardMarkup(keyboard)

        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=image_bytes,
            caption=f"ГОТОВСЬКА СИГНАЛ\nНапрям: *{signal_text}*\nЧас: {datetime.datetime.now().strftime('%H:%M:%S')}",
            parse_mode="Markdown",
            reply_markup=markup
        )

async def market_listener():
    """Слухач ринку через WebSocket."""
    while True:
        try:
            async with websockets.connect(wss_url) as ws:
                await ws.send("40")
                while True:
                    data = await ws.recv()
                    if bot_active:
                        signal = analyze_market(data)
                        if signal:
                            await send_signal_to_telegram(signal)
        except websockets.ConnectionClosed as e:
            logging.error(f"З'єднання закрите: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Невідома помилка: {e}")
            await asyncio.sleep(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ввімкнення бота."""
    global bot_active
    bot_active = True
    await update.message.reply_text("Бот увімкнено!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для вимкнення бота."""
    global bot_active
    bot_active = False
    await update.message.reply_text("Бот вимкнено!")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок InlineKeyboard."""
    query = update.callback_query
    await query.answer()
    if query.data == "stop":
        global bot_active
        bot_active = False
        await query.edit_message_text("Бот вимкнено!")
    elif query.data == "start":
        bot_active = True
        await query.edit_message_text("Бот увімкнено!")

async def main():
    """Основна функція."""
    global bot
    bot = Bot(token=TELEGRAM_TOKEN)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("bot.log"),
            logging.StreamHandler()
        ]
    )

    # Запуск слухача ринку як окремого таску
    asyncio.create_task(market_listener())

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button_handler))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())