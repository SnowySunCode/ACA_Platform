# ACA Platform — Railway deployment

## Почему Railway
Для ACA Platform нужен persistent storage: сервер хранит SQLite и сессии.
На Railway подключите Volume к `/data`. Сервер автоматически увидит
`RAILWAY_VOLUME_MOUNT_PATH` и положит туда:

- `/data/aca_server.sqlite3`
- `/data/aca_server_backups/`

## Самый короткий путь

1. Создайте отдельный GitHub-репозиторий для содержимого папки `server/`
   (не кладите туда ваш `aca_system_db.json`).
2. Railway → New Project → Deploy from GitHub repo.
3. Выберите репозиторий.
4. Railway сам увидит Dockerfile.
5. Откройте сервис → Add Volume → mount path: `/data`.
6. Settings → Healthcheck Path: `/health`.
7. Settings → Serverless: ON.
8. Networking → Generate Domain.
9. Откройте `https://ВАШ-ДОМЕН/health`.
   Должен вернуться JSON с `"ok": true`.

## Клиент
В `aca_server_config.json`:

```json
{
  "server_url": "https://ВАШ-ДОМЕН.up.railway.app"
}
```

Клиент 5.15.1 содержит retry для cold start Railway (502/503/504).

## Важно
Не храните существующий `aca_system_db.json` в публичном GitHub.
Для переноса текущей базы сделаем отдельный безопасный импорт после того,
как Railway выдаст постоянный домен.


## Самый быстрый вариант с Mac

Откройте Terminal в папке `server` и запустите:

```bash
chmod +x deploy_railway_mac.command
./deploy_railway_mac.command
```

Скрипт сам:
- установит Railway CLI через Homebrew, если его нет;
- откроет вход в Railway;
- создаст проект;
- задеплоит сервер;
- добавит persistent volume `/data`;
- предложит загрузить существующий `../aca_system_db.json`;
- передеплоит сервер уже с persistent storage;
- создаст HTTPS-домен Railway.

После этого вручную включите только один переключатель:
`Service → Settings → Deploy → Serverless → ON`.
