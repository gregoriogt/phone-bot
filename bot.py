"""
Phone lookup Telegram bot with city facts on demand.
"""

import os
import re
import json
import logging
from datetime import datetime
import zoneinfo
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "codes_db.json"
FACTS_PATH = BASE_DIR / "city_facts.json"

if DB_PATH.exists():
    with open(DB_PATH, encoding="utf-8") as f:
        ENTRIES = json.load(f)
    logger.info("База загружена: %s записей", len(ENTRIES))
else:
    ENTRIES = []
    logger.warning("codes_db.json не найден.")

if FACTS_PATH.exists():
    with open(FACTS_PATH, encoding="utf-8") as f:
        CITY_FACTS = json.load(f)
    logger.info("База фактов загружена: %s городов", len(CITY_FACTS))
else:
    CITY_FACTS = {}
    logger.warning("city_facts.json не найден.")


def lookup(digits10: str):
    for entry in ENTRIES:
        prefix = entry["prefix"]
        if digits10.startswith(prefix):
            return entry
    return None


def normalize_phone(raw: str):
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    return None


def format_russian_phone(digits10: str) -> str:
    return f"+7{digits10}"


def format_population(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} млн чел."
    return f"{n // 1_000} тыс. чел."


def get_local_time(tz_name: str) -> str:
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        now = datetime.now(tz)
        offset = now.strftime("%z")
        offset_fmt = f"UTC{offset[:3]}:{offset[3:]}"
        return f"{now.strftime('%H:%M')} ({offset_fmt})"
    except Exception as e:
        logger.exception("Ошибка при определении локального времени: %s", e)
        return "н/д"


def build_telegram_link(phone_e164: str) -> str:
    return f"http://t.me/{phone_e164}"


def facts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Факты", callback_data="city_facts")]
    ])


def format_city_facts(city: str) -> str:
    data = CITY_FACTS.get(city)
    if not data:
        return f"{city}\n\nПо этому городу пока нет заготовленных фактов."

    lines = [city, "", "Факты:"]
    for item in data.get("facts", []):
        lines.append(f"- {item}")

    lines.extend(["", "Заходы:"])
    for item in data.get("openers", []):
        lines.append(f"- {item}")

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(ENTRIES)
    await update.message.reply_text(
        f"Привет! База содержит {count:,} записей по диапазонам номеров РФ.\n\n"
        "Отправь мобильный номер, скажу город, оператора, местное время и дам ссылку для Telegram.\n\n"
        "Поддерживаемые форматы:\n"
        "+79118339000\n"
        "89118339000\n"
        "79118339000"
    )


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw = update.message.text.strip()
    digits = normalize_phone(raw)

    if not digits:
        await update.message.reply_text(
            "Не похоже на российский номер. Используй один из форматов:\n"
            "+79118339000\n"
            "89118339000\n"
            "79118339000"
        )
        return

    if digits[0] != "9":
        await update.message.reply_text(
            "Этот бот работает только с мобильными номерами, которые начинаются на 9."
        )
        return

    if not ENTRIES:
        await update.message.reply_text("База данных не загружена. Нужен файл codes_db.json.")
        return

    phone_e164 = format_russian_phone(digits)
    telegram_link = build_telegram_link(phone_e164)
    entry = lookup(digits)

    if not entry:
        lines = [
            f"📞 Номер: `{phone_e164}`",
            "",
            f"💬 [Открыть в Telegram]({telegram_link})",
            "",
            "Номер не найден в базе регионов.",
        ]
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    context.user_data["last_city"] = entry["city"]

    lines = [
        f"📞 Номер: `{phone_e164}`",
        f"📡 Оператор: *{entry['operator']}*",
        f"📍 Регион: *{entry['region']}*",
        f"🏙 Город: *{entry['city']}*",
        f"👥 Население: *{format_population(entry['population'])}*",
        f"🕐 Местное время: *{get_local_time(entry['timezone'])}*",
        "",
        f"💬 [Открыть в Telegram]({telegram_link})",
        "",
        "⚠️ _Регион выдачи номера при подключении, не текущее местонахождение._",
    ]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=facts_keyboard(),
    )


async def facts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    city = context.user_data.get("last_city")
    if not city:
        await query.message.reply_text("Сначала проверь номер, чтобы я понял город.")
        return

    await query.message.reply_text(format_city_facts(city))


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(facts_callback, pattern="^city_facts$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone))

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
