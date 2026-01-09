# Server Deployment Guide: Auto-Agent-Harness

Руководство по развёртыванию Auto-Agent-Harness на сервере.

---

## Содержание

1. [Требования](#требования-к-серверу)
2. [Режимы аутентификации Claude](#режимы-аутентификации-claude)
3. [Режим 1: Native (OAuth подписка)](#режим-1-native-oauth-подписка)
4. [Режим 2: Docker + API Key](#режим-2-docker--api-key)
5. [Режим 3: Docker + OAuth (Гибрид)](#режим-3-docker--oauth-гибрид)
6. [Импорт существующего проекта](#импорт-существующего-проекта)
7. [Конфигурация](#конфигурация)
8. [Troubleshooting](#troubleshooting)

---

## Требования к серверу

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| RAM | 2 GB | 4 GB |
| CPU | 2 cores | 4 cores |
| Disk | 20 GB | 50 GB |
| Python | 3.11+ | 3.12 |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |

---

## Режимы аутентификации Claude

Auto-Agent-Harness поддерживает **три режима** аутентификации с Claude API:

| Режим | Где работает | Auth Method | Цена | Рекомендуется для |
|-------|--------------|-------------|------|-------------------|
| **Native** | Локальная машина | OAuth (subscription) | Подписка Claude Pro/Max | Разработка |
| **Docker + API Key** | Сервер/облако | API Key | Pay-per-token | Production (простое) |
| **Docker + OAuth** | Сервер/облако | OAuth (mounted) | Подписка | Production (экономия) |

### Сравнение режимов

```
┌─────────────────────────────────────────────────────────────────┐
│                     NATIVE MODE                                  │
│  ✅ Использует подписку Claude Pro/Max                          │
│  ✅ Простая настройка (claude login)                            │
│  ❌ Требует локальную машину с браузером                        │
├─────────────────────────────────────────────────────────────────┤
│                  DOCKER + API KEY                                │
│  ✅ Работает на любом сервере                                   │
│  ✅ Простой deployment                                          │
│  ❌ Платите за каждый токен                                     │
├─────────────────────────────────────────────────────────────────┤
│                  DOCKER + OAUTH                                  │
│  ✅ Работает на сервере                                         │
│  ✅ Использует подписку (экономия)                              │
│  ❌ Нужно периодически обновлять токены                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Режим 1: Native (OAuth подписка)

**Лучший для:** Локальная разработка, использование Claude Pro/Max подписки.

### Требования
- Локальная машина (Windows/macOS/Linux)
- Браузер для OAuth
- Claude CLI (`npm install -g @anthropic-ai/claude-code`)

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или: venv\Scripts\activate  # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Авторизоваться в Claude (откроется браузер)
claude login

# 5. Запустить
./start.sh  # Linux/macOS
# или: start.bat  # Windows
```

### Как это работает

```
┌─────────────────────────────────────────────────┐
│              Your Machine                        │
│  ┌─────────────┐     ┌──────────────────────┐  │
│  │ claude login│ ──► │ ~/.claude/           │  │
│  │  (browser)  │     │  .credentials.json   │  │
│  └─────────────┘     └──────────────────────┘  │
│         │                      │               │
│         ▼                      ▼               │
│  ┌─────────────────────────────────────────┐  │
│  │        auto-agent-harness               │  │
│  │  Python process (NOT Docker)            │  │
│  │  Uses Claude Pro/Max subscription       │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## Режим 2: Docker + API Key

**Лучший для:** Простой серверный deployment, облачные платформы.

### Установка (Быстрый старт)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Интерактивная настройка
./scripts/setup-docker-auth.sh --api-key
# Введите ваш ANTHROPIC_API_KEY

# 3. Запустить
docker-compose up -d --build
```

### Ручная установка

```bash
# 1. Клонировать
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Создать workspace
mkdir -p workspace

# 3. Создать .env
cat > .env << 'EOF'
# Claude API Authentication
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx

# Application Authentication
JWT_SECRET_KEY=REPLACE_WITH_RANDOM_32_CHAR_HEX
DEFAULT_ADMIN_PASSWORD=your-secure-password

# Paths
WORKSPACE_DIR=./workspace
EOF

# 4. Сгенерировать JWT secret
JWT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s/REPLACE_WITH_RANDOM_32_CHAR_HEX/$JWT/" .env

# 5. Запустить
docker-compose up -d --build

# 6. Проверить
curl http://localhost:8888/api/health
```

### Как это работает

```
┌─────────────────────────────────────────────────┐
│                   Server                         │
│  ┌─────────────────────────────────────────┐   │
│  │           Docker Container               │   │
│  │  ┌─────────────────────────────────┐    │   │
│  │  │  ANTHROPIC_API_KEY=sk-ant-xxx   │    │   │
│  │  │  auto-agent-harness             │    │   │
│  │  │  (pays per token)               │    │   │
│  │  └─────────────────────────────────┘    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Режим 3: Docker + OAuth (Гибрид)

**Лучший для:** Серверный deployment с использованием Claude Pro/Max подписки.

### Как это работает

1. **Один раз** на локальной машине: `claude login` + извлечение токенов
2. Токены копируются на сервер
3. Docker использует подписку через извлечённые токены

```
┌─────────────────────────────────────────────────┐
│              Local Machine (once)               │
│  ┌─────────────┐     ┌──────────────────────┐  │
│  │ claude login│ ──► │ ~/.claude/           │  │
│  │  (browser)  │     │  .credentials.json   │  │
│  └─────────────┘     └──────────────────────┘  │
│                              │                  │
│         ┌────────────────────┘                  │
│         ▼                                       │
│  ┌──────────────────┐                          │
│  │ extract-token.sh │  ──────────────────┐     │
│  └──────────────────┘                    │     │
└──────────────────────────────────────────│─────┘
                                           │
                   (copy to server)        │
                                           ▼
┌─────────────────────────────────────────────────┐
│                   Server                         │
│  ┌─────────────────────────────────────────┐   │
│  │           Docker Container               │   │
│  │  ┌─────────────────────────────────┐    │   │
│  │  │  Volume: credentials (mounted)  │    │   │
│  │  │  auto-agent-harness             │    │   │
│  │  │  (uses subscription)            │    │   │
│  │  └─────────────────────────────────┘    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Установка

#### На локальной машине:

```bash
# 1. Клонировать репозиторий
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Авторизоваться в Claude (если ещё не сделано)
claude login

# 3. Извлечь credentials
./scripts/setup-docker-auth.sh --oauth-extract

# 4. Скопировать на сервер
rsync -avz . user@server:/opt/autocoder/auto-agent-harness/
```

#### На сервере:

```bash
# 1. Перейти в директорию
cd /opt/autocoder/auto-agent-harness

# 2. Запустить
docker-compose up -d --build

# 3. Проверить
curl http://localhost:8888/api/health
```

### Обновление токенов

OAuth токены истекают периодически. Для обновления:

```bash
# На локальной машине
cd auto-agent-harness
./scripts/setup-docker-auth.sh --oauth-extract

# Скопировать обновлённые credentials на сервер
rsync -avz .docker-credentials/ user@server:/opt/autocoder/auto-agent-harness/.docker-credentials/

# На сервере: перезапустить контейнер
ssh user@server "cd /opt/autocoder/auto-agent-harness && docker-compose restart"
```

---

## Импорт существующего проекта

После установки (любой режим) можно импортировать существующие проекты.

### Через UI

1. Открыть UI: `http://server:8888`
2. Нажать **"Import Existing"**
3. Выбрать папку проекта
4. Выбрать режим:
   - **Analysis Mode** - агент анализирует код, создаёт features
   - **Skip Analysis** - просто регистрирует проект

### Через CLI (Docker)

```bash
# 1. Скопировать проект в workspace
cp -r /path/to/your-project /opt/autocoder/workspace/

# 2. Зарегистрировать через API
curl -X POST http://localhost:8888/api/projects/import \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "/workspace/your-project", "name": "your-project"}'
```

### Через CLI (Native)

```bash
# 1. Запустить start.py
python start.py

# 2. Выбрать "Import existing project"
# 3. Указать путь к проекту
```

---

## Конфигурация

### Переменные окружения

| Переменная | Описание | Default | Режим |
|------------|----------|---------|-------|
| `ANTHROPIC_API_KEY` | API ключ Anthropic | - | Docker + API Key |
| `AUTH_ENABLED` | Включить UI аутентификацию | `true` | Все |
| `JWT_SECRET_KEY` | Секрет для JWT токенов | **Обязательно** | Все |
| `DEFAULT_ADMIN_PASSWORD` | Пароль админа | `admin` | Все |
| `PORT` | Порт сервера | `8888` | Все |
| `WORKSPACE_DIR` | Директория проектов | `./workspace` | Docker |
| `ALLOWED_ROOT_DIRECTORY` | Root в контейнере | `/workspace` | Docker |
| `DATA_DIR` | Директория данных | `/app/data` | Docker |
| `REQUIRE_LOCALHOST` | Только localhost | `false` | Docker |

### Структура директорий

```
/opt/autocoder/
├── auto-agent-harness/     # Репозиторий приложения
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── .env                # Конфигурация
│   ├── .docker-credentials/# OAuth credentials (если режим 3)
│   └── scripts/
│       ├── extract-claude-credentials.sh
│       └── setup-docker-auth.sh
└── workspace/              # Директория проектов
    ├── project-1/
    └── project-2/
```

---

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name autocoder.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name autocoder.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/autocoder.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/autocoder.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # WebSocket timeout
    }
}
```

---

## Troubleshooting

### Проблема: "No Claude credentials found"

**Причина:** OAuth credentials не найдены.

**Решение:**
```bash
# Native mode
claude login

# Docker mode - проверить монтирование
docker-compose exec auto-agent-harness ls -la /home/autocoder/.claude/
```

### Проблема: "API key invalid"

**Причина:** Неверный или истёкший API ключ.

**Решение:**
```bash
# Проверить .env
grep ANTHROPIC_API_KEY .env

# Проверить что ключ передан в контейнер
docker-compose exec auto-agent-harness env | grep ANTHROPIC
```

### Проблема: "OAuth token expired"

**Причина:** OAuth токены истекли (обычно через 7 дней).

**Решение:**
```bash
# На локальной машине
claude login  # Обновить токены
./scripts/setup-docker-auth.sh --oauth-extract

# Скопировать на сервер и перезапустить
rsync -avz .docker-credentials/ user@server:/path/to/.docker-credentials/
ssh user@server "cd /path/to/harness && docker-compose restart"
```

### Проблема: Container не запускается

```bash
# Проверить логи
docker-compose logs auto-agent-harness

# Проверить .env
cat .env | grep -v "^#" | grep -v "^$"

# Частые проблемы:
# 1. JWT_SECRET_KEY не указан
# 2. Порт занят
# 3. Недостаточно памяти
```

### Проблема: Permission denied

```bash
# Проверить права на workspace
ls -la workspace/

# Исправить (Docker user имеет UID 1000)
sudo chown -R 1000:1000 workspace/
```

---

## Полезные команды

```bash
# Статус
docker-compose ps

# Логи
docker-compose logs -f

# Перезапуск
docker-compose restart

# Пересборка
docker-compose build --no-cache && docker-compose up -d

# Войти в контейнер
docker-compose exec auto-agent-harness bash

# Backup данных
docker run --rm -v autocoder-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/autocoder-backup.tar.gz /data

# Проверить credentials в контейнере
docker-compose exec auto-agent-harness cat /home/autocoder/.claude/.credentials.json | head -c 100
```

---

## Quick Reference

### Native Mode
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
pip install -r requirements.txt
claude login
./start.sh
```

### Docker + API Key
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
./scripts/setup-docker-auth.sh --api-key
docker-compose up -d --build
```

### Docker + OAuth
```bash
# Local machine
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
claude login
./scripts/setup-docker-auth.sh --oauth-extract
rsync -avz . user@server:/opt/autocoder/auto-agent-harness/

# Server
cd /opt/autocoder/auto-agent-harness
docker-compose up -d --build
```
