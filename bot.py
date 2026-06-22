import os
import asyncio
import logging
import ssl
from datetime import datetime, timezone, timedelta
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ["BOT_TOKEN"]
CHANNEL_ID   = os.environ["CHANNEL_ID"]
RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]

UPDATE_HOURS = [9, 14, 20]
TZ_OFFSET    = timedelta(hours=5)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# ─────────────────────────────────────────────
# Получение курсов
# ─────────────────────────────────────────────

BASE_URL = "https://real-time-metal-prices.p.rapidapi.com/api/v1/radpidhub"

METALS = {
    "gold":   "gold-price/USD",
    "silver": "silver-price/USD",
}

async def get_metal_prices() -> dict | None:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    headers = {
        "x-rapidapi-key":  RAPIDAPI_KEY,
        "x-rapidapi-host": "real-time-metal-prices.p.rapidapi.com",
        "Content-Type":    "application/json",
    }

    result = {}
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        for metal, path in METALS.items():
            url = f"{BASE_URL}/{path}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                    logger.info(f"{metal} raw response: {data}")
                    # Пробуем разные поля
                    price = (
                        data.get("price_usd_per_troy_oz") or
                        data.get("price") or
                        data.get("rate") or
                        data.get("ask") or
                        data.get("Price") or
                        0
                    )
                    price = float(price)
                    if price > 0:
                        result[metal] = price
                    else:
                        logger.warning(f"{metal} — нет цены: {data}")
            except Exception as e:
                logger.warning(f"{metal} failed: {e}")

    if all(k in result for k in ("gold", "silver")):
        return result

    logger.error(f"Не удалось получить курсы. Получено: {result}")
    return None


def is_trading_day() -> bool:
    now = datetime.now(timezone.utc) + TZ_OFFSET
    return now.weekday() < 5


def format_message(gold: float, silver: float) -> str:
    return f"Gold ${gold:,.2f}  |  Silver ${silver:,.2f}"


# ─────────────────────────────────────────────
# Закреплённое сообщение
# ─────────────────────────────────────────────

pinned_message_id: int | None = None


async def load_pinned_msg_id():
    global pinned_message_id
    env_id = os.environ.get("PINNED_MSG_ID")
    if env_id:
        pinned_message_id = int(env_id)
        logger.info(f"PINNED_MSG_ID: {pinned_message_id}")


async def send_or_update_rates():
    global pinned_message_id

    if not is_trading_day():
        logger.info("Выходной — пропуск")
        return

    metals = await get_metal_prices()
    if not metals:
        return

    text = format_message(metals["gold"], metals["silver"])

    try:
        if pinned_message_id:
            await bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=pinned_message_id,
                text=text
            )
            logger.info(f"Обновлено: {text}")
        else:
            msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
            pinned_message_id = msg.message_id
            await bot.pin_chat_message(
                chat_id=CHANNEL_ID,
                message_id=msg.message_id,
                disable_notification=True
            )
            logger.info(f"Создано. PINNED_MSG_ID={pinned_message_id}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")


# ─────────────────────────────────────────────
# Расписание
# ─────────────────────────────────────────────

async def scheduler():
    await asyncio.sleep(3)
    logger.info(f"Планировщик запущен. {UPDATE_HOURS} UTC+5, Пн-Пт")
    await send_or_update_rates()

    while True:
        now = datetime.now(timezone.utc) + TZ_OFFSET
        cur = now.hour * 60 + now.minute

        nxt = next((h * 60 for h in UPDATE_HOURS if h * 60 > cur), UPDATE_HOURS[0] * 60 + 1440)
        wait = (nxt - cur) * 60 - now.second
        logger.info(f"Следующее в {(now + timedelta(seconds=wait)).strftime('%H:%M')} (через {wait//60} мин)")

        await asyncio.sleep(wait)
        await send_or_update_rates()


# ─────────────────────────────────────────────
# Команды
# ─────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "✅ Бот курсов металлов активен.\n"
        "Обновления в 09:00, 14:00, 20:00 по Ташкенту (Пн-Пт).\n\n"
        "/rates — текущие курсы\n"
        "/status — статус"
    )

@dp.message(Command("rates"))
async def cmd_rates(message: Message):
    metals = await get_metal_prices()
    if metals:
        await message.answer(format_message(metals["gold"], metals["silver"]))
    else:
        await message.answer("❌ Не удалось получить курсы.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    now = datetime.now(timezone.utc) + TZ_OFFSET
    await message.answer(
        f"Время: {now.strftime('%d.%m.%Y %H:%M')}\n"
        f"День: {'рабочий' if is_trading_day() else 'выходной'}\n"
        f"PINNED_MSG_ID: {pinned_message_id or 'не задан'}"
    )


async def main():
    await load_pinned_msg_id()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
