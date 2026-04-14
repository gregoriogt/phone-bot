"""
Telegram-бот: определение города/региона по мобильному номеру РФ
+ локальное время
+ ссылки для открытия в Telegram и MAX
+ логирование использований в Google Sheets через Apps Script webhook

Переменные окружения:
- BOT_TOKEN
- GOOGLE_SCRIPT_URL   (необязательно, если не задана, логирование отключено)

Использует базу данных codes_db.json, собранную scraper.py.
"""

import os
import re
import json
import logging
from datetime import datetime
import zoneinfo
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "codes_db.json"
if DB_PATH.exists():
    with open(DB_PATH, encoding="utf-8") as f:
        ENTRIES = json.load(f)
    logger.info("База загружена: %s записей", len(ENTRIES))
else:
    ENTRIES = []
    logger.warning("codes_db.json не найден. Запусти scraper.py сначала.")


def lookup(digits10: str):
    """Ищет совпадение по убыванию длины префикса."""
    for entry in ENTRIES:
        prefix = entry["prefix"]
        if digits10.startswith(prefix):
            return entry
    return None


def normalize_phone(raw: str):
    """
    Принимает:
    +79118339000
    89118339000
    79118339000

    Возвращает 10 цифр без префикса страны, например:
    9118339000
    """
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    return None


def format_russian_phone(digits10: str) -> str:
    """Возвращает номер в формате +7XXXXXXXXXX."""
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


def build_messenger_links(phone_e164: str) -> tuple[str, str]:
    telegram_link = f"http://t.me/{phone_e164}"
    max_link = f"https://max.ru/{phone_e164}"
    return telegram_link, max_link


def log_to_google_sheets(update: Update, phone_e164: str, entry):
    """
    Отправляет событие использования в Google Sheets через Apps Script webhook.
    Если GOOGLE_SCRIPT_URL не задан, функция тихо завершается.
    """
    url = os.environ.get("GOOGLE_SCRIPT_URL")
    if not url:
        return

    try:
        user = update.effective_user
        payload = {
            "timestamp_utc": datetime.utcnow().isoformat(),
            "user_id": user.id if user else "",
            "username": user.username if user and user.username else "",
            "first_name": user.first_name if user and user.first_name else "",
            "phone": phone_e164,
            "region": entry["region"] if entry else "",
            "city": entry["city"] if entry else "",
            "operator": entry["operator"] if entry else "",
        }

        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.warning("Не удалось записать аналитику в Google Sheets: %s", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(ENTRIES)
    if update.message:
        await update.message.reply_text(
            f"Привет! База содержит {count:,} записей по диапазонам номеров РФ.\n\n"
            "Отправь мобильный номер, скажу город, оператора, местное время и дам ссылки для Telegram/MAX.\n\n"
            "Поддерживаемые форматы:\n"
            "+79118339000\n"
            "89118339000\n"
            "79118339000\n\n"
            "⚠️ Это регион выдачи номера при подключении. После 2013 г. можно сменить оператора, сохранив номер."
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
        await update.message.reply_text(
            "База данных не загружена. Нужен файл codes_db.json."
        )
        return

    phone_e164 = format_russian_phone(digits)
    telegram_link, max_link = build_messenger_links(phone_e164)
    entry = lookup(digits)

    log_to_google_sheets(update, phone_e164, entry)

    if not entry:
        lines = [
            f"📞 Номер: `{phone_e164}`",
            "",
            f"💬 [Открыть в Telegram]({telegram_link})",
            f"💬 [Открыть в MAX]({max_link})",
            "",
            "Номер не найден в базе регионов.",
        ]
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    lines = [
        f"📞 Номер: `{phone_e164}`",
        f"📡 Оператор: *{entry['operator']}*",
        f"📍 Регион: *{entry['region']}*",
        f"🏙 Город: *{entry['city']}*",
        f"👥 Население: *{format_population(entry['population'])}*",
        f"🕐 Местное время: *{get_local_time(entry['timezone'])}*",
        "",
        f"💬 [Открыть в Telegram]({telegram_link})",
        f"💬 [Открыть в MAX]({max_link})",
        "",
        "⚠️ _Регион выдачи номера при подключении, не текущее местонахождение._",
    ]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения Railway.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone))

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
