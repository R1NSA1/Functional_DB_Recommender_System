# =============================================================================
# ТЕСТИРОВАНИЕ ПОЛЬЗОВАТЕЛЬСКИХ СЦЕНАРИЕВ
# =============================================================================

import psycopg2
import pandas as pd
import random
import datetime

# Подключение к БД
DB_CONFIG = {
    'host': 'localhost',
    'database': 'movie_recommender',
    'user': 'ilyshaaaa',
    'password': ''
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# СЦЕНАРИЙ 1: НОВЫЙ ПОЛЬЗОВАТЕЛЬ
# =============================================================================

def scenario_new_user():
    print("\n" + "="*60)
    print("СЦЕНАРИЙ 1: НОВЫЙ ПОЛЬЗОВАТЕЛЬ (холодный старт)")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Создаем нового пользователя
    username = f"new_user_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    cur.execute("""
        INSERT INTO users (username, email, registration_date, is_active)
        VALUES (%s, %s, CURRENT_DATE, TRUE)
        RETURNING user_id
    """, (username, f"{username}@example.com"))
    user_id = cur.fetchone()[0]
    conn.commit()
    
    print(f"\n✅ Создан пользователь: {username} (ID: {user_id})")
    print(f"❌ История оценок: 0 фильмов")
    
    # 2. Проверяем, что нет оценок
    cur.execute("SELECT COUNT(*) FROM ratings WHERE user_id = %s", (user_id,))
    rating_count = cur.fetchone()[0]
    print(f"📊 Оценок в системе: {rating_count}")
    
    # 3. Решение холодного старта: популярные фильмы
    print("\n📽️ РЕШЕНИЕ: Рекомендации на основе популярности")
    
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies
        WHERE vote_count > 100
        ORDER BY vote_count DESC
        LIMIT 10
    """)
    
    print("\nТоп-10 популярных фильмов:")
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i:2d}. {row[0][:50]:50} | ⭐ {row[1]:.1f} | {row[2]} оценок")
    
    # 4. Альтернатива: опрос жанров
    print("\n📋 АЛЬТЕРНАТИВА: Рекомендации на основе опроса")
    print("   Если бы пользователь выбрал жанр 'Action':")
    
    cur.execute("""
        SELECT m.title, m.vote_average, g.genre_name
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        WHERE g.genre_name = 'Action'
        ORDER BY m.vote_average DESC
        LIMIT 5
    """)
    
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i}. {row[0]} (⭐ {row[1]})")
    
    cur.close()
    conn.close()
    
    return user_id

# =============================================================================
# СЦЕНАРИЙ 2: ОПЫТНЫЙ ПОЛЬЗОВАТЕЛЬ
# =============================================================================

def scenario_experienced_user():
    print("\n" + "="*60)
    print("СЦЕНАРИЙ 2: ОПЫТНЫЙ ПОЛЬЗОВАТЕЛЬ")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Находим пользователя с 20-50 оценками
    cur.execute("""
        SELECT u.user_id, u.username, COUNT(r.rating) as rating_count
        FROM users u
        JOIN ratings r ON u.user_id = r.user_id
        GROUP BY u.user_id, u.username
        HAVING COUNT(r.rating) BETWEEN 20 AND 50
        ORDER BY rating_count DESC
        LIMIT 1
    """)
    
    row = cur.fetchone()
    
    if not row:
        print("\n⚠️ Нет пользователей с 20-50 оценками.")
        print("   Создаем тестового пользователя...")
        
        # Создаем пользователя и добавляем оценки
        cur.execute("""
            INSERT INTO users (username, email, registration_date, is_active)
            VALUES ('experienced_user', 'exp@example.com', CURRENT_DATE, TRUE)
            RETURNING user_id
        """)
        user_id = cur.fetchone()[0]
        
        # Добавляем 30 случайных оценок
        cur.execute("SELECT movie_id FROM movies LIMIT 50")
        movies = cur.fetchall()
        
        for movie in movies[:30]:
            rating = random.choice([3.0, 3.5, 4.0, 4.5, 5.0])
            cur.execute("""
                INSERT INTO ratings (user_id, movie_id, rating, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id, movie_id) DO NOTHING
            """, (user_id, movie[0], rating))
        
        conn.commit()
        rating_count = 30
        username = "experienced_user"
    else:
        user_id, username, rating_count = row
    
    print(f"\n✅ Пользователь: {username} (ID: {user_id})")
    print(f"📊 История оценок: {rating_count} фильмов")
    
    # Получаем любимые жанры пользователя
    cur.execute("""
        SELECT g.genre_name, COUNT(*) as count
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        WHERE r.user_id = %s AND r.rating >= 4
        GROUP BY g.genre_name
        ORDER BY count DESC
        LIMIT 3
    """, (user_id,))
    
    favorite_genres = [row[0] for row in cur.fetchall()]
    print(f"🎯 Любимые жанры: {', '.join(favorite_genres)}")
    
    # Рекомендации на основе любимых жанров
    if favorite_genres:
        placeholders = ','.join(['%s'] * len(favorite_genres))
        query = f"""
            SELECT DISTINCT m.title, m.vote_average, g.genre_name
            FROM movies m
            JOIN movie_genres mg ON m.movie_id = mg.movie_id
            JOIN genres g ON mg.genre_id = g.genre_id
            WHERE g.genre_name IN ({placeholders})
            AND m.movie_id NOT IN (SELECT movie_id FROM ratings WHERE user_id = %s)
            ORDER BY m.vote_average DESC
            LIMIT 10
        """
        params = favorite_genres + [user_id]
        cur.execute(query, params)
        
        print("\n📽️ ПЕРСОНАЛИЗИРОВАННЫЕ РЕКОМЕНДАЦИИ:")
        for i, row in enumerate(cur.fetchall(), 1):
            print(f"  {i:2d}. {row[0][:50]:50} | ⭐ {row[1]:.1f} | {row[2]}")
    
    cur.close()
    conn.close()

# =============================================================================
# СЦЕНАРИЙ 3: ЭКСПЕРТ
# =============================================================================

def scenario_expert():
    print("\n" + "="*60)
    print("СЦЕНАРИЙ 3: ЭКСПЕРТ (киноман)")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Находим пользователя с максимальным количеством оценок
    cur.execute("""
        SELECT u.user_id, u.username, COUNT(r.rating) as rating_count,
               AVG(r.rating) as avg_rating
        FROM users u
        JOIN ratings r ON u.user_id = r.user_id
        GROUP BY u.user_id, u.username
        ORDER BY rating_count DESC
        LIMIT 1
    """)
    
    row = cur.fetchone()
    
    if row:
        user_id, username, rating_count, avg_rating = row
        print(f"\n✅ Эксперт: {username} (ID: {user_id})")
        print(f"📊 Оценок: {rating_count} | Средний рейтинг: {avg_rating:.1f}")
        
        # Глубокие рекомендации (коллаборативная фильтрация)
        print("\n📽️ ГЛУБОКИЕ РЕКОМЕНДАЦИИ (коллаборативная фильтрация):")
        
        # Находим похожих пользователей
        cur.execute("""
            SELECT r2.user_id, COUNT(*) as common
            FROM ratings r1
            JOIN ratings r2 ON r1.movie_id = r2.movie_id
            WHERE r1.user_id = %s AND r2.user_id != %s
            GROUP BY r2.user_id
            ORDER BY common DESC
            LIMIT 5
        """, (user_id, user_id))
        
        similar_users = [row[0] for row in cur.fetchall()]
        
        if similar_users:
            placeholders = ','.join(['%s'] * len(similar_users))
            query = f"""
                SELECT m.title, AVG(r.rating) as avg_rating, COUNT(*) as recommendations
                FROM ratings r
                JOIN movies m ON r.movie_id = m.movie_id
                WHERE r.user_id IN ({placeholders})
                AND r.movie_id NOT IN (SELECT movie_id FROM ratings WHERE user_id = %s)
                GROUP BY m.title
                HAVING COUNT(*) >= 2
                ORDER BY avg_rating DESC, recommendations DESC
                LIMIT 10
            """
            params = similar_users + [user_id]
            cur.execute(query, params)
            
            for i, row in enumerate(cur.fetchall(), 1):
                print(f"  {i:2d}. {row[0][:50]:50} | ⭐ {row[1]:.1f} | {row[2]} экспертов")
        else:
            print("  Нет похожих пользователей для сравнения")
    else:
        print("\n⚠️ Эксперты не найдены")
    
    cur.close()
    conn.close()

# =============================================================================
# СЦЕНАРИЙ 4: НОВЫЙ ФИЛЬМ
# =============================================================================

def scenario_new_movie():
    print("\n" + "="*60)
    print("СЦЕНАРИЙ 4: НОВЫЙ ФИЛЬМ (холодный старт товара)")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Создаем новый фильм (только в анализе, физически не добавляем)
    new_movie = {
        'title': 'Новый блокбастер 2024',
        'genres': ['Action', 'Sci-Fi']
    }
    
    print(f"\n🎬 Новый фильм: {new_movie['title']}")
    print(f"🏷️ Жанры: {', '.join(new_movie['genres'])}")
    print("❌ Оценок пока нет (0)")
    
    # Решение: рекомендация на основе жанров
    placeholders = ','.join(['%s'] * len(new_movie['genres']))
    query = f"""
        SELECT m.title, m.vote_average, COUNT(r.rating) as rating_count
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        LEFT JOIN ratings r ON m.movie_id = r.movie_id
        WHERE g.genre_name IN ({placeholders})
        GROUP BY m.title, m.vote_average
        ORDER BY rating_count DESC, m.vote_average DESC
        LIMIT 10
    """
    cur.execute(query, new_movie['genres'])
    
    print("\n📽️ ПОХОЖИЕ ФИЛЬМЫ (для старта рекомендаций):")
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i:2d}. {row[0][:50]:50} | ⭐ {row[1]:.1f} | {row[2]} оценок")
    
    cur.close()
    conn.close()

# =============================================================================
# ЗАПУСК ВСЕХ СЦЕНАРИЕВ
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ПОЛЬЗОВАТЕЛЬСКИХ СЦЕНАРИЕВ")
    print("Рекомендательная система фильмов")
    print("="*60)
    
    # Запуск всех сценариев
    scenario_new_user()
    scenario_experienced_user()
    scenario_expert()
    scenario_new_movie()
    
    print("\n" + "="*60)
    print("✅ Тестирование завершено!")
    print("="*60)
