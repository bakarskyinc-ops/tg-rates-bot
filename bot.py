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

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
ALPHA_KEY = os.environ["ALPHA_KEY"]

UPDATE_HOURS = [9, 14, 20]
TZ_OFFSET = timedelta(hours=5)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ─────────────────────────────────────────────
# Получение курсов через Alpha Vantage
# ─────────────────────────────────────────────

async def get_price(session, from_currency: str) -> float | None:
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=CURRENCY_EXCHANGE_RATE"
        f"&from_currency={from_currency}"
        f"&to_currency=USD"
        f"&apikey={ALPHA_KEY}"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json()
            rate = data["Realtime Currency Exchange Rate"]["5. Exchange Rate"]
            return float(rate)
    except Exception as e:
        logger.warning(f"{from_currency} failed: {e}")
        return None


async def get_metal_prices() -> dict | None:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:
        gold     = await get_price(session, "XAU")
        silver   = await get_price(session, "XAG")
        platinum = await get_price(session, "XPT")

        if gold and silver and platinum:
            logger.info(f"Курсы: gold={gold}, silver={silver}, platinum={platinum}")
            return {"gold": gold, "silver": silver, "platinum": platinum}

    logger.error("Не удалось получить курсы")
    return None


def format_message(gold: float, silver: float, platinum: float) -> str:
    return (
        f"Gold ${gold:,.2f}  |  "
        f"Silver ${silver:,.2f}  |  "
        f"Platinum ${platinum:,.2f}"
    )


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

    metals = await get_metal_prices()
    if not metals:
        logger.warning("Курсы недоступны, пропуск")
        return

    text = format_message(metals["gold"], metals["silver"], metals["platinum"])

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
            logger.info(f"Создано и закреплено. Добавь в Railway: PINNED_MSG_ID={pinned_message_id}")
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")


# ─────────────────────────────────────────────
# Расписание: 09:00, 14:00, 20:00 Ташкент
# ─────────────────────────────────────────────

async def scheduler():
    await asyncio.sleep(3)
    logger.info(f"Планировщик запущен. Обновления в {UPDATE_HOURS} по UTC+5")
    await send_or_update_rates()

    while True:
        now = datetime.now(timezone.utc) + TZ_OFFSET
        current_minutes = now.hour * 60 + now.minute

        next_minutes = None
        for h in UPDATE_HOURS:
            target = h * 60
            if target > current_minutes:
                next_minutes = target
                break

        if next_minutes is None:
            next_minutes = UPDATE_HOURS[0] * 60 + 24 * 60

        wait_seconds = (next_minutes - current_minutes) * 60 - now.second
        next_time = (now + timedelta(seconds=wait_seconds)).strftime("%H:%M")
        logger.info(f"Следующее обновление в {next_time} (через {wait_seconds//60} мин)")

        await asyncio.sleep(wait_seconds)
        await send_or_update_rates()


# ─────────────────────────────────────────────
# Команды
# ─────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "✅ Бот курсов металлов активен.\n"
        "Обновления в 09:00, 14:00, 20:00 по Ташкенту.\n\n"
        "/rates — текущие курсы\n"
        "/status — статус бота"
    )

@dp.message(Command("rates"))
async def cmd_rates(message: Message):
    metals = await get_metal_prices()
    if metals:
        await message.answer(format_message(metals["gold"], metals["silver"], metals["platinum"]))
    else:
        await message.answer("❌ Не удалось получить курсы.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    now = datetime.now(timezone.utc) + TZ_OFFSET
    await message.answer(
        f"🤖 Статус бота\n"
        f"Время (UTC+5): {now.strftime('%d.%m.%Y %H:%M')}\n"
        f"PINNED_MSG_ID: {pinned_message_id or 'не задан'}\n"
        f"Расписание: {', '.join(f'{h}:00' for h in UPDATE_HOURS)}"
    )


# ─────────────────────────────────────────────
# Запуск
# ─────────────────────────────────────────────

async def main():
    await load_pinned_msg_id()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
