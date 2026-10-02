ACA Platform
ACA Platform — desktop-приложение для управления учебным процессом академии: учениками, преподавателями, оценками, прогрессом, доступами и аналитикой.
Текущая архитектура — клиент-серверная:
- Desktop client: Python + CustomTkinter
- Server: FastAPI
- Database: SQLite
- Hosting: Railway
- macOS distribution: .app / .dmg
- Live sync: через ACA Server
Текущие версии
Компонент	Версия
ACA Platform Client	5.15.5
ACA Platform Server	1.0.2
macOS build	Apple Silicon / arm64


Что умеет ACA Platform
- аккаунты администратора, преподавателей и учеников;
- роли и разграничение доступа;
- invite-коды для преподавателей;
- управление учениками;
- журнал на 120 уроков;
- оценки и веса оценок;
- GPA и аналитика;
- контроль прогресса;
- graduation / итоговый контроль;
- ссылки на Geometry Dash уровни и showcase;
- RU / EN интерфейс;
- восстановление доступа;
- server-side сессии;
- live sync между несколькими клиентами;
- серверные резервные копии.
Для пользователей
macOS
Для обычного использования Python, Terminal и дополнительные библиотеки не нужны.
1. Откройте файл ACA-Platform-5.15.5-macOS-arm64.dmg.
2. Перетащите ACA Platform в папку Applications.
3. Запустите Applications → ACA Platform.
Приложение автоматически подключается к ACA Server.
Текущий macOS-билд собран для Apple Silicon: M1 / M2 / M3 / M4 / M5, arm64.
Gatekeeper
Текущий DMG может быть не подписан сертификатом Developer ID Application и не notarized Apple.
Если macOS блокирует первый запуск:
1. Откройте System Settings → Privacy & Security.
2. Найдите сообщение о заблокированном ACA Platform.
3. Нажмите Open Anyway.
После оформления Apple Developer Program рекомендуется выпускать подписанные и notarized сборки.
Сервер
Production URL:
https://capable-reverence-production-c65c.up.railway.app
Healthcheck:
https://capable-reverence-production-c65c.up.railway.app/health
Сервер использует:
- FastAPI;
- SQLite;
- persistent Railway Volume;
- server-side authentication;
- sliding sessions;
- revision-based state sync;
- API для login / registration / state / backup / admin operations.
Persistent storage
Рабочая SQLite база на Railway:
/data/aca_server.sqlite3
Резервные копии:
/data/aca_server_backups/
Старый aca_system_db.json используется только для первоначального импорта или ручной миграции.
Клиент и подключение к серверу
Начиная с 5.15.5, production Railway URL встроен непосредственно в клиент.
Приоритет выбора сервера:
1. ACA_LOCAL_MODE=1 — явный локальный режим для разработки;
2. переменная ACA_SERVER_URL;
3. aca_server_config.json;
4. встроенный production Railway URL.
Production-сборка больше не переключается молча на локальную JSON-базу, если config-файл отсутствует.
Локальный режим
Локальная база поддерживается только для разработки:
ACA_LOCAL_MODE=1 python3 aca_platform.py
Без ACA_LOCAL_MODE=1 клиент должен использовать ACA Server.
Сессии
Desktop-клиент сохраняет session token в пользовательской директории.
macOS:
~/Library/Application Support/ACA Platform/aca_session.json
Этот файл не содержит пароль пользователя.
Обычное закрытие приложения не завершает серверную сессию.
Кнопка Logout завершает текущую сессию и удаляет локальный token.
SSL
Клиент использует HTTPS с включённой проверкой сертификата.
Начиная с версии 5.15.4, CA bundle берётся через certifi, поэтому production .app не должен зависеть от сертификатов конкретной локальной установки Python.
SSL verification не отключается.
Разработка
Требования
Рекомендуемый Python:
Python 3.13+
Основные зависимости:
customtkinter
pillow
certifi
pyinstaller
Установка:
/usr/local/bin/python3 -m pip install --upgrade   customtkinter   pillow   certifi   pyinstaller
Запуск клиента из исходников
cd "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2"

/usr/local/bin/python3 aca_platform.py
Проверка production URL
cd "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2"

/usr/local/bin/python3 - <<'PY'
import aca_platform

print("VERSION:", aca_platform.APP_VERSION)
print("SERVER:", aca_platform.load_server_url())
PY
Ожидаемый результат:
VERSION: 5.15.5
SERVER: https://capable-reverence-production-c65c.up.railway.app
Сборка macOS .app
Перед сборкой должны существовать:
aca_platform.py
aca_platform_icon.png
aca_platform_icon.icns
Очистка:
cd "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2"

rm -rf build dist "ACA Platform.spec"
Сборка:
/usr/local/bin/python3 -m PyInstaller   --noconfirm   --clean   --windowed   --name "ACA Platform"   --osx-bundle-identifier "com.apexcreatoracademy.acaplatform"   --icon "aca_platform_icon.icns"   --collect-all customtkinter   --collect-data certifi   --add-data "aca_platform_icon.png:."   aca_platform.py
Результат:
dist/ACA Platform.app
Запуск:
open "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2/dist/ACA Platform.app"
Сборка DMG
Установить create-dmg:
brew install create-dmg
Удалить старый DMG:
cd "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2"

rm -f "ACA-Platform-5.15.5-macOS-arm64.dmg"
Собрать:
create-dmg   --volname "ACA Platform"   --window-pos 200 120   --window-size 660 400   --icon-size 128   --icon "ACA Platform.app" 170 190   --hide-extension "ACA Platform.app"   --app-drop-link 490 190   "ACA-Platform-5.15.5-macOS-arm64.dmg"   "dist/ACA Platform.app"
Результат:
ACA-Platform-5.15.5-macOS-arm64.dmg
Подпись и notarization macOS
Для полноценного публичного релиза требуется участие в Apple Developer Program и сертификат:
Developer ID Application
Сертификат Apple Development для публичного Developer ID релиза не подходит.
После получения Developer ID рекомендуется:
1. подписать .app;
2. включить Hardened Runtime;
3. подписать .dmg;
4. отправить DMG через xcrun notarytool;
5. выполнить stapler staple;
6. проверить через spctl.
Без Developer ID приложение всё равно можно распространять, но macOS может потребовать ручное подтверждение запуска через Gatekeeper.
Railway deployment
Server entry point:
server/aca_server_railway.py
Деплой:
cd "/Users/marina/Downloads/ACA_Platform_Railway_1.0.2/server"

railway up . --path-as-root
Healthcheck:
curl "https://capable-reverence-production-c65c.up.railway.app/health"
Проверка persistent storage:
curl "https://capable-reverence-production-c65c.up.railway.app/"
Production server должен возвращать:
"storage": "persistent-volume"
Ограничения
SQLite
Текущая серверная архитектура рассчитана на один экземпляр ACA Server.
Не следует включать несколько Railway replicas, пока backend использует SQLite и process-local write lock.
Для горизонтального масштабирования потребуется переход на PostgreSQL или другой shared database backend.
Serverless
Railway Serverless поддерживается.
Desktop-клиент содержит bounded retry для временных ошибок:
502
503
504
Структура проекта
ACA_Platform_Railway_1.0.2/
├── aca_platform.py
├── aca_platform_icon.png
├── aca_platform_icon.icns
├── client/
│   ├── aca_platform_server_client_5_15_5.py
│   └── aca_server_config.example.json
├── server/
│   ├── aca_server_railway.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── deploy_railway_mac.command
├── dist/
│   └── ACA Platform.app
└── ACA-Platform-5.15.5-macOS-arm64.dmg
Безопасность
- пароли не хранятся в plaintext;
- используется PBKDF2-HMAC-SHA256;
- session tokens генерируются криптографически стойко;
- server хранит только hash session token;
- HTTPS certificate verification включена;
- роли и разрешения проверяются на сервере;
- локальная JSON-база не используется production-клиентом без явного ACA_LOCAL_MODE=1.
Статус проекта
- [x] Railway server
- [x] persistent SQLite
- [x] server authentication
- [x] live sync
- [x] stable session persistence
- [x] HTTPS + certifi
- [x] built-in production server URL
- [x] disabled silent local DB fallback
- [x] macOS .app
- [x] .icns application icon
- [x] macOS .dmg
- [ ] Developer ID signing
- [ ] Apple notarization
- [ ] Windows .exe
- [ ] Windows installer
License
Copyright © ACA Platform.
All rights reserved.