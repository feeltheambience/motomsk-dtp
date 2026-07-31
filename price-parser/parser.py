"""Парсеры цен для Wildberries и Ozon.

Wildberries — через публичный JSON-API карточки товара (быстро, без браузера).
Ozon — через headless-браузер Playwright (у Ozon жёсткая анти-бот защита,
        обычным HTTP-запросом цену не достать).

Каждая функция возвращает dict вида:
    {"ok": True, "name": ..., "price": 1234.0, "old_price": 1500.0, "url": ...}
или при ошибке:
    {"ok": False, "error": "...", "url": ...}
"""

from __future__ import annotations

import re
import logging

import requests

log = logging.getLogger("price-parser")


# --------------------------------------------------------------------------- #
# Wildberries
# --------------------------------------------------------------------------- #

WB_DEST_MOSCOW = -1257786  # регион влияет на цену/наличие; -1257786 ≈ Москва


def wb_extract_article(url_or_id: str) -> int | None:
    """Достаёт числовой артикул (nm) из ссылки WB или принимает его напрямую."""
    s = str(url_or_id).strip()
    if s.isdigit():
        return int(s)
    m = re.search(r"/catalog/(\d+)", s)
    return int(m.group(1)) if m else None


def wb_price(url_or_id: str, dest: int = WB_DEST_MOSCOW) -> dict:
    """Текущая цена товара на Wildberries."""
    article = wb_extract_article(url_or_id)
    if article is None:
        return {"ok": False, "error": "не удалось определить артикул", "url": url_or_id}

    try:
        r = requests.get(
            "https://card.wb.ru/cards/v2/detail",
            params={"appType": 1, "curr": "rub", "dest": dest, "nm": article},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
        products = r.json().get("data", {}).get("products", [])
        if not products:
            return {"ok": False, "error": "товар не найден / нет в наличии",
                    "url": url_or_id}

        p = products[0]
        # Цена лежит в первой размерной позиции, в копейках.
        price_block = {}
        for size in p.get("sizes", []):
            if size.get("price"):
                price_block = size["price"]
                break

        total = price_block.get("total")
        basic = price_block.get("basic")
        if total is None:
            return {"ok": False, "error": "нет цены (возможно, нет в наличии)",
                    "url": url_or_id}

        return {
            "ok": True,
            "source": "wb",
            "name": p.get("name", ""),
            "price": round(total / 100, 2),
            "old_price": round(basic / 100, 2) if basic else None,
            "url": f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
        }
    except Exception as e:  # noqa: BLE001 — хотим не падать, а вернуть ошибку
        log.warning("WB %s: %s", article, e)
        return {"ok": False, "error": str(e), "url": url_or_id}


# --------------------------------------------------------------------------- #
# Ozon (требует playwright: pip install playwright && playwright install chromium)
# --------------------------------------------------------------------------- #

def ozon_price(url: str, headless: bool = True, wait_ms: int = 3000) -> dict:
    """Текущая цена товара на Ozon через headless-браузер."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False,
                "error": "не установлен playwright (pip install playwright)",
                "url": url}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            page = browser.new_page(
                locale="ru-RU",
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/122.0 Safari/537.36"),
            )
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(wait_ms)  # дать прогрузиться цене

            name = ""
            try:
                name = page.locator("h1").first.inner_text(timeout=5000).strip()
            except Exception:  # noqa: BLE001
                pass

            # Ищем все вхождения "… ₽" и берём минимальное как актуальную цену
            body = page.locator("body").inner_text()
            browser.close()

        prices = [
            int(re.sub(r"\D", "", m))
            for m in re.findall(r"\d[\d\s  ]*₽", body)
        ]
        prices = [p for p in prices if p > 0]
        if not prices:
            return {"ok": False, "error": "цена на странице не найдена "
                    "(возможно, капча или нет в наличии)", "url": url}

        return {
            "ok": True,
            "source": "ozon",
            "name": name,
            "price": float(min(prices)),
            "old_price": float(max(prices)) if len(set(prices)) > 1 else None,
            "url": url,
        }
    except Exception as e:  # noqa: BLE001
        log.warning("Ozon %s: %s", url, e)
        return {"ok": False, "error": str(e), "url": url}


def fetch_price(url: str) -> dict:
    """Определяет магазин по ссылке и вызывает нужный парсер."""
    low = url.lower()
    if "wildberries" in low or "wb.ru" in low or str(url).isdigit():
        return wb_price(url)
    if "ozon" in low:
        return ozon_price(url)
    return {"ok": False, "error": "неизвестный магазин (нужен WB или Ozon)",
            "url": url}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Использование: python parser.py <ссылка или артикул WB>")
        sys.exit(1)
    from pprint import pprint
    pprint(fetch_price(sys.argv[1]))
