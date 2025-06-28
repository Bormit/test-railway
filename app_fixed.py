# ПОЛНЫЙ КОД С ПРОКСИ для Railway
from flask import Flask, request, jsonify
import sqlite3
import re
import os
import xml.etree.ElementTree as ET
import requests
import yt_dlp
from datetime import datetime
import logging
import html
import random
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Конфигурация базы данных
DB_PATH = os.getenv('DB_PATH', 'transcripts.db')

# НАСТРОЙКИ ПРОКСИ
PROXY_LIST = [
    os.getenv('PROXY_1', ''),
    os.getenv('PROXY_2', ''),
    os.getenv('PROXY_3', ''),
    os.getenv('PROXY_4', ''),
    os.getenv('PROXY_5', ''),
]

# Убираем пустые прокси
PROXY_LIST = [p for p in PROXY_LIST if p]

print(f"🌐 Настроено прокси: {len(PROXY_LIST)}")
for i, proxy in enumerate(PROXY_LIST, 1):
    masked = proxy.split('@')[0] + '@***' if '@' in proxy else proxy[:20] + '***'
    print(f"   Прокси {i}: {masked}")


def init_db():
    """Инициализация базы данных"""
    print("🔧 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
    print("=" * 50)

    try:
        current_dir = os.getcwd()
        print(f"📁 Рабочая директория: {current_dir}")

        data_dir = 'data'
        abs_data_dir = os.path.abspath(data_dir)
        print(f"📁 Создаю папку: {abs_data_dir}")

        os.makedirs(data_dir, exist_ok=True)

        if os.path.exists(data_dir):
            print(f"✅ Папка data создана/существует")
        else:
            print(f"❌ Не удалось создать папку data")
            return False

        abs_db_path = os.path.abspath(DB_PATH)
        print(f"💾 Создаю БД: {abs_db_path}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                language TEXT NOT NULL,
                transcript_text TEXT NOT NULL,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts';")
        table_exists = cursor.fetchone()

        if table_exists:
            print(f"✅ Таблица transcripts создана")
        else:
            print(f"❌ Таблица transcripts НЕ создана")
            conn.close()
            return False

        conn.close()

        if os.path.exists(DB_PATH):
            size = os.path.getsize(DB_PATH)
            print(f"✅ Файл БД создан, размер: {size} байт")
            print(f"📍 Путь к БД: {abs_db_path}")
            return True
        else:
            print(f"❌ Файл БД НЕ создан")
            return False

    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_video_id(url):
    """Извлечение video_id из YouTube URL"""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
        r'youtube\.com/watch\?.*v=([^&\n?#]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_random_proxy():
    """Выбираем случайный прокси из списка"""
    if not PROXY_LIST:
        print("⚠️  ВНИМАНИЕ: Прокси не настроены! Работаем без прокси (будет блокировка)")
        return None

    proxy = random.choice(PROXY_LIST)
    masked = proxy.split('@')[0] + '@***' if '@' in proxy else proxy[:20] + '***'
    print(f"🔄 Используем прокси: {masked}")
    return proxy


def get_transcript_with_proxy(video_id, max_retries=3):
    """
    Получение транскрипции с ротацией прокси
    Пробуем разные прокси при неудачах
    """

    for attempt in range(max_retries):
        print(f"\n🎯 Попытка {attempt + 1}/{max_retries}")

        # Выбираем новый прокси для каждой попытки
        proxy = get_random_proxy()

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Настройки yt-dlp с анти-бот защитой
            ydl_opts = {
                'writesubtitles': False,
                'writeautomaticsub': False,
                'skip_download': True,
                'quiet': False,
                'no_warnings': False,

                # Анти-бот настройки
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',

                # Дополнительные заголовки
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                },

                # Экстрактор YouTube
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['configs'],
                    }
                }
            }

            # Добавляем прокси если есть
            if proxy:
                ydl_opts['proxy'] = proxy

            # Задержка между запросами (важно!)
            if attempt > 0:
                delay = random.uniform(3, 8)
                print(f"⏳ Задержка {delay:.1f}с перед повтором...")
                time.sleep(delay)

            print(f"📡 Прокси: {proxy[:30]}..." if proxy else "📡 Без прокси")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                title = info.get('title', 'Unknown')
                subtitles = info.get('subtitles', {})
                auto_subtitles = info.get('automatic_captions', {})

                print(f"📹 Название: {title}")
                print(f"🎬 Ручные субтитры: {list(subtitles.keys())}")
                print(f"🤖 Автосубтитры: {list(auto_subtitles.keys())[:5]}...")

                # Собираем субтитры (приоритет английским)
                all_subs = []

                if 'en' in subtitles:
                    all_subs.extend(subtitles['en'])
                    print(f"✅ Английские ручные: {len(subtitles['en'])}")
                elif 'en' in auto_subtitles:
                    all_subs.extend(auto_subtitles['en'])
                    print(f"✅ Английские авто: {len(auto_subtitles['en'])}")
                elif subtitles:
                    first_lang = list(subtitles.keys())[0]
                    all_subs.extend(subtitles[first_lang])
                    print(f"✅ Первые доступные ({first_lang}): {len(subtitles[first_lang])}")
                elif auto_subtitles:
                    first_lang = list(auto_subtitles.keys())[0]
                    all_subs.extend(auto_subtitles[first_lang])
                    print(f"✅ Первые авто ({first_lang}): {len(auto_subtitles[first_lang])}")

                if not all_subs:
                    return {
                        'success': False,
                        'error': 'НЕТ ДОСТУПНЫХ СУБТИТРОВ'
                    }

                print(f"📝 Всего субтитров: {len(all_subs)}")

                # Пробуем скачать субтитры
                for i, sub in enumerate(all_subs[:3], 1):  # Первые 3
                    print(f"\n📥 Загрузка субтитров {i}: {sub.get('ext', 'unknown')}")

                    if sub.get('ext') not in ['srv1', 'srv2', 'srv3', 'ttml', 'vtt']:
                        continue

                    sub_url = sub.get('url')
                    if not sub_url:
                        continue

                    try:
                        # Используем тот же прокси для загрузки субтитров
                        proxies = {'http': proxy, 'https': proxy} if proxy else None

                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Referer': 'https://www.youtube.com/'
                        }

                        response = requests.get(sub_url, headers=headers, proxies=proxies, timeout=30)

                        if response.status_code == 200 and len(response.content) > 100:
                            content = response.text

                            # Парсим XML
                            try:
                                clean_content = html.unescape(content)
                                root = ET.fromstring(clean_content)

                                texts = []
                                for text_elem in root.findall('.//text'):
                                    if text_elem.text:
                                        clean_text = text_elem.text.strip()
                                        if clean_text:
                                            texts.append(clean_text)

                                if texts:
                                    full_text = ' '.join(texts)
                                    full_text = re.sub(r'\s+', ' ', full_text).strip()

                                    print(f"🎉 УСПЕХ!")
                                    print(f"📊 Частей: {len(texts)}, Символов: {len(full_text)}")
                                    print(f"📝 Превью: {full_text[:200]}...")

                                    return {
                                        'success': True,
                                        'text': full_text,
                                        'language': 'en',
                                        'title': title,
                                        'proxy_used': proxy[:30] + "..." if proxy else None
                                    }

                            except ET.ParseError as e:
                                print(f"❌ Ошибка парсинга XML: {e}")

                    except Exception as e:
                        print(f"❌ Ошибка загрузки субтитров: {e}")

                print(f"❌ Субтитры не загрузились, пробуем другой прокси...")

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка попытки {attempt + 1}: {error_msg}")

            # Проверяем на bot detection
            if any(keyword in error_msg.lower() for keyword in ['bot', 'sign in', 'confirm', 'captcha']):
                print(f"🤖 YouTube заблокировал прокси, пробуем другой...")
                if attempt < max_retries - 1:
                    continue
                else:
                    return {
                        'success': False,
                        'error': f'YouTube bot detection - все прокси заблокированы: {error_msg}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Техническая ошибка: {error_msg}'
                }

    return {
        'success': False,
        'error': f'Превышено количество попыток ({max_retries})'
    }


@app.route('/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервиса"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'engine': 'yt-dlp-proxy',
        'proxy_count': len(PROXY_LIST)
    })


@app.route('/transcript', methods=['POST'])
def get_video_transcript():
    """Основной endpoint для получения транскрипции с прокси"""
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400

        url = data['url']
        save_to_db = data.get('save', True)

        # Извлекаем video_id
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400

        print(f"\n" + "=" * 60)
        print(f"🎯 ЗАПРОС С ПРОКСИ: {video_id}")
        print(f"🔗 URL: {url}")
        print(f"🌐 Доступно прокси: {len(PROXY_LIST)}")
        print(f"💾 Save to DB: {save_to_db}")

        # Проверяем кеш
        if save_to_db:
            print(f"🔍 ПРОВЕРКА КЕША...")
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT transcript_text, language, created_at, title FROM transcripts WHERE video_id = ?',
                    (video_id,)
                )
                existing = cursor.fetchone()
                conn.close()

                if existing:
                    print(f"✅ НАЙДЕНО В КЕШЕ")
                    return jsonify({
                        'video_id': video_id,
                        'url': url,
                        'text': existing[0],
                        'language': existing[1],
                        'title': existing[3],
                        'cached': True,
                        'created_at': existing[2],
                        'word_count': len(existing[0].split())
                    })
                else:
                    print(f"❌ НЕТ В КЕШЕ - получаем новую транскрипцию")
            except Exception as cache_error:
                print(f"❌ ОШИБКА ПРОВЕРКИ КЕША: {cache_error}")

        # Получаем транскрипцию с прокси
        print(f"🎯 ПОЛУЧЕНИЕ ТРАНСКРИПЦИИ С ПРОКСИ...")
        result = get_transcript_with_proxy(video_id)

        if not result['success']:
            print(f"❌ ОШИБКА: {result['error']}")
            return jsonify({
                'video_id': video_id,
                'url': url,
                'error': result['error'],
                'proxy_count': len(PROXY_LIST)
            }), 422

        print(f"✅ ТРАНСКРИПЦИЯ ПОЛУЧЕНА С ПРОКСИ!")

        # Сохраняем в базу
        if save_to_db:
            print(f"💾 СОХРАНЕНИЕ В БАЗУ ДАННЫХ...")
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                cursor.execute(
                    '''INSERT OR REPLACE INTO transcripts 
                       (video_id, url, title, language, transcript_text, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (video_id, url, result.get('title'), result['language'], result['text'], datetime.now())
                )

                conn.commit()
                conn.close()
                print(f"✅ СОХРАНЕНО В БАЗУ УСПЕШНО!")

            except Exception as db_error:
                print(f"❌ ОШИБКА СОХРАНЕНИЯ В БД: {db_error}")

        return jsonify({
            'video_id': video_id,
            'url': url,
            'text': result['text'],
            'language': result['language'],
            'title': result.get('title'),
            'cached': False,
            'word_count': len(result['text'].split()),
            'proxy_used': result.get('proxy_used'),
            'source': 'yt-dlp-proxy'
        })

    except Exception as e:
        print(f"❌ ОШИБКА API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/transcripts', methods=['GET'])
def list_transcripts():
    """Получение списка всех транскрипций"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        offset = (page - 1) * limit

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Получаем общее количество
        cursor.execute('SELECT COUNT(*) FROM transcripts')
        total = cursor.fetchone()[0]

        # Получаем данные
        cursor.execute('''
            SELECT video_id, url, title, language, 
                   substr(transcript_text, 1, 200) as preview,
                   length(transcript_text) as text_length,
                   created_at, updated_at
            FROM transcripts
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', [limit, offset])

        transcripts = []
        for row in cursor.fetchall():
            transcripts.append({
                'video_id': row[0],
                'url': row[1],
                'title': row[2],
                'language': row[3],
                'preview': row[4] + '...' if len(row[4]) == 200 else row[4],
                'text_length': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            })

        conn.close()

        return jsonify({
            'transcripts': transcripts,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        })

    except Exception as e:
        print(f"❌ Ошибка списка: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/transcript/<video_id>', methods=['GET'])
def get_single_transcript(video_id):
    """Получение полной транскрипции по video_id"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM transcripts WHERE video_id = ?',
            (video_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'error': 'Transcript not found'}), 404

        return jsonify({
            'video_id': row[1],
            'url': row[2],
            'title': row[3],
            'language': row[4],
            'text': row[5],
            'status': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        })

    except Exception as e:
        print(f"❌ Ошибка получения транскрипции: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("🚀 ЗАПУСК YouTube Transcript API С ПРОКСИ")
    print(f"📡 Сервис будет доступен: http://localhost:5000")
    print("🎯 Движок: yt-dlp + residential прокси")
    print(f"🌐 Настроено прокси: {len(PROXY_LIST)}")
    print()

    # Инициализируем БД
    if not init_db():
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать базу данных!")
        exit(1)

    print("\n" + "=" * 60)
    print("🎉 БАЗА ДАННЫХ ГОТОВА!")
    print("🚀 ЗАПУСКАЮ FLASK СЕРВЕР С ПРОКСИ...")
    print("=" * 60)

    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)