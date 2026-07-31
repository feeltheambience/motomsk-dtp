"""Трекер цен: раз в запуск обходит товары из products.json, сохраняет цены
в prices.json и, если цена изменилась (или упала ниже target), шлёт сообщение
в Telegram.

Запуск вручную:      python tracker.py
По расписанию:       cron / GitHub Actions раз в несколько часов

Уведомления в Telegram включаются переменными окружения:
    TG_BOT_TOKEN — токен бота (от @BotFather)
    TG_CHAT_ID   — ваш chat id (узнать у @userinfobot)
Без них скрипт просто печатает изменения в консоль.
"""

from __future__ import annotations

import os
import json
import time
import logging
from pathlib import Path

import requests

from parser import fetch_price

log = logging.getLogger("tracker")

HERE = Path(__file__).parent
PRODUCTS_FILE = HERE / "products.json"
PRICES_FILE = HERE / "prices.json"

# Пауза между товарами, чтобы не долбить магазины слишком часто.
DELAY_SECONDS = 5


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def notify_telegram(text: str) -> None:
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        log.info("[telegram отключён] %s", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось отправить в Telegram: %s", e)


def fmt(v) -> str:
    return f"{v:,.0f}".replace(",", " ") if v is not None else "—"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    products = load_json(PRODUCTS_FILE, [])
    if not products:
        log.info("Добавьте товары в %s", PRODUCTS_FILE.name)
        return

    history = load_json(PRICES_FILE, {})

    for item in products:
        url = item["url"]
        target = item.get("target")  # желаемая цена для уведомления «упала ниже»
        title = item.get("title", "")

        result = fetch_price(url)
        if not result.get("ok"):
            log.info("✗ %s — %s", title or url, result.get("error"))
            time.sleep(DELAY_SECONDS)
            continue

        name = title or result.get("name") or url
        price = result["price"]
        prev = history.get(url, {}).get("price")

        log.info("• %s — %s ₽", name, fmt(price))

        # Уведомляем при первом появлении, изменении цены или падении ниже target.
        changed = prev is not None and price != prev
        below_target = target is not None and price <= target

        if changed or below_target:
            arrow = "🔻" if (prev and price < prev) else "🔺" if prev else "🆕"
            lines = [f"{arrow} <b>{name}</b>", f"Цена: <b>{fmt(price)} ₽</b>"]
            if prev is not None:
                lines.append(f"Было: {fmt(prev)} ₽")
            if below_target:
                lines.append(f"✅ Ниже цели {fmt(target)} ₽")
            lines.append(result["url"])
            notify_telegram("\n".join(lines))

        history[url] = {
            "name": name,
            "price": price,
            "old_price": result.get("old_price"),
            "checked_at": int(time.time()),
        }
        time.sleep(DELAY_SECONDS)

    save_json(PRICES_FILE, history)
    log.info("Готово. Данные сохранены в %s", PRICES_FILE.name)


if __name__ == "__main__":
    main()
