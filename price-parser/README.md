# Трекер цен Wildberries + Ozon

Небольшой парсер, который следит за ценами товаров и шлёт уведомление
в Telegram, когда цена меняется или падает ниже заданной.

- **Wildberries** — через публичный JSON-API карточки (быстро, без браузера).
- **Ozon** — через headless-браузер Playwright (у Ozon сильная анти-бот
  защита, обычным HTTP-запросом цену не получить).

## Установка

```bash
cd price-parser
pip install -r requirements.txt
# только если нужен Ozon:
playwright install chromium
```

## Настройка товаров

Отредактируйте `products.json`. Для WB можно указать полную ссылку или
просто артикул. `target` — необязательная цель: уведомление придёт, когда
цена станет ≤ этого значения.

```json
[
  { "title": "Наушники", "url": "https://www.wildberries.ru/catalog/12345678/detail.aspx", "target": 2000 },
  { "title": "Кофеварка", "url": "https://www.ozon.ru/product/xxx-123456789/", "target": 5000 }
]
```

## Уведомления в Telegram

Задайте переменные окружения (без них изменения просто печатаются в консоль):

```bash
export TG_BOT_TOKEN="токен_от_@BotFather"
export TG_CHAT_ID="ваш_chat_id"   # узнать у @userinfobot
```

## Запуск

Проверить один товар:

```bash
python parser.py https://www.wildberries.ru/catalog/12345678/detail.aspx
python parser.py 12345678          # можно просто артикул WB
```

Обойти все товары из `products.json` и сохранить цены в `prices.json`:

```bash
python tracker.py
```

## «Чтобы всегда видеть цену» — по расписанию

Запускайте `tracker.py` регулярно. Пример cron (раз в 3 часа):

```
0 */3 * * * cd /path/to/price-parser && /usr/bin/python3 tracker.py >> tracker.log 2>&1
```

Или GitHub Actions (`.github/workflows/prices.yml`), где токен и chat id
хранятся в Secrets репозитория.

## Важно

- Оба магазина **запрещают автоматический сбор** в правилах использования.
  Для личного отслеживания нескольких товаров это обычно не проблема, но
  держите **низкую частоту** запросов (раз в несколько часов, не чаще).
- Структура ответа WB и вёрстка Ozon периодически меняются — если парсер
  перестал находить цену, поправьте разбор в `parser.py`.
- Ozon может отдать капчу вместо страницы — тогда вернётся ошибка «цена не
  найдена». Помогают редкие запросы и, при необходимости, не-headless режим.
