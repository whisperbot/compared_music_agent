from flask import Flask, render_template_string, request, jsonify, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'data.db'

# 数据库连接
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 初始化数据库
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # 配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        # 视频表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vid TEXT UNIQUE NOT NULL,
                url1 TEXT NOT NULL,
                url2 TEXT NOT NULL,
                url3 TEXT,
                url4 TEXT
            )
        ''')
        # 标注表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                best_version INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id),
                UNIQUE(video_id, user_name)
            )
        ''')
        # 初始化默认配置
        cursor.execute('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', ('video_count', '4'))
        db.commit()

# 首页
@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

# 获取配置
@app.route('/api/config', methods=['GET'])
def get_config():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', ('video_count',))
    row = cursor.fetchone()
    video_count = int(row['value']) if row else 4
    return jsonify({'video_count': video_count})

# 设置配置
@app.route('/api/config', methods=['POST'])
def set_config():
    video_count = request.json.get('video_count')
    if video_count not in [2, 3, 4]:
        return jsonify({'error': '视频数量必须是2、3或4'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('video_count', str(video_count)))
    db.commit()
    return jsonify({'success': True, 'video_count': video_count})

# 获取下一个待标注视频
@app.route('/api/next', methods=['POST'])
def get_next_video():
    user_name = request.json.get('user_name', '').strip()
    if not user_name:
        return jsonify({'error': '请输入用户名'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 获取视频数量配置
    cursor.execute('SELECT value FROM config WHERE key = ?', ('video_count',))
    row = cursor.fetchone()
    video_count = int(row['value']) if row else 4
    
    # 找用户没标注过的视频
    cursor.execute('''
        SELECT v.id, v.vid, v.url1, v.url2, v.url3, v.url4
        FROM videos v
        LEFT JOIN annotations a ON v.id = a.video_id AND a.user_name = ?
        WHERE a.id IS NULL
        ORDER BY v.id ASC
        LIMIT 1
    ''', (user_name,))
    video = cursor.fetchone()
    
    if not video:
        return jsonify({'done': True, 'message': '🎉 你已经完成了所有视频标注！感谢参与~'})
    
    # 统计总进度
    cursor.execute('SELECT COUNT(*) FROM videos')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM annotations WHERE user_name = ?', (user_name,))
    done = cursor.fetchone()[0]
    
    # 根据配置返回相应数量的URL
    urls = [video['url1'], video['url2'], video['url3'], video['url4']][:video_count]
    
    return jsonify({
        'done': False,
        'video_count': video_count,
        'video': {
            'id': video['id'],
            'vid': video['vid'],
            'urls': urls
        },
        'progress': {'done': done, 'total': total, 'percent': round((done+1)/total*100) if total>0 else 0}
    })

# 提交标注结果
@app.route('/api/submit', methods=['POST'])
def submit_annotation():
    user_name = request.json.get('user_name', '').strip()
    video_id = request.json.get('video_id')
    best_version = request.json.get('best_version')
    
    if not user_name or not video_id or best_version not in [1,2,3,4,5,6]:
        return jsonify({'error': '参数错误'}), 400
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO annotations (video_id, user_name, best_version)
            VALUES (?, ?, ?)
        ''', (video_id, user_name, best_version))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取标注统计结果
@app.route('/api/stats')
def get_stats():
    db = get_db()
    cursor = db.cursor()
    
    # 总标注数
    cursor.execute('SELECT COUNT(*) FROM annotations')
    total_annotations = cursor.fetchone()[0]
    
    # 参与人数
    cursor.execute('SELECT COUNT(DISTINCT user_name) FROM annotations')
    total_users = cursor.fetchone()[0]
    
    # 每个版本的得票率
    cursor.execute('''
        SELECT best_version, COUNT(*) as count 
        FROM annotations 
        WHERE best_version IN (1,2,3,4)
        GROUP BY best_version
    ''')
    version_votes = {row[0]: row[1] for row in cursor.fetchall()}
    
    return jsonify({
        'total_annotations': total_annotations,
        'total_users': total_users,
        'version_votes': version_votes
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=True)
