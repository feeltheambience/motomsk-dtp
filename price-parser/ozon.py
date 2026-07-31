"""Парсер цен Ozon для запуска на своём ноутбуке.

Заточен под анти-бот защиту Ozon:
  • обычный (видимый) браузер — Ozon так реже показывает капчу;
  • сохранение cookies/сессии между запусками (папка .ozon_profile рядом);
  • реалистичные заголовки, размер окна, локаль;
  • случайные паузы (джиттер), чтобы запросы не шли «как часы»;
  • при капче — не долбить, а сделать паузу и попробовать позже.

Использование:
    python ozon.py "https://www.ozon.ru/product/xxx-123456789/"
    python ozon.py                     # возьмёт ссылки из ozon_products.txt

Установка (один раз):
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import re
import sys
import time
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
PROFILE_DIR = HERE / ".ozon_profile"        # сюда браузер сложит cookies
LINKS_FILE = HERE / "ozon_products.txt"      # по ссылке в строке
OUTPUT_FILE = HERE / "ozon_prices.json"

# Показывать окно браузера? True = видимый (рекомендуется для Ozon).
HEADLESS = False

# Паузы между товарами, сек (берётся случайное значение в этом диапазоне).
DELAY_MIN, DELAY_MAX = 12, 25

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/122.0.0.0 Safari/537.36")


def _sleep(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))


def _prices_from_text(text: str) -> list[int]:
    nums = [int(re.sub(r"\D", "", m)) for m in re.findall(r"\d[\d\s  ]*₽", text)]
    return [n for n in nums if n > 0]


def _price_from_jsonld(page) -> int | None:
    """Пробуем взять цену из структурированных данных (надёжнее вёрстки)."""
    try:
        scripts = page.locator('script[type="application/ld+json"]').all()
    except Exception:
        return None
    for s in scripts:
        try:
            data = json.loads(s.inner_text())
        except Exception:
            continue
        for obj in (data if isinstance(data, list) else [data]):
            offers = obj.get("offers") if isinstance(obj, dict) else None
            if isinstance(offers, dict) and offers.get("price"):
                try:
                    return int(float(offers["price"]))
                except (TypeError, ValueError):
                    pass
    return None


def _is_captcha(page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False
    markers = ("подтвердите, что вы не робот", "доступ ограничен",
               "проверка безопасности", "captcha", "access denied")
    return any(m in body for m in markers)


def fetch_one(context, url: str) -> dict:
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        _sleep(2.5, 4.5)  # дать прогрузиться цене

        if _is_captcha(page):
            return {"ok": False, "error": "капча — Ozon просит проверку", "url": url}

        name = ""
        try:
            name = page.locator("h1").first.inner_text(timeout=6000).strip()
        except Exception:
            pass

        price = _price_from_jsonld(page)
        if price is None:
            prices = _prices_from_text(page.locator("body").inner_text())
            price = min(prices) if prices else None

        if price is None:
            return {"ok": False, "error": "цена не найдена", "url": url}

        return {"ok": True, "name": name, "price": float(price), "url": url}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "url": url}
    finally:
        page.close()


def load_links() -> list[str]:
    if len(sys.argv) > 1:
        return [a for a in sys.argv[1:] if a.strip()]
    if LINKS_FILE.exists():
        return [ln.strip() for ln in LINKS_FILE.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    return []


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Не установлен Playwright. Выполните:\n"
              "    pip install playwright\n"
              "    playwright install chromium")
        sys.exit(1)

    links = load_links()
    if not links:
        print(f"Добавьте ссылки Ozon в {LINKS_FILE.name} (по одной в строке) "
              f"или передайте ссылку аргументом.")
        sys.exit(1)

    results = {}
    with sync_playwright() as pw:
        # Постоянный контекст = браузер помнит cookies → меньше капчи.
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            locale="ru-RU",
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            for i, url in enumerate(links, 1):
                res = fetch_one(context, url)
                if res["ok"]:
                    price = f"{res['price']:,.0f}".replace(",", " ")
                    print(f"[{i}/{len(links)}] ✓ {res['name'][:60]} — {price} ₽")
                    results[url] = res
                else:
                    print(f"[{i}/{len(links)}] ✗ {url}\n        {res['error']}")
                    if "капча" in res["error"]:
                        print("        Ozon дал капчу — останавливаюсь, "
                              "попробуйте снова через 30–60 минут.")
                        break
                if i < len(links):
                    _sleep(DELAY_MIN, DELAY_MAX)
        finally:
            context.close()

    if results:
        OUTPUT_FILE.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nСохранено в {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
