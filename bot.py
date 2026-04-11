"""
Telegram-бот: точное определение города по мобильному номеру РФ.
Использует базу данных codes_db.json собранную scraper.py.
"""

import os
import re
import json
import logging
from datetime import datetime
import zoneinfo
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Загружаем базу
DB_PATH = Path(__file__).parent / "codes_db.json"
if DB_PATH.exists():
    with open(DB_PATH, encoding="utf-8") as f:
        ENTRIES = json.load(f)
    print(f"База загружена: {len(ENTRIES)} записей")
else:
    ENTRIES = []
    print("ВНИМАНИЕ: codes_db.json не найден! Запусти scraper.py сначала.")


def lookup(digits10: str) -> dict | None:
    """Ищет совпадение по убыванию длины префикса."""
    for entry in ENTRIES:
        prefix = entry["prefix"]
        if digits10.startswith(prefix):
            return entry
    return None


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    return None


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
    except Exception:
        return "н/д"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(ENTRIES)
    await update.message.reply_text(
        f"Привет! База содержит {count:,} записей по диапазонам номеров РФ.\n\n"
        "Отправь мобильный номер - скажу точный город, оператора и местное время.\n\n"
        "Форматы: +7 916 123 45 67 / 89161234567 / 9161234567\n\n"
        "⚠️ Это регион выдачи номера при подключении. После 2013 г. можно сменить оператора, сохранив номер."
    )


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    digits = normalize_phone(raw)

    if not digits:
        await update.message.reply_text(
            "Не похоже на российский номер. Попробуй: +7 916 1234567 или 89161234567"
        )
        return

    if digits[0] != "9":
        await update.message.reply_text(
            "Этот бот работает только с мобильными номерами (начинаются на 9)."
        )
        return

    if not ENTRIES:
        await update.message.reply_text(
            "База данных не загружена. Запусти scraper.py сначала."
        )
        return

    entry = lookup(digits)

    if not entry:
        await update.message.reply_text(
            f"Номер `{raw}` не найден в базе.",
            parse_mode="Markdown"
        )
        return

    lines = [
        f"📞 Номер: `{raw}`",
        f"📡 Оператор: *{entry['operator']}*",
        f"📍 Регион: *{entry['region']}*",
        f"🏙 Город: *{entry['city']}*",
        f"👥 Население: *{format_population(entry['population'])}*",
        f"🕐 Местное время: *{get_local_time(entry['timezone'])}*",
        "",
        "⚠️ _Регион выдачи номера при подключении, не текущее местонахождение._",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone))

    print("Бот запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
