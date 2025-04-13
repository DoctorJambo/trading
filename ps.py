import asyncio
import websockets
import logging
import requests
import threading
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from PIL import Image
from io import BytesIO
import datetime

# Токен Telegram та Chat ID
TELEGRAM_TOKEN = '7842140985:AAGRm6iS4N6omgUwpyQFHc0v_9VTtRDMeDY'
CHAT_ID = 1923764922   # твій ID

# Статус бота
bot_active = True
session_id = "2fcb7a80dfed0115fe0f00ca078284a0"  # заміни на свій session_id
user_agent = "Mozilla/5.0 (Android 13; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0"

wss_url = "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket"


def analyze_market(data):
    if "trend:up" in data:
        return "ВГОРУ"
    elif "trend:down" in data:
        return "ВНИЗ"
    return None

def get_screenshot():
    screenshot_url = "https://api.pocketoption.com/chart_screenshot/pair_id_here"
    headers = {"User-Agent": user_agent, "Cookie": f"session_id={session_id}"}
    response = requests.get(screenshot_url, headers=headers)
    if response.status_code == 200:
        return BytesIO(response.content)
    return None

async def send_signal_to_telegram(signal_text):
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
        except Exception as e:
            logging.error(f"WebSocket error: {e}")
            await asyncio.sleep(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = True
    await update.message.reply_text("Бот увімкнено!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = False
    await update.message.reply_text("Бот вимкнено!")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "stop":
        await stop(update, context)
    elif query.data == "start":
        await start(update, context)

def start_market_listener():
    asyncio.run(market_listener())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=start_market_listener, daemon=True).start()

    bot = Bot(token=TELEGRAM_TOKEN)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()
