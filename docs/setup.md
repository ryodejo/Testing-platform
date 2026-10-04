# Структура, настройки и данные

## Устройство приложения

- `DjangoProject1/` — настройки и корневые маршруты.
- `tasks/` — модели, формы, сервисы расчёта, права доступа и Admin.
- `frontend/templates/` — общий шаблон и страницы; `frontend/static/` — CSS/JavaScript.
- `tasks/migrations/` — история схемы; `tasks/management/commands/` — `seed_demo` и `backup_db`.
- `scripts/dev.ps1` — локальные переменные; `docs/` — проверочные материалы.

Сохранена иерархия `Test → Topic → Question → Answer`. `Test.topic` задаёт тему каталога, `Topic` — раздел внутри теста. UUID черновика привязан к пользователю. Результат и снимки ответов сохраняются транзакционно; повторная отправка возвращает существующий результат. Правильные ответы доступны после завершения. SQLite IMMEDIATE сериализует записи.

## Настройки

`SECRET_KEY` обязателен. `DEBUG` по умолчанию выключен, `ALLOWED_HOSTS` задаётся через запятую. Локальный `dev.ps1` сохраняет уже установленные переменные. При `DEBUG=0` защищённые cookies требуют HTTPS.

`DATABASE_PATH` выбирает SQLite-файл, по умолчанию — `db.sqlite3` в корне. `TEST_DB_PATH` — отдельная уничтожаемая тестовая база. Не назначайте ей рабочую базу. `.env.example` содержит примеры, не загружаемые автоматически.

Для SMTP перед запуском задайте:

```powershell
$env:EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
$env:EMAIL_HOST = 'smtp.your-provider.example'
$env:EMAIL_PORT = '587'
$env:EMAIL_HOST_USER = 'your-account@example.com'
$env:DEFAULT_FROM_EMAIL = 'your-account@example.com'
$env:EMAIL_USE_TLS = '1'
$env:EMAIL_USE_SSL = '0'
$credential = Get-Credential -UserName $env:EMAIL_HOST_USER -Message 'Пароль приложения SMTP'
$env:EMAIL_HOST_PASSWORD = $credential.GetNetworkCredential().Password
```

Замените примеры настройками провайдера. Для SSL на 465: `EMAIL_USE_TLS=0`, `EMAIL_USE_SSL=1`. Пароль не записывайте в Git. Без настройки используется console backend: письмо видно в терминале сервера. Для неизвестного email показывается нейтральное подтверждение.

## Данные и администрирование

Перед изменением схемы существующей базы:

```powershell
. .\scripts\dev.ps1
.\.venv\Scripts\python.exe manage.py backup_db
.\.venv\Scripts\python.exe manage.py migrate
```

Копии сохраняются в игнорируемом `backups/`. Исходные миграции сохранены; новые добавляют снимки попыток и защиту уникальности новых email. Старые аккаунты без email сохраняют вход, совпадающие адреса требуют согласованного исправления администратором. Недостающие исторические ответы не выдумываются.

Создайте администратора через `createsuperuser`. Новый тест сохраняется неопубликованным; затем добавляются разделы, вопросы и варианты. Для публикации нужен хотя бы один вопрос; каждому вопросу — минимум два варианта и ровно один правильный. Перед изменением структуры снимите публикацию. Результаты в Admin доступны только для просмотра.

Публичное развёртывание требует настройки HTTPS, статических файлов, ограничения частоты запросов, SMTP и оценки нагрузки. Встроенный сервер предназначен для разработки.
