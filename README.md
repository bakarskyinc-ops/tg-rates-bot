# WYLDAN BAKARSKY — Бот курсов золота

Бот обновляет закреплённое сообщение в Telegram-канале каждые 5 минут.  
Показывает: курс USD (ЦБ РУз), золото и серебро (spot, за грамм и унцию).

---

## Деплой на Railway — пошагово

### 1. Создай бота в Telegram
1. Открой [@BotFather](https://t.me/BotFather)
2. `/newbot` → придумай имя → получи **BOT_TOKEN**

### 2. Добавь бота в канал
1. Зайди в настройки канала → Администраторы
2. Добавь своего бота как администратора
3. Выдай права: **Отправка сообщений** + **Редактирование сообщений** + **Закрепление сообщений**

### 3. Узнай CHANNEL_ID
Перешли любое сообщение из канала боту [@userinfobot](https://t.me/userinfobot)  
Он покажет ID вида `-1001234567890` — это и есть твой CHANNEL_ID.

### 4. Загрузи на GitHub
```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/ТВОЙ_ЮЗЕР/tg-rates-bot.git
git push -u origin main
```

### 5. Деплой на Railway
1. Зайди на [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → выбери репозиторий
3. Railway сам определит Python и установит зависимости

### 6. Добавь переменные окружения
В Railway: вкладка **Variables** → добавь:

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | токен от BotFather |
| `CHANNEL_ID` | `-1001234567890` (твой ID) |
| `UPDATE_INTERVAL` | `300` (5 минут) |

### 7. Первый запуск
- Бот отправит первое сообщение в канал и закрепит его
- В логах Railway появится: `PINNED_MSG_ID=12345`
- Скопируй это число и добавь в Variables: `PINNED_MSG_ID=12345`
- Это нужно чтобы после перезапуска бот редактировал то же сообщение

---

## Команды бота (в личке)
- `/rates` — получить текущие курсы
- `/status` — статус бота и ID закреплённого сообщения

---

## Источники данных
- **USD/UZS** — [cbu.uz](https://cbu.uz) (Центральный банк Узбекистана)
- **XAU, XAG** — [metals.live](https://metals.live) (spot, бесплатно, без API-ключа)
