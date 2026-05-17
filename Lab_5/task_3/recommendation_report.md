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
| Фильмы | 9082 |
| Пользователи | 671 |
| Рейтинги | 99810 |
| Фильмы с `content_features` | 9082 |

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
hybrid_score = 0.6 * collaborative_score + 0.4 * content_score
```

Перед объединением оба сигнала нормализуются через `MinMaxScaler`.

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

Результаты тестового запуска:

| Метод | Метрика | Значение |
|---|---|---:|
| Collaborative Filtering | RMSE | 0.8902 |
| Collaborative Filtering | MAE | 0.6867 |
| Collaborative Filtering | test ratings | 19962 |
| Content-Based Filtering | hit_rate@10 | 0.02 |
| Hybrid Method | hit_rate@10 | 0.06 |

`hit_rate@10` рассчитан на 50 пользователях. Для hybrid-оценки скрытые рейтинги исключаются из обучающей выборки перед обучением SVD, чтобы не использовать тестовый ответ при ранжировании.

## Демонстрация

Демонстрационный запуск сохраняет результат в [`demo_results.json`](demo_results.json).

Параметры демо:

| Параметр | Значение |
|---|---:|
| `user_id` | 15 |
| `seed_movie_id` | 318 |
| `top_n` | 10 |

`movie_id = 318` соответствует фильму `The Shawshank Redemption`.

### Пример результата

Content-based рекомендации для `The Shawshank Redemption`:

| Фильм | Год | Content score |
|---|---:|---:|
| `Brubaker` | 1980 | 0.2688 |
| `Cool Hand Luke` | 1967 | 0.1874 |
| `Double Jeopardy` | 1999 | 0.1799 |
| `No Escape` | 1994 | 0.1760 |
| `Starred Up` | 2013 | 0.1715 |

Collaborative рекомендации для пользователя `15`:

| Фильм | Год | Predicted rating |
|---|---:|---:|
| `Breaking the Waves` | 1996 | 3.5135 |
| `Cinema Paradiso` | 1988 | 3.4192 |
| `The Professional` | 1981 | 3.3620 |
| `Howl's Moving Castle` | 2004 | 3.3599 |
| `It Happened One Night` | 1934 | 3.3142 |

Hybrid рекомендации для пользователя `15`:

| Фильм | Год | Hybrid score |
|---|---:|---:|
| `Dial M for Murder` | 1954 | 0.8683 |
| `The Professional` | 1981 | 0.8009 |
| `Sabrina` | 1954 | 0.7777 |
| `Breaking the Waves` | 1996 | 0.7721 |
| `Platoon` | 1986 | 0.7473 |
