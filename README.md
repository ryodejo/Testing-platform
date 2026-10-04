# Testing Platform

Учебная платформа для прохождения тестов и разбора ответов. Django-приложение для портфолио IT-стажёра с SQLite и адаптивным русскоязычным интерфейсом.

![Главная страница](docs/screenshots/home-1440.png)

## Возможности

- Регистрация с обязательным уникальным email, вход, выход и восстановление пароля средствами Django.
- Каталог опубликованных тестов, поиск, фильтр по теме и страница перед началом.
- Выбор ответов, прогресс, предупреждение о пропусках и серверный расчёт баллов.
- История собственных попыток и разбор с объяснениями; снимки сохраняют результаты при изменении вопросов.
- Защита от повторной отправки, проверка владельца результатов и CSRF.
- Django Admin с inline-формами и проверкой публикации; демоданные и резервное копирование.

## Технологии и требования

Python 3.11+, Django 5.2 LTS, SQLite, HTML/CSS/JavaScript. Версии закреплены в [requirements.txt](requirements.txt). Внешние шрифты и CDN не нужны.

Нужны Git, Windows PowerShell и Python с pip и Launcher (`py`). Если Launcher отсутствует, используйте `python -m venv .venv`, предварительно проверив `python --version`.

## Установка и запуск

```powershell
git clone https://github.com/ryodejo/Testing-platform.git
Set-Location .\Testing-platform
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\dev.ps1
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`dev.ps1` создаёт случайный `SECRET_KEY` в игнорируемом `.local/secret-key.txt`, задаёт `DEBUG=1` и локальные `ALLOWED_HOSTS`, если они ещё не установлены. Секрет сохраняется между запусками. Политика выполнения меняется только в текущем окне; активация venv не требуется. В новом окне снова выполните `. .\scripts\dev.ps1` перед командами Django.

Откройте [главную](http://127.0.0.1:8000/), [каталог](http://127.0.0.1:8000/tests/) и [регистрацию](http://127.0.0.1:8000/register/). После входа доступна [история](http://127.0.0.1:8000/history/).

Демокоманда создаёт четыре теста по пять вопросов: Python, SQL, HTTP и тестирование ПО. Повтор не создаёт дубликаты и не перезаписывает ручные правки.

Администратор создаётся вручную, без заранее заданного пароля:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Затем откройте [Django Admin](http://127.0.0.1:8000/admin/). Перед миграциями существующей базы выполните `manage.py backup_db`; на чистом клоне база создаётся командой `migrate`.

## Восстановление пароля и настройки

На [странице восстановления](http://127.0.0.1:8000/password-reset/) введите email аккаунта. Письмо с одноразовой ссылкой по умолчанию выводится **в терминал runserver**, а не отправляется в почтовый ящик. Ссылка действует один час. Не публикуйте журналы со ссылками сброса.

Настройки читаются из переменных окружения; [.env.example](.env.example) — пример, файл `.env` автоматически не загружается. SMTP и работа с данными описаны в [руководстве](docs/setup.md).

## Проверки

После установки зависимостей, из корня проекта:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\dev.ps1
$env:TEST_DB_PATH = Join-Path (Get-Location).Path '.local\test-review.sqlite3'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --noinput
```

`TEST_DB_PATH` — отдельная одноразовая база: Django создаёт и удаляет её. Файловая SQLite нужна для проверки одновременных запросов. Не указывайте рабочую `db.sqlite3`.

## Ограничения и документация

Локальный учебный проект: SQLite и `runserver` не рассчитаны на production-нагрузку. Нет подтверждения email, прокторинга и принудительного таймера. Черновик действует 12 часов, тест ограничен 100 вопросами. У старых результатов без снимков нельзя достоверно восстановить ответы и процент. Реальная SMTP-доставка требует настройки.

- [Структура, настройки и данные](docs/setup.md).
- [Тест-кейсы](docs/test-cases.md) и [ручной чек-лист](docs/manual-testing.md).
- [Отчёт реализации](docs/implementation-report.md).
- [Проверка документации и локального запуска](docs/reproducibility.md).
