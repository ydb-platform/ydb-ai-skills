# Навыки и агентские инструменты у вендоров баз данных

## Резюме

Рынок уже вышел из стадии, где достаточно было опубликовать `AGENTS.md` с несколькими советами. У наиболее активных вендоров складывается трехслойная модель:

1. **Skills** передают агенту устойчивое предметное знание: как проектировать схему, выбирать индексы, диагностировать запросы, работать с конкретным SDK и не нарушать ограничения продукта.
2. **MCP, CLI и API** дают агенту «руки»: прочитать метаданные, выполнить диагностический запрос, создать ресурс или изменить конфигурацию.
3. **Плагины и собственные установщики** объединяют знания и инструменты, настраивают подключение, обновляют контент и добавляют runtime-механику — маршрутизацию, hooks и проверку окружения.

Самые зрелые реализации принадлежат не обязательно самым крупным СУБД. ClickHouse, Redis, MongoDB, Databricks и Qdrant быстро сформировали отдельные репозитории навыков и понятные способы установки. Microsoft строит сильную горизонтальную систему вокруг PostgreSQL, SQL Server и Data API Builder. Snowflake делает ставку на управляемую серверную доставку skills и MCP. CockroachDB выбрал консервативный путь: глубокая эксплуатационная база знаний без автоматического выполнения команд. У MySQL, напротив, официальный action-layer пока заметнее, чем переносимый каталог знаний; часть разрыва закрывают MariaDB и Percona.

Текущий проект YDB уже силён в двух местах: переносимость между агентами и дисциплина безопасных инструкций. Его слабое место — не формат, а полнота продукта и отсутствие стандартизированного безопасного action-layer. Наиболее перспективный вектор — не превращать репозиторий в энциклопедию и не начинать с автономных изменений в продакшене, а построить **проверяемый YDB copilot stack**:

- компактный маршрутизатор и 6–10 сильных предметных навыков;
- измерение реального skill lift в запусках с навыком и без него;
- read-only MCP/CLI-слой с жёсткими лимитами и аудитом;
- плагины, объединяющие skills, документацию и инструменты;
- затем — ограниченные изменения с подтверждением пользователя и правами, принудительно заданными на стороне YDB.

Если коротко, возможность для YDB — стать не «ещё одним набором подсказок», а эталоном для распределённых SQL-систем: глубокое знание YQL и архитектуры YDB, безопасная диагностика живой базы, воспроизводимые рекомендации и доказанная совместимость с разными агентами.

## 1. Рамка исследования

Срез отражает состояние публичных решений на 10 сентября 2026 года. В выборку включены популярные реляционные, аналитические, document-, search- и vector-database продукты, а также наиболее близкие к YDB распределённые SQL-платформы. Это не рейтинг популярности СУБД: цель — покрыть основные продуктовые и технологические подходы.

Под «скиллом» здесь понимается пакет инструкций в открытом формате Agent Skills: каталог с обязательным `SKILL.md` и, при необходимости, `references/`, `scripts/` и `assets/`. Агент сначала видит короткие метаданные, затем загружает основной текст и только по необходимости — дополнительные материалы. Формат специально рассчитан на progressive disclosure и переносимость между инструментами.[^1]

Важно не смешивать четыре разных сущности:

| Слой | Что он даёт | Типичный риск |
|---|---|---|
| Instructions / rules | Постоянные правила для репозитория или сессии | Раздувание контекста, отсутствие точной активации |
| Agent Skill | Знание и workflow, загружаемые по задаче | Устаревание, неверная маршрутизация, слабая проверка эффекта |
| MCP / CLI / API | Доступ к данным и действиям | Утечки, дорогие запросы, несанкционированные изменения |
| Plugin / extension | Доставка набора skills, MCP-конфигурации, hooks и команд | Vendor lock-in конкретного агента, усложнение релиза |

MCP — протокол подключения AI-приложений к внешним системам и инструментам; сам по себе он не учит модель правильно пользоваться базой.[^2] Databricks формулирует это особенно ясно: skills передают знания, а MCP предоставляет инструменты.[^3] Поэтому сравнивать только число MCP-методов или только число `SKILL.md` недостаточно.

Статусы в таблицах трактуются строго:

- **официальный** — репозиторий или документация находятся у вендора и заявлены как поддерживаемый продуктовый путь;
- **официальный preview/lab** — работа самого вендора, но не production-grade или не общий GA-путь;
- **contrib/community** — полезный проект экосистемы, который нельзя выдавать за основную продуктовую поставку;
- **не обнаружен** — в исследованном публичном контуре не найден отдельный переносимый pack; это не утверждение, что его нигде не существует.

## 2. Карта рынка

| Экосистема | Knowledge-layer | Action-layer | Как поставляется | Характерный подход | Зрелость для нашей задачи |
|---|---|---|---|---|---|
| ClickHouse | Официальный `agent-skills` | Официальный ClickHouse MCP | `npx skills`, `clickhousectl`, Cursor plugin | Правила по темам, SQL-валидация, строгий read-only default | Очень высокая |
| Redis | Официальные skills | Docs MCP и Redis DB MCP | `npx`, Claude/Cursor/Codex plugins | Отдельные knowledge- и data-MCP, обязательные evals | Очень высокая |
| MongoDB | Официальные skills | Hosted Atlas MCP и local MCP | `npx`, setup utility, плагины | Один pack для cloud и self-managed, OAuth/RBAC, лимиты | Очень высокая |
| PostgreSQL | Несколько vendor packs | Разные MCP по облакам и продуктам | Plugins, `npx`, MCP | Нет единого центра; сильны Microsoft и Neon | Высокая, но фрагментированная |
| Oracle Database | Большой официальный router/reference tree | SQLcl MCP | `npx`, Claude plugin, SQLcl | Широкая база знаний + полноценный SQL/PLSQL tool | Высокая |
| MySQL | Отдельный общий pack не обнаружен | Oracle MCP PoC; native MCP в roadmap | Source/PoC | Официальный фокус пока на action-layer | Низкая–средняя |
| MariaDB | Официальные короткие skills | MariaDB Shell MCP | `npx`, agent plugins | Практичные wrong/right rules; self-contained plugins | Высокая |
| Percona | Lab skills | Docs MCP / существующие DB-инструменты | `npx`, manual | Закрывает MySQL/Percona operational knowledge | Средняя |
| SQL Server / Azure SQL | Skills для Azure SQL container; custom skills в SSMS | Production-oriented SQL MCP через Data API Builder | Plugins, SSMS, MCP | Typed CRUD вместо свободного NL2SQL, RBAC и observability | Высокая |
| Snowflake | Native Cortex Agent skills; CoCo catalog | Managed MCP | Stage/Git, SQL/REST, CoCo install | Skills остаются в Git/stage; server-side governance | Очень высокая |
| Databricks | Большой официальный каталог | Managed MCP | `databricks aitools`, plugins | Генерируемые манифесты, runtime hooks, Unity Catalog | Очень высокая |
| Google Cloud DB / BigQuery | Общий официальный Google catalog | Remote MCP и MCP Toolbox | Catalog/index, extensions | Cross-product skills, SELECT-only инструменты для BigQuery | Высокая |
| CockroachDB | Официальные operational skills | Автовыполнение намеренно не входит | `npx`, manual, Cursor plugin | Глубокая диагностика, запрос выполняет человек | Высокая knowledge, низкая action |
| TiDB | Официальный AgenticStore catalog | Продуктовые CLI/API, без столь цельного общего MCP-пути | Репозиторий skills/rules | Skills вокруг драйверов, фреймворков и TiDB Cloud | Средняя |
| Elastic | Официальный широкий catalog | Elastic MCP/API ecosystem | `npx`, native plugins, installer | Выборочная установка, сильный security disclaimer | Высокая |
| Qdrant | Официальная иерархия skills | Qdrant MCP | `npx`, plugin, live advisor | Динамический поиск нужных leaf-skills и A/B-оценка | Очень высокая |
| Pinecone | Официальные skills | Query via MCP | `npx`, plugin | Переход от статических rules к skills, source validation | Высокая |
| Weaviate | Официальные skills и cookbooks | Скрипты и DB/API access | `npx`, plugin, manual | Skills исполняют end-to-end RAG workflows | Средняя–высокая |
| Neo4j | `neo4j-contrib`, не основной официальный pack | Neo4j MCP/CLI | `npx`, extensions/plugins | Широкое graph/GraphRAG знание, но иной статус поддержки | Средняя–высокая |

Из таблицы видны три группы зрелости:

1. **Полный стек:** ClickHouse, Redis, MongoDB, Snowflake, Databricks, Google и частично Microsoft. У них знания, действия и поставка образуют одну систему.
2. **Сильное знание, осторожные действия:** CockroachDB, Neon/PostgreSQL, Oracle skills, Elastic, Qdrant. Здесь особое внимание уделяется качеству рекомендаций или контролю доступа.
3. **Фрагментированный переход:** MySQL/TiDB и часть community-экосистем. Есть полезные assets, но нет единой истории установки, governance и оценки качества.

## 3. Разбор по вендорам

### 3.1. ClickHouse: правила как инженерный продукт

ClickHouse публикует отдельный официальный репозиторий Agent Skills. Он охватывает базовые практики, проектирование схем, оптимизацию запросов, ingestion и работу с `chDB`; установка доступна через универсальный `npx skills add`, собственный `clickhousectl` и плагины.[^4]

Главная особенность — не количество текстов, а инженерия источника. Большой раздел best practices разбит на отдельные правила с единым шаблоном, severity/impact и примерами; итоговые артефакты генерируются из канонического дерева. В CI проверяются структура, ссылки и SQL на реальном бинарнике ClickHouse.[^5] Это уменьшает две типичные проблемы навыков: расхождение копий для разных агентов и синтаксически правдоподобные, но неработающие запросы.

Action-layer поставляется отдельным официальным MCP-сервером. Он стартует read-only; запись и destructive operations включаются раздельно. При этом документация прямо говорит, что программный safety gate — best effort, а реальной границей безопасности должны быть права пользователя базы.[^6]

Что полезно YDB:

- генерировать agent-specific пакеты из одного источника;
- проверять YQL/DDL настоящим парсером или тестовой YDB;
- хранить у каждого правила стабильный ID, степень риска и диагностируемый anti-pattern;
- разделить разрешения на read, write и destructive не только в prompt, но и в credential/RBAC.

### 3.2. Redis: раздельные каналы знаний и данных

У Redis есть официальный набор из предметных навыков для core-концепций, подключений, Search, semantic cache, clustering, security, observability и разработки Redis-модуля/решения. Он поставляется через `npx`, Claude и Cursor, а также в формате плагина для Codex/ChatGPT; agent-specific копии генерируются из общей директории, а не поддерживаются вручную.[^7]

Отдельно существуют два MCP-сценария:

- публичный read-only Redis Docs MCP без доступа к пользовательской базе;
- Redis MCP для чтения, записи, запросов и базового управления конкретным экземпляром.[^8]

Такое разделение архитектурно важно. Поиск актуальной документации почти безрисков, тогда как подключение к данным требует credentials, ограничений и иной модели доверия. Их не обязательно размещать в одном сервере.

Redis также задаёт высокий стандарт проверки контента: существенное изменение skill должно сопровождаться eval-сценариями; тесты лежат вне каталога навыка, чтобы модель не видела «ответы»; baseline хранит pass rate, токены, время и стоимость для модельной матрицы.[^9]

Для YDB отсюда следуют два прямых решения: отдельный Docs MCP и независимый Database MCP, а также обязательная регрессия качества для каждого существенного изменения правила.

### 3.3. MongoDB: единый путь от laptop до managed cloud

MongoDB поддерживает официальный skills-репозиторий с навыками по connection setup, natural-language querying, query optimization, schema design, Search/AI и Atlas Stream Processing. Плагины могут подключать либо hosted Atlas MCP по HTTP/OAuth, либо локальный MCP для self-managed MongoDB; setup utility помогает выбрать режим и сформировать конфигурацию.[^10]

MCP Server существует в двух формах: управляемый Atlas и локальный self-hosted. В enterprise-сценарии контроль строится не только вокруг prompt: используются организационный opt-in, read-only enforcement, Atlas roles и сетевые ограничения.[^11] Документация отдельно рекомендует включать read-only при первичной настройке, если запись явно не нужна.[^12]

Отдельно заслуживают внимания ограничения объёма данных и памяти: MongoDB документирует caps, предотвращающие переполнение процесса и контекстного окна.[^13] Это не косметика — database MCP без row/byte/time limits легко превращает безобидную команду в отказ в обслуживании или утечку большого набора данных.

У репозитория есть отдельная testing-структура: evals по навыкам, schema validation и boundary tests, проверяющие, что агент выбирает нужный skill, а не соседний.[^14] Последний класс тестов особенно важен для YDB после появления `ydb-topics`, `ydb-coordination` и operational skills.

### 3.4. PostgreSQL: сильная, но фрагментированная экосистема

У сообщества PostgreSQL не обнаружен единый канонический skill pack уровня документации самого проекта. Вместо него появились несколько вендорских центров компетенций.

Microsoft публикует большой PostgreSQL pack: лёгкий router подключает десятки subskills по общему PostgreSQL, Azure Database for PostgreSQL и связанным сценариям. Плагин объединяет knowledge-layer с `postgres-mcp` и Azure CLI и требует подтверждения перед destructive changes.[^15] Это пример широкого дерева, где верхний skill не пытается вместить всю документацию.

Neon выбрал противоположный формат: один компактный vendor-neutral набор best practices по схемам, индексам, запросам и частым ошибкам. Проект подчёркивает экспертную человеческую редактуру.[^16] Предыдущий формат `ai-rules` был архивирован в пользу Agent Skills — наглядный сигнал перехода отрасли от всегда загружаемых инструкций к активации по задаче.[^17]

Вывод для YDB: нет необходимости выбирать между «одним большим файлом» и «сотней атомарных карточек». Рабочая композиция — небольшой router, самостоятельные surface-skills и дробные rules/references внутри них. Именно к этому уже близка локальная архитектура проекта.

### 3.5. Oracle Database: широкий router и мощный локальный инструмент

Oracle ведёт общий официальный каталог skills для своих технологий. Домен Database представлен одним верхнеуровневым router, который направляет агента к материалам по администрированию, application development, архитектуре, backup, containers, design, DevOps, migrations, monitoring, performance, PL/SQL, security, SQL Developer и SQLcl.[^18]

То есть «один skill» в списке не означает маленькое покрытие: за ним стоит большое дерево ссылок и многошаговых workflow. Это важное предостережение против сравнений по числу каталогов.

Для действий Oracle использует SQLcl MCP. Он работает с заранее сохранёнными подключениями и допускает SQL, PL/SQL и операции SQLcl.[^19] Вендор отдельно рекомендует least privilege, очищенные read-only replicas/datasets и аудит; MCP-вызовы маркируются в database sessions и логируются.[^20]

Oracle показывает подход для зрелых enterprise-систем: использовать существующий доверенный CLI и connection store как основу tool-layer, а не писать второй драйвер и вторую систему credentials.

### 3.6. MySQL, MariaDB и Percona: разный темп внутри одной экосистемы

Для MySQL на момент среза не обнаружен отдельный официальный переносимый набор product-wide Agent Skills. Oracle публикует MySQL MCP proof of concept для MySQL AI/HeatWave и прямо не позиционирует его как production-ready.[^21] В публичном roadmap native MCP сначала задуман read-only — для метрик, обнаружения схемы и запросов к данным.[^22]

MariaDB продвинулась дальше на knowledge-layer. Официальный pack состоит из коротких навыков по миграции с MySQL/Oracle, оптимизации запросов, replication/HA, system-versioned tables, vectors и настройке MariaDB MCP. Материалы используют пары wrong/right, version notes и ссылки на первичную документацию.[^23]

Отдельный репозиторий MariaDB plugins объединяет эти знания с MariaDB Shell MCP. Есть варианты для разработки, SQL-работы и contributor workflow; skill content vendored по точному commit SHA, а тесты включают не только структуру, но и исполнение SQL на живой базе.[^24]

Percona Lab закрывает часть operational gap для MySQL/Percona — миграции, encryption, audit, masking, replication/HA и query optimization.[^25] Но lab-статус и отсутствие единой продуктовой поставки отличают его от официальных полноценных стеков Redis или ClickHouse.

Для YDB эта группа полезна как пример того, что узкие практичные навыки и live SQL validation могут дать больше ценности, чем широкий, но непроверенный каталог.

### 3.7. SQL Server и Azure SQL: типизированные операции вместо свободного SQL

Microsoft поставляет набор skills для Azure SQL Database container, ориентированный на путь local development → Azure. В документации описано 17 навыков и три слоя знания: встроенные инструкции, version-pinned references и при необходимости живой Microsoft Learn MCP.[^26] Сценарий пока уже, чем весь SQL Server, но архитектура поставки зрелая.

В SSMS Agent Mode пользовательские и project-scoped `SKILL.md` стали нативной частью рабочего процесса, то есть IDE базы превращается в один из runtime-ов навыков.[^27]

Самая сильная идея Microsoft находится в action-layer. SQL MCP на основе Data API Builder экспонирует типизированные и детерминированные CRUD/tools, поддерживает RBAC, caching и OpenTelemetry и намеренно не сводит весь доступ к «сгенерируй произвольный SQL». Stored procedures и views могут становиться явными бизнес-инструментами.[^28]

Это один из лучших образцов для production-сценария YDB: предпочтительнее иметь `describe_table`, `explain_query`, `list_slow_queries` и ограниченный `execute_readonly_yql`, чем один безграничный `run_sql`.

### 3.8. Snowflake: skills как управляемый серверный объект

Snowflake пошёл дальше файловой установки. Cortex Agents может подключить skill из Git-репозитория или named stage; содержимое остаётся по источнику, агент обнаруживает метаданные и подгружает инструкции и файлы по необходимости. Добавление возможно через UI, SQL или REST, а scripts исполняются через отдельный code-execution tool.[^29]

CoCo при этом имеет десятки встроенных skills и отдельный community/curated каталог. Репозиторий или конкретный skill можно установить по Git URL; локальная система кэширует и регистрирует пакет.[^30]

Managed MCP у Snowflake — часть самой платформы. Он использует OAuth/RBAC, grants на уровне tools, поддерживает Cortex Analyst, Search, Agents, SQL и custom tools, а также задаёт ограничения числа инструментов, размера ответа и рекурсивных вызовов.[^31]

Это вероятный долгосрочный вектор рынка: skill становится версионируемым объектом платформы, а не файлом, который каждый разработчик вручную копирует в домашний каталог.

### 3.9. Databricks: packaging, runtime hooks и governance

Официальный `databricks-agent-skills` делит каталог на stable и experimental и покрывает discovery, приложения, bundles, jobs, Lakebase, model serving и другие поверхности. Канонический установщик — `databricks aitools install`; также генерируются плагины для нескольких агентов.[^32]

Важно, что plugin — больше, чем архив с Markdown. Он добавляет команды и hooks: раннее наполнение контекста, маршрутизацию prompt по regex и подсказки при ошибках аутентификации. Agent-specific manifests генерируются из одного источника и проверяются CI.[^32]

Managed MCP интегрирован с Unity Catalog и предоставляет управляемый доступ к SQL, Genie, Vector Search и функциям.[^33] При этом отдельный Databricks SQL MCP допускает запись по умолчанию, если явно не выставить `disallow_writes=true`.[^34] Это полезный контрпример: managed не обязательно значит safe-by-default, поэтому политика YDB должна быть явной и проверяемой.

Genie добавляет ещё один слой — семантическую модель над данными вместо прямого NL2SQL.[^35] Для YDB подобный слой имеет смысл позже, после стабилизации read-only primitives и domain skills.

### 3.10. Google Cloud: единый каталог продуктов и расширения MCP Toolbox

Google публикует общий каталог Agent Skills, где database/data-навыки находятся рядом с другими cloud-продуктами: BigQuery, Bigtable, Cloud SQL, AlloyDB, Spanner и onboarding. Машиночитаемый `index.json` описывает entrypoints, что облегчает discovery и автоматическую установку.[^36]

BigQuery skill знает о нескольких вариантах action-layer. Remote MCP предоставляет discovery и выполнение SELECT-only запросов и маркирует запросы служебным label; альтернативой служит локальный MCP Toolbox.[^37]

MCP Toolbox распространяет готовые extensions для BigQuery, Cloud SQL for MySQL/PostgreSQL/SQL Server, AlloyDB, Spanner, Firestore и self-hosted databases, включая варианты с observability.[^38]

Сильная сторона подхода — общий distribution plane для большого портфеля и единые operational primitives. Слабая — database-specific глубина может уступать отдельному репозиторию одного продукта.

### 3.11. CockroachDB и TiDB: ближайшие ориентиры для distributed SQL

Cockroach Labs публикует официальный каталог из 29+ задач по нескольким эксплуатационным доменам: schema/index design, transaction contention, hot ranges, performance, backup/restore, migration и другим. Skills дают диагностические запросы, последовательность проверки и safety warnings, но намеренно не исполняют команды: пользователь запускает их сам.[^39]

Это сильный вариант для регулируемых сред и ранней стадии продукта: knowledge-layer приносит пользу без новой поверхности доступа. Цена — отсутствие замкнутого цикла «обнаружил → проверил на живой системе → уточнил диагноз».

TiDB ведёт `agent-rules`/AgenticStore с навыками вокруг TiDB Cloud, SQL и query tuning, Serverless Driver, Kysely, Prisma, Next.js, `mysql2`, PyTiDB и filesystem mount.[^40] В основном репозитории TiDB также есть repo-local maintainer skills с профилями валидации, но это другой класс: помощь разработке самой СУБД, а не пользователям базы.[^41]

Для YDB CockroachDB — содержательный ориентир по distributed SQL diagnostics, а TiDB — по интеграциям с драйверами и application frameworks. Потенциальное преимущество YDB — объединить обе стороны и добавить безопасный read-only runtime.

### 3.12. Elastic, Qdrant, Pinecone, Weaviate и Neo4j

Elastic ведёт официальный широкий каталог по Elasticsearch, Kibana, Observability, Security и Cloud. Он рекомендует устанавливать только нужные домены, чтобы не ухудшать маршрутизацию избыточным контекстом, и прямо предупреждает, что skills являются исполняемым prompt-контентом: нужны проверка источника, минимальные privileges и ограниченные tool/network permissions.[^42]

Qdrant строит иерархию hub/leaf skills и формулирует полезный принцип: skill — не пересказ документации, а ответ на «когда, почему и какой компромисс выбрать». Особый `qdrant-advisor` не содержит фиксированной предметной базы, а ищет актуальные leaf-skills на `skills.qdrant.tech`; для offline-сред остаётся полный bundle.[^43]

Ещё важнее система оценки Qdrant: еженедельный A/B skill-lift — одинаковые задачи выполняются с навыками и без них, несколькими моделями и повторными прогонами. Слепой judge проверяет обязательные критерии, вредные рекомендации, фактические доказательства, активацию router и достижение нужного leaf-skill.[^44]

Pinecone публикует skills для quickstart, MCP query, CLI, Assistant, full-text search и docs. Проект пришёл к ним из прежнего набора статических `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, что отражает общий переход к progressive disclosure.[^45]

Weaviate сочетает instructions с исполняемыми utility scripts и end-to-end RAG cookbooks.[^46] Это повышает практическую ценность, но требует контроля зависимостей, credentials и сетевого доступа.

Neo4j имеет богатый `neo4j-contrib` pack по Cypher, data modeling, GraphRAG, GDS, Aura, CLI и MCP. Он полезен как образец широты, но статус `contrib` нужно явно отличать от core-supported продукта.[^47]

## 4. Какие подходы фактически победили

### 4.1. Skills — это навигация и решения, а не копия документации

Лучшие каталоги не пытаются вложить manual в context window. Они содержат:

- признаки, по которым распознаётся задача;
- дерево решений и порядок диагностики;
- безопасные defaults и границы применимости;
- хорошие и плохие примеры;
- ссылки на версионированный первичный источник;
- команды или tools, которыми можно проверить гипотезу.

Это видно у Qdrant, ClickHouse, CockroachDB и Neon. Большой prose без decision points быстро устаревает и слабо влияет на поведение модели.

### 4.2. Progressive disclosure масштабируется через router → surface → rule

Есть два устойчивых варианта:

- **атомарный каталог:** много независимо активируемых skills, как у CockroachDB или Elastic;
- **иерархия:** компактный router, surface-skills и references/rules, как у Oracle, Microsoft PostgreSQL и текущего YDB.

Второй вариант лучше сохраняет единую safety-policy и уменьшает конфликт между близкими навыками. Первый проще устанавливать выборочно. Для YDB оптимален гибрид: discoverable surface-skills (`ydb-table`, `ydb-topics`) плюс атомарные внутренние rules с ID.

### 4.3. Git остаётся источником, но не конечным UX

Практически сформировалась лестница поставки:

1. ручное копирование — fallback;
2. `npx skills add vendor/repo` — переносимый минимум;
3. native marketplace/plugin — удобная установка и обновление;
4. vendor CLI — проверка auth, версии и окружения;
5. managed skills — организация публикует и назначает знания централизованно.

ClickHouse и Databricks уже используют собственные CLI. Snowflake хранит ссылку на Git/stage и загружает материалы на сервере. Это делает versioning, policy и rollout частью продукта.

### 4.4. Компилируемые копии лучше ручного дублирования

Один source tree и генерация Claude/Cursor/Codex/Copilot manifests — общая практика Redis, ClickHouse и Databricks. Ручные копии неизбежно расходятся. В релизе стоит проверять, что generated artifacts идентичны текущему source, ссылки разрешаются, frontmatter соответствует спецификации, а declared tools существуют.

### 4.5. Knowledge freshness решается несколькими слоями

Вендоры комбинируют:

- pinned references — воспроизводимость;
- live Docs MCP — актуальность;
- runtime introspection (`--help`, version, capabilities) — соответствие установленной системе;
- server-hosted skills — централизованное обновление;
- dynamic advisor/search — получение только релевантного фрагмента.

Ни один слой не решает всё. Live search может незаметно изменить ответ, а pinned text устаревает. Для YDB разумная политика: нормативные правила привязаны к версии; документация доступна live; фактические capabilities проверяются у кластера и CLI.

### 4.6. Безопасность должна быть принудительной ниже prompt-слоя

Практика рынка приводит к следующей модели:

| Контроль | Где должен жить | Почему |
|---|---|---|
| Read-only по умолчанию | MCP server и DB role | Prompt можно обойти или неверно интерпретировать |
| Отдельный destructive opt-in | Конфигурация сервера + отдельное право | `DROP` качественно отличается от обычной записи |
| Подтверждение намерения | Agent workflow | Пользователь должен видеть конкретную операцию |
| Row/byte/time limits | Server/tool implementation | Защищает базу и context window |
| Per-tool permissions | Gateway/RBAC | Не каждый агент должен иметь универсальный SQL |
| Audit tag и журнал | Сессия/запрос/сервер | Нужна трассировка человеческого и агентского действия |
| Sanitized replica | Deployment architecture | Снижает последствия ошибочного доступа |
| Secret isolation | Connection store / OS / platform | Credentials не должны попадать в skill и prompt |

ClickHouse, MongoDB, Oracle, Snowflake и Microsoft сходятся на defense in depth, хотя defaults у отдельных реализаций различаются. Текущий двухфазный gate YDB — хорошая UX-политика, но будущий MCP должен считать её дополнительным слоем, а не границей безопасности.

### 4.7. Проверка синтаксиса — только начало

Можно выделить пять уровней качества:

1. **Structure:** frontmatter, пути, ссылки, размер, manifests.
2. **Executable examples:** YQL/SQL компилируется и исполняется на реальной версии.
3. **Answer quality:** модель с полным текстом навыка отвечает правильно на набор задач.
4. **Activation and boundaries:** runtime действительно выбирает нужный skill и не активирует соседний.
5. **Causal lift:** результат с skill статистически и practically лучше результата без skill при сопоставимых условиях.

Большинство каталогов остаются на уровнях 1–2. Текущий YDB проект уже покрывает model compatibility и предметные evals, но его тестирование полным skill content как system prompt измеряет верхнюю границу, а не реальную активацию. Qdrant и Redis показывают следующий шаг: A/B baseline, повторы, стоимость, routing и anti-criteria.

## 5. Позиция текущего проекта YDB

Локальный репозиторий уже содержит важные элементы зрелой архитектуры:

- универсальную установку в Claude, Cursor, Windsurf, Copilot, Codex, Roo, Gemini, Amp, Kiro, Trae и generic target;
- `ydb-core` как компактный router и слой общих safety-инструкций;
- `ydb-table` с разделением authoring/audit и rules/references;
- стабильные rule IDs и negative-pattern каталог;
- discovery фактических CLI-команд через version/help вместо выдуманных флагов;
- двухфазный gate перед мутацией;
- Promptfoo-матрицу нескольких моделей и провайдеров.

Это подтверждается [README](../../README.md), [руководством по авторингу](../authoring.md), [описанием тестирования](../testing.md) и самим [`ydb-core`](../../skills/ydb-core/SKILL.md).

Оценка относительно рынка:

| Измерение | Позиция YDB сейчас | Лидеры/ориентиры | Разрыв |
|---|---|---|---|
| Переносимость | Сильная | Redis, Databricks, ClickHouse | Нужны native plugins и lifecycle/update UX |
| Архитектура контента | Сильная основа | Oracle, Microsoft PostgreSQL, Qdrant | Пока мало законченных surfaces |
| Глубина DB-экспертизы | Сильная в узком контуре | ClickHouse, CockroachDB | Нужны topics, coordination, ops, больше SDK |
| Безопасность инструкций | Очень сильная | ClickHouse, MongoDB | Нет server-enforced tool layer |
| Действия на живой базе | Ограничены CLI workflow | Snowflake, Databricks, MongoDB | Нет официального read-only MCP/gateway |
| Проверка примеров | Развивается | ClickHouse, MariaDB | Нужны real YDB compile/execute suites |
| Model/eval coverage | Выше среднего | Redis, Qdrant | Нет A/B without-skill и runtime activation |
| Актуальность знаний | Links + CLI discovery | Snowflake, Qdrant, Microsoft | Нет live Docs MCP/версионного resolver |
| Enterprise governance | Концептуально | Snowflake, Databricks, MongoDB | Нет org policy, per-tool grants и audit plane |

Главный вывод: проект не отстаёт по формату. Он находится раньше по продуктовой полноте. Поэтому смена основы не нужна; нужно довести существующую архитектуру до замкнутого и измеримого пользовательского сценария.

## 6. Рекомендуемая продуктовая позиция

### 6.1. Формулировка

**YDB AI Skills — безопасный и проверяемый экспертный слой для проектирования, разработки и диагностики YDB во всех основных AI-агентах.**

Три слова здесь принципиальны:

- **безопасный** — read-only defaults, явное подтверждение, DB-enforced permissions, limits и audit;
- **проверяемый** — советы привязаны к источнику и версии, запросы выполняются в тестовой YDB, эффект навыка измеряется A/B;
- **экспертный** — акцент на специфике распределённой YDB, а не на общих SQL-рецептах.

### 6.2. Где может появиться защитимый дифференциатор

Универсальный формат скопировать легко. Сложнее воспроизвести четыре взаимосвязанных актива:

1. **Глубокая модель YDB-specific решений:** partitioning, hotspots, transactions, retries, sessions, query/service limits, topic semantics, coordination, rolling operations.
2. **Одинаковая диагностика в разных языках:** rule ID связывает Java/Go/C++/Python/C# примеры, audit и telemetry.
3. **Безопасный evidence loop:** агент может получить schema, plan, stats и version, но не имеет неограниченного доступа.
4. **Измеримый multi-agent reliability:** публикуется не только число skills, а activation rate, skill lift, harmful-advice rate и совместимость.

Эта комбинация пока не является стандартом ни у одного из рассмотренных distributed SQL-вендоров.

### 6.3. Какой каталог нужен, а какой — нет

На первом зрелом рубеже достаточно следующего набора:

| Skill | Основной результат |
|---|---|
| `ydb-core` | Router, auth, safety, version/capability discovery |
| `ydb-table` | Схема, YQL, транзакции, SDK patterns, review/audit |
| `ydb-topics` | Producer/consumer semantics, ordering, retries, throughput |
| `ydb-coordination` | Locks, leader election, leases, failure semantics |
| `ydb-observability` | Метрики, планы, slow queries, hotspots, incident triage |
| `ydb-migrations` | Совместимые изменения схемы и перенос с PostgreSQL/MySQL |
| `ydb-security` | IAM, service accounts, TLS, secrets, least privilege, audit |
| `ydb-operations` | Capacity, backup/restore, rolling procedures; сначала read-only advice |

Внутри `ydb-table` стоит закрыть Python и C# на том же уровне, что Java/Go/C++, а не создавать отдельный верхний skill на каждый язык. Отдельные integration-skills оправданы только для платформ с самостоятельным workflow — например, SQLAlchemy, Spring, Kubernetes или Terraform.

Не стоит начинать с десятков мелких skills: они увеличат routing ambiguity быстрее, чем полезное покрытие. Новая единица должна появляться, когда у неё есть самостоятельные activation cues, источники, evals и владелец.

## 7. Целевая архитектура

```text
Agent / IDE / Chat
        │
        ├── YDB Skills
        │     ├── router + safety policy
        │     ├── surface skills
        │     └── versioned rules/references
        │
        ├── YDB Docs MCP (public, read-only, no customer data)
        │     └── docs search, version resolver, examples
        │
        └── YDB Database MCP / trusted CLI adapter
              ├── L1 metadata: version, databases, tables, schema
              ├── L2 diagnostics: explain, stats, bounded read query
              ├── L3 approved change: typed, previewed operations
              └── L4 admin/destructive: disabled by default
                         │
                         └── YDB IAM/RBAC, quotas, audit, timeouts
```

### 7.1. Почему два MCP, а не один

Docs MCP можно сделать публичным и неавторизованным; он не должен знать адрес пользовательского кластера. Database MCP работает локально или в управляемом доверенном контуре и имеет access policy. Разделение упрощает threat model, onboarding и эксплуатацию — тот же принцип виден у Redis.

### 7.2. Набор безопасных primitives

Первая версия Database MCP должна быть маленькой:

- `get_server_capabilities`
- `list_databases`
- `list_tables`
- `describe_table`
- `get_table_statistics`
- `explain_yql`
- `execute_readonly_yql`
- `get_query_diagnostics`

Для каждого tool нужны typed input, deadline, maximum rows/bytes, redaction policy, query tag, audit event и понятная ошибка. `execute_readonly_yql` должен проверять режим на сервере и работать credential-ом без write privileges. Разбор текста запроса на стороне клиента полезен как дополнительная проверка, но не достаточен.

Write-tools стоит добавлять позже и делать предметными: например, `propose_table_change`, `apply_approved_schema_change`, `create_topic`. Сначала tool возвращает plan/diff и оценку риска, затем пользователь одобряет точный вариант, после чего отдельный вызов использует short-lived approval token. Универсальный unrestricted `execute_yql` не должен быть default-инструментом.

### 7.3. Manifest и сборка

Кроме стандартного frontmatter, проекту нужен собственный машиночитаемый manifest, из которого генерируются пакеты:

- версия skill и минимальная версия YDB/CLI/SDK;
- surface, role и activation cues;
- источники и дата их проверки;
- требуемые tools и уровень риска;
- совместимые агенты;
- eval suites и владелец;
- статус stable/preview/experimental.

Один pipeline должен собирать universal bundle, native plugins, catalog index и checksums. Это повторяет зрелые стороны Redis/Databricks/ClickHouse, но оставляет `SKILL.md` переносимым источником.

## 8. Дорожная карта

### Этап 1. Доказать качество knowledge-layer — 0–3 месяца

Цель: из хорошего framework сделать полезный законченный pack.

- Завершить `ydb-table`, включая Python и C#.
- Выпустить `ydb-topics`, `ydb-coordination` и минимальный `ydb-observability`.
- Для каждого rule добавить owner, upstream source/version и executable example там, где это возможно.
- Запускать YQL и schema examples против поддерживаемых версий YDB.
- Добавить negative routing tests: table-задача не должна активировать topics и наоборот.
- Ввести A/B eval: одинаковая задача с skill и без него, минимум на двух моделях и с повторами.
- Измерять activation, correctness, must/avoid criteria, turns, tokens, latency и стоимость.
- Сформировать release manifest и generated agent packages; проверять отсутствие drift в CI.

Критерий завершения: опубликованный каталог решает главные developer-задачи, а прирост качества доказан, а не предполагается.

### Этап 2. Замкнуть read-only цикл — 3–6 месяцев

Цель: агент проверяет рекомендации на реальной системе без права её менять.

- Выпустить Docs MCP либо эквивалентный structured documentation endpoint.
- Выпустить Database MCP/CLI adapter с metadata, explain и bounded read queries.
- Ввести отдельную read-only YDB role и готовый setup workflow.
- Добавить row/byte/time caps, redaction, query tags и audit log.
- Поставлять skill + MCP config одним native plugin для 2–3 приоритетных агентов.
- Добавить `ydb ai doctor` и `ydb ai skills install/check/update` в CLI либо отдельный официальный installer.
- Тестировать реальную runtime activation в каждом поддерживаемом приоритетном агенте.

Критерий завершения: пользователь может установить комплект одной командой, подключить least-privilege credential и получить объяснение, подтверждённое schema/plan/metrics.

### Этап 3. Управляемые изменения — 6–12 месяцев

Цель: разрешить ограниченные действия без потери контроля.

- Добавить typed mutation tools только для отобранных workflow.
- Реализовать plan/preview → exact approval → apply.
- Разделить write и destructive permissions; destructive оставить выключенным.
- Использовать short-lived credentials/tokens и per-tool grants.
- Добавить policy packs для developer, reviewer, operator и incident responder.
- Расширить skills на migrations, security, backup/restore и capacity.
- Публиковать change/audit correlation ID в ответе инструмента.

Критерий завершения: каждое изменение можно связать с одобренным планом, credential, tool call и записью аудита.

### Этап 4. Управляемая платформа знаний — 12+ месяцев

Цель: организационный rollout и актуальные знания без ручного копирования.

- Hosted remote MCP с OAuth для облачного YDB-сценария.
- Централизованные org policies и назначение bundles командам.
- Версионированная server-side доставка skills/references.
- Dynamic retrieval только релевантных правил по версии кластера и SDK.
- Семантический слой для аналитики там, где он даёт более надёжный результат, чем NL2YQL.
- Opt-in telemetry по activation/failure и быстрый путь «неверный совет → regression test».

## 9. Метрики, по которым стоит управлять проектом

Количество skills — плохая north-star metric. Нужна сбалансированная панель:

| Группа | Метрика | Что показывает |
|---|---|---|
| Discovery | Activation precision/recall | Нужный skill включается, лишний — нет |
| Quality | Task pass rate и skill lift | Навык действительно улучшает результат |
| Safety | Harmful-advice / forbidden-action rate | Агент не обходит ограничения |
| Grounding | Доля значимых советов с валидным source/version | Рекомендации проверяемы |
| Execution | Compile/execute pass rate примеров | Команды работают на реальной YDB |
| Efficiency | Tokens, turns, latency, cost | Progressive disclosure экономит ресурсы |
| Compatibility | Pass rate по агентам и моделям | Переносимость не декларативна |
| Operations | MCP errors, timeouts, capped responses | Tool-layer пригоден к эксплуатации |
| Freshness | Median age источника и время обновления после upstream change | Контент не отстаёт от продукта |

Для релиза полезен quality gate: новый skill не становится stable, пока не прошёл structure, source, executable, boundary и A/B checks. Экспериментальные skills можно выпускать раньше, но их статус должен быть видим в manifest и installer.

## 10. Решения, которые стоит принять сейчас

### P0 — в ближайшем цикле

1. Утвердить целевой каталог из 6–8 surface-skills и владельцев.
2. Сделать A/B skill-lift и runtime activation частью тестовой стратегии.
3. Добавить live validation YQL/DDL на матрице поддерживаемых YDB versions.
4. Описать contract будущего read-only tool-layer до реализации MCP.
5. Ввести source/version/risk metadata и generated manifests.

### P1 — после наполнения базового каталога

1. Docs MCP.
2. Минимальный read-only Database MCP или адаптер поверх доверенного YDB CLI.
3. Native plugin bundles для приоритетных агентов.
4. CLI lifecycle: install, update, doctor, compatibility check.
5. Public quality dashboard или release report без маркетинговых «поддерживается» там, где нет runtime test.

### P2 — только после накопления эксплуатационных данных

1. Typed write-tools с точным preview и approval.
2. Hosted MCP, OAuth и org policy.
3. Dynamic server-side skills.
4. Semantic analytics layer и более автономные operational workflows.

## 11. Чего делать не стоит

- Не измерять зрелость количеством `SKILL.md`.
- Не копировать документацию в skills целиком.
- Не публиковать универсальный write-capable `run_yql` как default tool.
- Не считать текстовое «спроси подтверждение» security boundary.
- Не поддерживать вручную независимые копии под каждого агента.
- Не обещать поддержку агента, проверив только полный skill как system prompt.
- Не смешивать публичный documentation retrieval с доступом к customer data.
- Не переходить сразу к автономному remediation: сначала диагностика, evidence и наблюдаемость.
- Не строить динамическую доставку знаний до появления стабильной таксономии и версионирования.

## 12. Итоговая рекомендация

Проекту следует развиваться по оси **knowledge quality → read-only evidence → governed action**, а не по оси «больше файлов → больше команд».

На ближайшие полгода наиболее выгодная ставка — закончить предметное покрытие ключевых поверхностей YDB, доказать прирост качества с помощью A/B и runtime evals и дать агенту безопасные read-only primitives для schema, explain и diagnostics. Это закроет самый заметный разрыв с ClickHouse, Redis, MongoDB и Databricks, не создавая преждевременно рискованных write-возможностей.

Среднесрочный продукт — единый устанавливаемый bundle: YDB skills, Docs MCP, Database MCP/CLI adapter, готовая least-privilege role, doctor и native integrations. Долгосрочно тот же стек может стать управляемой capability YDB Cloud с OAuth, per-tool policy, аудитом и централизованными skills.

Такой путь сохраняет сильные стороны текущего репозитория — переносимость, rule IDs, progressive disclosure и строгий mutation gate — и добавляет то, чем сегодня отличаются лидеры: проверяемый эффект, живая обратная связь от базы и управляемая поставка.

## Источники

[^1]: Agent Skills, [Specification](https://agentskills.io/specification) и [Overview](https://agentskills.io/home).
[^2]: Model Context Protocol, [Introduction](https://modelcontextprotocol.io/docs/getting-started/intro).
[^3]: Databricks, [Agent Skills documentation](https://docs.databricks.com/aws/en/agent-skills/).
[^4]: ClickHouse, [Agent Skills repository](https://github.com/ClickHouse/agent-skills).
[^5]: ClickHouse, [authoring and validation guidance](https://github.com/ClickHouse/agent-skills/blob/main/AGENTS.md).
[^6]: ClickHouse, [official MCP server](https://github.com/ClickHouse/mcp-clickhouse).
[^7]: Redis, [Agent Skills repository](https://github.com/redis/agent-skills).
[^8]: Redis, [Build with an agent](https://redis.io/docs/latest/develop/setup/build-with-an-agent/) и [Redis MCP Server](https://redis.io/docs/latest/integrate/redis-mcp/).
[^9]: Redis, [Agent Skills contribution and evaluation policy](https://github.com/redis/agent-skills/blob/main/CONTRIBUTING.md).
[^10]: MongoDB, [Agent Skills repository](https://github.com/mongodb/agent-skills).
[^11]: MongoDB, [MCP Server overview](https://www.mongodb.com/docs/mcp-server/overview/).
[^12]: MongoDB, [MCP Server setup](https://www.mongodb.com/docs/mcp-server/get-started/) и [manual configuration](https://www.mongodb.com/docs/mcp-server/configuration/manual-file-configuration/).
[^13]: MongoDB, [MCP memory and response limits](https://www.mongodb.com/docs/mcp-server/configuration/memory-overflow/).
[^14]: MongoDB, [Agent Skills testing structure](https://github.com/mongodb/agent-skills/tree/main/testing).
[^15]: Microsoft, [PostgreSQL Agent Skills](https://github.com/microsoft/postgres-skills).
[^16]: Neon, [Postgres Agent Skills](https://github.com/neondatabase/postgres-skills).
[^17]: Neon, [archived AI rules repository](https://github.com/neondatabase-labs/ai-rules).
[^18]: Oracle, [Skills catalog](https://github.com/oracle/skills) и [Database router](https://github.com/oracle/skills/blob/main/db/SKILL.md).
[^19]: Oracle, [SQLcl MCP Server documentation](https://docs.oracle.com/en/database/oracle/sql-developer-command-line/25.2/sqcug/sqlcl-mcp-server.html).
[^20]: Oracle Database Blog, [Introducing MCP Server for Oracle Database](https://blogs.oracle.com/database/introducing-mcp-server-for-oracle-database).
[^21]: Oracle, [MySQL MCP Server proof of concept](https://github.com/oracle/mcp/blob/main/src/mysql-mcp-server/README.md).
[^22]: Oracle MySQL Blog, [MySQL development roadmap](https://blogs.oracle.com/mysql/mysql-development-as-it-happens).
[^23]: MariaDB, [Agent Skills repository](https://github.com/MariaDB/skills).
[^24]: MariaDB Corporation, [AI plugins](https://github.com/mariadb-corporation/ai-plugins).
[^25]: Percona Lab, [Database skills](https://github.com/Percona-Lab/skills).
[^26]: Microsoft, [Azure SQL Database container Agent Skills](https://github.com/microsoft/azure-sql-database-container/blob/main/docs/agent-skills.md).
[^27]: Microsoft, [Agent Skills in SQL Server Management Studio](https://github.com/MicrosoftDocs/data-tools/blob/main/ssms/github-copilot/agent-skills.md).
[^28]: Microsoft Learn, [MCP support for SQL](https://learn.microsoft.com/en-us/sql/mcp/) и [Data API Builder MCP overview](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/overview).
[^29]: Snowflake, [Cortex Agents Skills](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-skills).
[^30]: Snowflake Labs, [CoCo Skills](https://github.com/Snowflake-Labs/coco-skills).
[^31]: Snowflake, [Cortex Agents managed MCP](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp).
[^32]: Databricks, [Agent Skills repository](https://github.com/databricks/databricks-agent-skills).
[^33]: Databricks, [Managed MCP servers](https://docs.databricks.com/gcp/en/agents/mcp-tools/managed-mcp).
[^34]: Databricks, [Databricks SQL MCP](https://docs.databricks.com/aws/en/agents/mcp-tools/databricks-sql).
[^35]: Databricks, [Genie MCP](https://docs.databricks.com/aws/en/agents/mcp-tools/genie-mcp).
[^36]: Google, [Skills catalog](https://github.com/google/skills) и [machine-readable index](https://github.com/google/skills/blob/main/index.json).
[^37]: Google, [BigQuery skill MCP usage](https://github.com/google/skills/blob/main/skills/cloud/bigquery-basics/references/mcp-usage.md).
[^38]: Google, [MCP Toolbox extensions](https://github.com/googleapis/mcp-toolbox/blob/main/MCP-TOOLBOX-EXTENSION.md).
[^39]: Cockroach Labs, [CockroachDB Skills](https://github.com/cockroachlabs/cockroachdb-skills) и [usage model](https://github.com/cockroachlabs/cockroachdb-skills/blob/main/docs/usage.md).
[^40]: PingCAP, [AgenticStore agent rules and skills](https://github.com/pingcap/agent-rules).
[^41]: PingCAP, [TiDB repository agent guidance](https://github.com/pingcap/tidb/blob/master/AGENTS.md).
[^42]: Elastic, [Agent Skills repository](https://github.com/elastic/agent-skills).
[^43]: Qdrant, [Skills repository and advisor architecture](https://github.com/qdrant/skills).
[^44]: Qdrant, [Skills scoring methodology](https://github.com/qdrant/skills/blob/main/SCORING.md).
[^45]: Pinecone, [Agent Skills](https://github.com/pinecone-io/skills) и [legacy agent rules](https://github.com/pinecone-io/pinecone-agents-ref).
[^46]: Weaviate, [Agent Skills](https://github.com/weaviate/agent-skills).
[^47]: Neo4j Contrib, [Neo4j Skills](https://github.com/neo4j-contrib/neo4j-skills).
