"""
Парсер kody.su - собирает все DEF-коды мобильных операторов РФ (900-999)
и строит базу для точного поиска по префиксу номера.
Запускать один раз: python3 scraper.py
"""

import re
import json
import time
import urllib.request
from pathlib import Path

REGION_TO_CITY = {
    "Москва": ("Москва", 13_010_000, "Europe/Moscow"),
    "Московская область": ("Москва", 13_010_000, "Europe/Moscow"),
    "Санкт-Петербург": ("Санкт-Петербург", 5_600_000, "Europe/Moscow"),
    "Ленинградская область": ("Санкт-Петербург", 5_600_000, "Europe/Moscow"),
    "Свердловская область": ("Екатеринбург", 1_544_000, "Asia/Yekaterinburg"),
    "Челябинская область": ("Челябинск", 1_189_000, "Asia/Yekaterinburg"),
    "Пермский край": ("Пермь", 1_065_000, "Asia/Yekaterinburg"),
    "Тюменская область": ("Тюмень", 847_000, "Asia/Yekaterinburg"),
    "Ханты-Мансийский АО": ("Ханты-Мансийск", 105_000, "Asia/Yekaterinburg"),
    "Ямало-Ненецкий АО": ("Салехард", 54_000, "Asia/Yekaterinburg"),
    "Курганская область": ("Курган", 333_000, "Asia/Yekaterinburg"),
    "Новосибирская область": ("Новосибирск", 1_633_000, "Asia/Novosibirsk"),
    "Омская область": ("Омск", 1_173_000, "Asia/Omsk"),
    "Томская область": ("Томск", 576_000, "Asia/Tomsk"),
    "Кемеровская область": ("Кемерово", 559_000, "Asia/Novosibirsk"),
    "Алтайский край": ("Барнаул", 639_000, "Asia/Barnaul"),
    "Республика Алтай": ("Горно-Алтайск", 66_000, "Asia/Barnaul"),
    "Красноярский край": ("Красноярск", 1_200_000, "Asia/Krasnoyarsk"),
    "Республика Хакасия": ("Абакан", 193_000, "Asia/Krasnoyarsk"),
    "Республика Тыва": ("Кызыл", 116_000, "Asia/Krasnoyarsk"),
    "Иркутская область": ("Иркутск", 624_000, "Asia/Irkutsk"),
    "Республика Бурятия": ("Улан-Удэ", 435_000, "Asia/Irkutsk"),
    "Забайкальский край": ("Чита", 347_000, "Asia/Chita"),
    "Хабаровский край": ("Хабаровск", 620_000, "Asia/Vladivostok"),
    "Хабаровский Край": ("Хабаровск", 620_000, "Asia/Vladivostok"),
    "Приморский край": ("Владивосток", 605_000, "Asia/Vladivostok"),
    "Амурская область": ("Благовещенск", 244_000, "Asia/Yakutsk"),
    "Еврейская АО": ("Биробиджан", 73_000, "Asia/Vladivostok"),
    "Сахалинская область": ("Южно-Сахалинск", 182_000, "Asia/Sakhalin"),
    "Магаданская область": ("Магадан", 90_000, "Asia/Magadan"),
    "Камчатский край": ("Петропавловск-Камчатский", 181_000, "Asia/Kamchatka"),
    "Чукотский АО": ("Анадырь", 15_000, "Asia/Anadyr"),
    "Республика Саха (Якутия)": ("Якутск", 369_000, "Asia/Yakutsk"),
    "Краснодарский край": ("Краснодар", 1_062_000, "Europe/Moscow"),
    "Ростовская область": ("Ростов-на-Дону", 1_142_000, "Europe/Moscow"),
    "Волгоградская область": ("Волгоград", 1_028_000, "Europe/Moscow"),
    "Астраханская область": ("Астрахань", 524_000, "Europe/Moscow"),
    "Республика Адыгея": ("Майкоп", 144_000, "Europe/Moscow"),
    "Республика Калмыкия": ("Элиста", 103_000, "Europe/Moscow"),
    "Республика Дагестан": ("Махачкала", 625_000, "Europe/Moscow"),
    "Республика Ингушетия": ("Магас", 10_000, "Europe/Moscow"),
    "Чеченская Республика": ("Грозный", 340_000, "Europe/Moscow"),
    "Кабардино-Балкарская Республика": ("Нальчик", 280_000, "Europe/Moscow"),
    "Карачаево-Черкесская Республика": ("Черкесск", 129_000, "Europe/Moscow"),
    "Республика Северная Осетия": ("Владикавказ", 310_000, "Europe/Moscow"),
    "Ставропольский край": ("Ставрополь", 461_000, "Europe/Moscow"),
    "Республика Крым": ("Симферополь", 370_000, "Europe/Moscow"),
    "Республика Башкортостан": ("Уфа", 1_144_000, "Asia/Yekaterinburg"),
    "Республика Татарстан": ("Казань", 1_318_000, "Europe/Moscow"),
    "Нижегородская область": ("Нижний Новгород", 1_250_000, "Europe/Moscow"),
    "Самарская область": ("Самара", 1_178_000, "Europe/Samara"),
    "Саратовская область": ("Саратов", 838_000, "Europe/Saratov"),
    "Оренбургская область": ("Оренбург", 575_000, "Asia/Yekaterinburg"),
    "Ульяновская область": ("Ульяновск", 640_000, "Europe/Ulyanovsk"),
    "Пензенская область": ("Пенза", 528_000, "Europe/Moscow"),
    "Республика Мордовия": ("Саранск", 318_000, "Europe/Moscow"),
    "Республика Марий Эл": ("Йошкар-Ола", 279_000, "Europe/Moscow"),
    "Чувашская Республика": ("Чебоксары", 496_000, "Europe/Moscow"),
    "Республика Удмуртия": ("Ижевск", 646_000, "Europe/Samara"),
    "Кировская область": ("Киров", 507_000, "Europe/Moscow"),
    "Республика Коми": ("Сыктывкар", 259_000, "Europe/Moscow"),
    "Республика Карелия": ("Петрозаводск", 285_000, "Europe/Moscow"),
    "Архангельская область": ("Архангельск", 351_000, "Europe/Moscow"),
    "Мурманская область": ("Мурманск", 302_000, "Europe/Moscow"),
    "Вологодская область": ("Вологда", 312_000, "Europe/Moscow"),
    "Новгородская область": ("Великий Новгород", 224_000, "Europe/Moscow"),
    "Псковская область": ("Псков", 210_000, "Europe/Moscow"),
    "Тверская область": ("Тверь", 425_000, "Europe/Moscow"),
    "Ярославская область": ("Ярославль", 609_000, "Europe/Moscow"),
    "Костромская область": ("Кострома", 288_000, "Europe/Moscow"),
    "Ивановская область": ("Иваново", 408_000, "Europe/Moscow"),
    "Владимирская область": ("Владимир", 358_000, "Europe/Moscow"),
    "Рязанская область": ("Рязань", 533_000, "Europe/Moscow"),
    "Тульская область": ("Тула", 497_000, "Europe/Moscow"),
    "Орловская область": ("Орёл", 318_000, "Europe/Moscow"),
    "Калужская область": ("Калуга", 340_000, "Europe/Moscow"),
    "Смоленская область": ("Смоленск", 326_000, "Europe/Moscow"),
    "Брянская область": ("Брянск", 403_000, "Europe/Moscow"),
    "Курская область": ("Курск", 450_000, "Europe/Moscow"),
    "Белгородская область": ("Белгород", 397_000, "Europe/Moscow"),
    "Воронежская область": ("Воронеж", 1_058_000, "Europe/Moscow"),
    "Липецкая область": ("Липецк", 508_000, "Europe/Moscow"),
    "Тамбовская область": ("Тамбов", 293_000, "Europe/Moscow"),
    "Калининградская область": ("Калининград", 493_000, "Europe/Kaliningrad"),
    "Республика Калмыкия": ("Элиста", 103_000, "Europe/Moscow"),
    "Россия": ("Москва", 13_010_000, "Europe/Moscow"),
}


def fetch_page(code: int) -> str | None:
    url = f"https://www.kody.su/mobile/{code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        print(f"  Ошибка {code}: {e}")
        return None


def parse_rows(html: str, def_code: str) -> list[dict]:
    """
    Парсит таблицу с kody.su и возвращает список записей вида:
    {prefix: "9001234", operator: "Теле2", region: "Краснодарский край", city: "Краснодар", ...}
    """
    results = []
    # Ищем строки таблицы
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 3:
            continue
        nums_raw = re.sub(r'<[^>]+>', '', cells[0]).strip()
        operator = re.sub(r'<[^>]+>', '', cells[1]).strip()
        region = re.sub(r'<[^>]+>', '', cells[2]).strip()

        if not nums_raw or not operator or not region:
            continue
        if region not in REGION_TO_CITY:
            continue

        city, population, timezone = REGION_TO_CITY[region]

        # Парсим номера: "900-000xxxx 001xxxx ..."
        # Убираем "DEF-" префикс
        nums_clean = re.sub(rf'^{def_code}-', '', nums_raw)
        # Каждый токен - отдельный диапазон
        tokens = nums_clean.split()
        for token in tokens:
            # Пропускаем "..." и числа типа "0135049"
            if token == '...' or re.match(r'^\d{7}$', token):
                continue
            # Убираем x и всё после первого x
            m = re.match(r'^(\d+)x', token)
            if m:
                prefix = def_code + m.group(1)
                results.append({
                    "prefix": prefix,
                    "operator": operator,
                    "region": region,
                    "city": city,
                    "population": population,
                    "timezone": timezone,
                })
    return results


def build_db():
    all_entries = []
    for code in range(900, 1000):
        print(f"Загружаю код {code}...")
        html = fetch_page(code)
        if not html:
            continue
        if "404" in html[:500] or "не найден" in html[:500].lower():
            continue
        entries = parse_rows(html, str(code))
        print(f"  → {len(entries)} записей")
        all_entries.extend(entries)
        time.sleep(0.5)  # вежливая пауза

    # Сортируем по убыванию длины префикса - для правильного поиска
    all_entries.sort(key=lambda x: len(x["prefix"]), reverse=True)

    with open("codes_db.json", "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f"\nГотово! Сохранено {len(all_entries)} записей в codes_db.json")


if __name__ == "__main__":
    build_db()
