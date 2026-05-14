# Jenkins CI

Локальный Jenkins для прогона CI-пайплайнов проекта (`unit`, `integration`, `e2e`). Поднимается через Docker Compose, конфигурируется декларативно через JCasC (Jenkins Configuration as Code).

## Что внутри

```
ci/
├── Jenkinsfile.unit             Pipeline: unit-тесты (под Docker-агентом python:3.11)
├── Jenkinsfile.integration      Pipeline: integration-тесты (docker compose)
├── Jenkinsfile.e2e              Pipeline: end-to-end сценарий
└── jenkins/
    ├── Dockerfile               jenkins/jenkins:lts + docker CLI + docker-compose plugin
    ├── plugins.txt              Список Jenkins-плагинов (workflow, docker, JCasC, job-dsl, …)
    ├── casc.yaml                JCasC: пользователи, security, jobs (3 pipelineJob)
    ├── docker-compose.yml       Сервис drones-jenkins, монтирует /var/run/docker.sock
    ├── .env.example             Шаблон конфига (логин/пароль/порт/git-репозиторий/ветка)
    └── build.sh                 Хелпер для триггера job через REST API + CSRF crumb
```

## Установка и запуск

### 1. Поднять Jenkins

```bash
make jenkins-up
```

Что происходит:
- Создаётся `ci/jenkins/.env` из `.env.example` (если его ещё нет — отредактируй пароль/ветку).
- Собирается образ `drones-jenkins:local`.
- Стартует контейнер `drones-jenkins`, доступен на http://localhost:8080.
- JCasC автоматически создаёт **3 jobs**: `drone-unit`, `drone-integration`, `drone-e2e`.

Логин по умолчанию: **admin / changeme** (из `.env`).

### 2. Проверить статус

```bash
make jenkins-ps       # docker compose ps
make jenkins-logs     # docker compose logs -f
```

### 3. Остановить / перезапустить

```bash
make jenkins-down
make jenkins-restart
```

Volume `jenkins_home` сохраняется между перезапусками. Чтобы полностью сбросить состояние:

```bash
make jenkins-down
docker volume rm jenkins_jenkins_home
```

## Прогон пайплайнов

### Из CLI (через REST API)

```bash
make jenkins-build-unit              # Запустить unit
make jenkins-build-unit WAIT=1       # Запустить и стримить лог до конца

make jenkins-build-integration WAIT=1
make jenkins-build-e2e WAIT=1
```

`WAIT=1` — ждёт постановки в очередь, старта билда, стримит progressiveText, печатает финальный результат (`SUCCESS` / `FAILURE`). Возвращает exit code 0 только при `SUCCESS`.

### Через UI

http://localhost:8080 → залогиниться → выбрать job → **Build Now**.

## Конфиг

Все параметры в `ci/jenkins/.env`:

| Переменная | Описание | Дефолт |
|---|---|---|
| `JENKINS_ADMIN_USER` | Логин админа | `admin` |
| `JENKINS_ADMIN_PASSWORD` | Пароль | `changeme` |
| `JENKINS_HTTP_PORT` | Порт UI | `8080` |
| `JENKINS_AGENT_PORT` | Порт JNLP-агента | `50000` |
| `GIT_REPO_URL` | Репо для пайплайнов | gitflic |
| `GIT_BRANCH` | Ветка | `feature/Jenkins` |


## Траблшутинг

**`make jenkins-up` падает на сборке Docker** — проверь, что Docker daemon запущен (`docker version`).

**Pipeline падает на checkout с `dubious ownership`** — это лечится строкой `git config --global --add safe.directory "${WORKSPACE}"` в Checkout-стейдже (уже есть в Jenkinsfile).

**Unit-тесты падают с `AttributeError: 'BaseRedisStoreComponent' has no attribute '_init_backend'`** — это рассинхрон тестов submodule `gcs` с SDK монорепо: тесты ожидают, что Redis-инициализация вынесена в отдельный метод `_init_backend()`, но в SDK она прямо в `__init__`. Не связано с Jenkins.

**`403` при триггере билда из CLI** — `build.sh` уже фетчит CSRF crumb и шлёт его в одной cookie-сессии. Если всё равно падает — проверь `JENKINS_ADMIN_PASSWORD` в `.env`.

**`Build did not start within timeout`** — Jenkins ещё не успел инициализировать executors. Подожди ~30 секунд после `jenkins-up` до первого триггера.
