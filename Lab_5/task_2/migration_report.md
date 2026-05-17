# Задание 2. Перенос данных в базу данных

## Цель

Выполнить миграцию исходных CSV-файлов из `Lab_5/datasets/` в PostgreSQL-базу данных, соответствующую архитектуре из задания 1.

В качестве СУБД выбрана PostgreSQL, потому что она поддерживает надежные внешние ключи, индексы, типы `DATE`, `TIMESTAMPTZ`, `BOOLEAN`, масштабируется лучше локальных файловых БД и подходит для дальнейшего развития рекомендательной системы.

## Исходные данные

| CSV-файл | Назначение |
|---|---|
| `movies_metadata.csv` | Метаданные фильмов |
| `links.csv` / `links_small.csv` | Связь MovieLens ID, IMDb ID и TMDB ID |
| `ratings.csv` / `ratings_small.csv` | Оценки пользователей |
| `keywords.csv` | Ключевые слова фильмов |
| `credits.csv` | Актеры и съемочная группа |

Для тестовой загрузки используется `ratings_small.csv` и `links_small.csv`. Полная загрузка может быть выполнена с параметрами `--ratings full --links full`.

## ETL-процесс

ETL реализован в [`etl.py`](etl.py).

### Extract

CSV-файлы считываются через `pandas`. Для больших рейтингов используется чтение чанками, чтобы не загружать весь файл `ratings.csv` в память.

### Transform

На этапе преобразования выполняются следующие действия:

1. Приведение идентификаторов `movieId`, `tmdbId`, `id`, `userId` к числовому типу.
2. Связь таблиц через `links`: `movieId` из MovieLens сопоставляется с `tmdbId` из TMDB.
3. Удаление строк без корректных идентификаторов.
4. Разбор JSON-подобных полей из CSV: `genres`, `belongs_to_collection`, `keywords`, `cast`, `crew`, `production_companies`, `production_countries`, `spoken_languages`.
5. Нормализация списковых признаков в справочники и таблицы связей many-to-many.
6. Преобразование Unix timestamp из рейтингов в `DATETIME`.
7. Формирование таблицы `content_features`, где хранится объединенный текстовый профиль фильма для будущей content-based модели.

### Адаптация данных

Требование по адаптации данных выполнено в ETL-скрипте:

| Требование | Реализация |
|---|---|
| Приведение к единому формату | ID приводятся к числовому типу, даты к `DATE`, timestamps к `TIMESTAMPTZ`, `adult` и `video` к `BOOLEAN` |
| Обработка отсутствующих значений | Строки без обязательных ID удаляются, пустые необязательные значения сохраняются как `NULL` |
| Удаление дубликатов | Фильмы дедублицируются по `movie_id`, связи many-to-many хранятся через `set` и `ON CONFLICT DO NOTHING` |
| Дубликаты справочников | Для `keywords` и `production_companies` используется канонизация по названию, потому что в исходных CSV одно название может иметь несколько ID |
| Невалидные связи | Рейтинги для фильмов, отсутствующих в загруженном каталоге, пропускаются |

### Load

Данные загружаются в таблицы PostgreSQL, созданные по схеме из [`schema_postgres.sql`](schema_postgres.sql).

Порядок загрузки:

1. `collections`
2. `movies`
3. справочники и связи: `genres`, `keywords`, `people`, `production_companies`, `production_countries`, `spoken_languages`
4. `content_features`
5. `users`
6. `ratings`

## Запуск

Если локальный PostgreSQL не установлен, можно поднять контейнер:

```powershell
docker compose -f Lab_5\task_2\docker-compose.yml up -d
```

Тестовая загрузка:

```powershell
.\.venv\Scripts\python.exe Lab_5\task_2\etl.py --recreate
```

Полная загрузка:

```powershell
.\.venv\Scripts\python.exe Lab_5\task_2\etl.py --recreate --ratings full --links full
```

Подключение задается через переменную окружения `DATABASE_URL` или аргумент `--database-url`.

Пример:

```powershell
$env:DATABASE_URL="postgresql://postgres:1234@127.0.0.1:5433/recsys_lab5"
.\.venv\Scripts\python.exe Lab_5\task_2\etl.py --recreate
```

В тестовом окружении использовалась строка:

```text
postgresql://postgres:1234@127.0.0.1:5433/recsys_lab5
```

## Результат тестовой загрузки

После запуска скрипт выводит JSON-отчет с количеством загруженных строк по основным таблицам. Это позволяет быстро проверить, что перенос данных прошел успешно.

## Проверка ETL

На текущем этапе проверены:

1. Установка зависимости `psycopg`.
2. Синтаксис Python-скрипта `etl.py`.
3. CLI-интерфейс скрипта.
4. Чтение CSV-файлов и сопоставление `movieId` с `tmdbId`.

Для `links_small.csv` сопоставлено 9082 фильма с метаданными.

Также при тестировании обнаружены дубли по названиям в `keywords.csv` и `production_companies` при разных исходных ID. В ETL добавлена канонизация по названию: если одно и то же название встречается с несколькими ID, выбирается один канонический ID, а связи many-to-many записываются на него.

## Результат тестовой загрузки в PostgreSQL

Тестовая загрузка выполнена на PostgreSQL `127.0.0.1:5433`, база `recsys_lab5`, источники `ratings_small.csv` и `links_small.csv`.

Итоговые количества:

| Таблица | Строк |
|---|---:|
| `movies` | 9082 |
| `users` | 671 |
| `ratings` | 99810 |
| `genres` | 20 |
| `movie_genres` | 22404 |
| `keywords` | 12936 |
| `movie_keywords` | 63501 |
| `people` | 147599 |
| `movie_cast` | 176695 |
| `movie_crew` | 186245 |
| `content_features` | 9082 |

Из `ratings_small.csv` пропущено 194 рейтинга, потому что для них не нашлось сопоставленного фильма в загруженном каталоге.

Контрольные SQL-запросы вынесены в [`validation_queries.sql`](validation_queries.sql).
