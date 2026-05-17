# Задание 3. Реализация рекомендательных систем

## Цель

Реализовать и проверить несколько типов рекомендательных систем на данных, загруженных в PostgreSQL в задании 2:

1. Content-Based Filtering.
2. Collaborative Filtering.
3. Hybrid Methods.

В отличие от предыдущих лабораторных, источником данных является не CSV напрямую, а PostgreSQL-база `recsys_lab5`.

## Источник данных

Используются таблицы:

| Таблица | Назначение |
|---|---|
| `movies` | Каталог фильмов |
| `ratings` | Оценки пользователей |
| `content_features` | Текстовые признаки фильмов |

После тестовой загрузки в PostgreSQL:

| Объект | Количество |
|---|---:|
| Фильмы | 45433 |
| Пользователи | 270883 |
| Рейтинги | 25980597 |
| Фильмы с `content_features` | 45433 |

## Реализация

Код находится в [`recommenders.py`](recommenders.py).

### 1. Content-Based Filtering

Используется `TfidfVectorizer` из `scikit-learn`.

Входные признаки берутся из таблицы `content_features`, где для каждого фильма заранее собран текстовый профиль:

```text
title + overview + genres + keywords + top cast + director/writer
```

Алгоритм:

1. Загрузить фильмы и `feature_text` из PostgreSQL.
2. Построить TF-IDF-матрицу.
3. Для выбранного фильма посчитать cosine similarity с остальными фильмами.
4. Вернуть топ похожих фильмов.

Метод в коде:

```python
ContentBasedRecommender.similar_movies()
```

### 2. Collaborative Filtering

Используется модель `SVD` из библиотеки `surprise`.

Алгоритм:

1. Загрузить `user_id`, `movie_id`, `rating` из PostgreSQL.
2. Обучить SVD на матрице user-item.
3. Для выбранного пользователя предсказать оценки еще не просмотренных фильмов.
4. Вернуть фильмы с максимальной предсказанной оценкой.

Методы в коде:

```python
CollaborativeRecommender.fit()
CollaborativeRecommender.recommend_for_user()
CollaborativeRecommender.evaluate()
```

### 3. Hybrid Methods

Гибридный метод объединяет:

1. Предсказанную оценку из collaborative filtering.
2. Content similarity между кандидатом и профилем пользователя.

Профиль пользователя строится по фильмам, которым пользователь поставил оценку `>= 4.0`.

Итоговая формула:

```text
hybrid_score = 0.8 * collaborative_score + 0.2 * content_score
```

Перед объединением оба сигнала нормализуются через `MinMaxScaler`.

Вес `alpha = 0.8` выбран по sampled top-N validation на полной базе. После перехода с `ratings_small.csv` на полный `ratings.csv` collaborative-сигнал стал значительно сильнее, поэтому гибрид получает большую долю collaborative-компоненты.

Метод в коде:

```python
HybridRecommender.recommend_for_user()
```

## Запуск

```powershell
.\.venv\Scripts\python.exe Lab_5\task_3\demo.py
```

Или с параметрами:

```powershell
.\.venv\Scripts\python.exe Lab_5\task_3\recommenders.py --user-id 15 --seed-movie-id 318 --top-n 10
```

По умолчанию используется подключение:

```text
postgresql://postgres:1234@127.0.0.1:5433/recsys_lab5
```

## Оценка эффективности

Для collaborative filtering используется разбиение рейтингов на train/test и метрики:

| Метрика | Назначение |
|---|---|
| RMSE | Средняя квадратичная ошибка предсказания рейтинга |
| MAE | Средняя абсолютная ошибка предсказания рейтинга |

Для content-based и hybrid дополнительно используется `hit_rate@10` на выборке пользователей:

1. Берется пользователь с достаточным количеством оценок.
2. Один понравившийся фильм скрывается.
3. Рекомендатель строит топ-10.
4. Проверяется, попал ли скрытый фильм в рекомендации.

Для top-N рекомендаций дополнительно используется стандартная sampled-evaluation схема:

1. Для пользователя скрывается один понравившийся фильм.
2. К нему добавляются 100 негативных кандидатов, которых пользователь не оценивал.
3. Модель ранжирует 101 фильм.
4. Считаются `hit_rate@10`, `precision@10`, `recall@10` и `ndcg@10`.

Такой сценарий лучше отражает качество ранжирования, чем поиск одного фильма среди всего каталога, и часто используется для offline-оценки рекомендательных систем.

Результаты тестового запуска SVD:

| Метод | Метрика | Значение |
|---|---|---:|
| Collaborative Filtering | RMSE mean | 0.8312 |
| Collaborative Filtering | RMSE std | 0.0022 |
| Collaborative Filtering | MAE mean | 0.6347 |
| Collaborative Filtering | MAE std | 0.0016 |
| Collaborative Filtering | folds | 5 |

Результаты sampled top-N evaluation:

| Метод | hit_rate@10 | precision@10 | recall@10 | ndcg@10 |
|---|---:|---:|---:|---:|
| Content-Based Filtering | 0.44 | 0.044 | 0.44 | 0.2646 |
| Collaborative Filtering | 0.59 | 0.059 | 0.59 | 0.3514 |
| Hybrid Method | 0.63 | 0.063 | 0.63 | 0.4123 |

Также была проведена более строгая full-catalog проверка, где скрытый фильм ищется среди всех популярных кандидатов. На ней `hit_rate@10` составил 0.02 для content-based и 0.06 для hybrid. Эти значения ниже, потому что задача существенно сложнее: модель выбирает 10 фильмов из 16691 кандидата, а не из 101.

Для hybrid-оценки скрытые рейтинги исключаются из обучающей выборки перед обучением SVD, чтобы не использовать тестовый ответ при ранжировании.

## Демонстрация

Демонстрационный запуск сохраняет результат в [`demo_results.json`](demo_results.json).

Параметры демо:

| Параметр | Значение |
|---|---:|
| `user_id` | 15 |
| `seed_movie_id` | 318 |
| `top_n` | 10 |
| `max_users` | 5000 |

`movie_id = 318` соответствует фильму `The Shawshank Redemption`.

Для обучения collaborative и hybrid моделей используется воспроизводимая выборка из 5000 активных пользователей полной базы. В эту выборку принудительно добавляется демонстрационный пользователь `15`, чтобы персональные рекомендации строились на его реальной истории оценок.

### Пример результата

Content-based рекомендации для `The Shawshank Redemption`:

| Фильм | Год | Content score |
|---|---:|---:|
| `Girls in Prison` | 1994 | 0.2893 |
| `Brubaker` | 1980 | 0.2781 |
| `Lost for Life` | 2013 | 0.2635 |
| `Brute Force` | 1947 | 0.2398 |
| `Caged` | 1950 | 0.2382 |

Collaborative рекомендации для пользователя `15`:

| Фильм | Год | Predicted rating |
|---|---:|---:|
| `The Godfather` | 1972 | 4.8915 |
| `A Clockwork Orange` | 1971 | 4.8908 |
| `Brazil` | 1985 | 4.7560 |
| `2001: A Space Odyssey` | 1968 | 4.7483 |
| `Taxi Driver` | 1976 | 4.7455 |

Hybrid рекомендации для пользователя `15`:

| Фильм | Год | Hybrid score |
|---|---:|---:|
| `The Godfather` | 1972 | 0.9430 |
| `Taxi Driver` | 1976 | 0.8975 |
| `A Clockwork Orange` | 1971 | 0.8865 |
| `Brazil` | 1985 | 0.8843 |
| `2001: A Space Odyssey` | 1968 | 0.8747 |
