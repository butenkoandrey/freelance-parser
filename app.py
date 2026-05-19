import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from models import db, Project
from parser import FreelanceParser

load_dotenv()

app = Flask(__name__)

# Настройка базы данных (PostgreSQL через Render или SQLite локально)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///freelancer.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Создание таблиц при запуске (если ещё не созданы)
with app.app_context():
    db.create_all()

# Данные для авторизации из переменных окружения
LOGIN = os.getenv('FREELANCE_LOGIN')
PASSWORD = os.getenv('FREELANCE_PASSWORD')

@app.route('/')
def index():
    """Главная страница со списком сохранённых заданий"""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    projects = Project.query.order_by(Project.created_at.desc()).paginate(page=page, per_page=per_page)
    return render_template('index.html', projects=projects)

@app.route('/run_parser')
def run_parser():
    """Запуск парсинга (вручную или через Cron Job)"""
    if not LOGIN or not PASSWORD:
        return 'Ошибка: не заданы логин или пароль в переменных окружения', 500
    
    parser = FreelanceParser(LOGIN, PASSWORD)
    try:
        new_count = parser.run(max_pages=3)   # парсим первые 3 страницы
        return f'Парсинг завершён. Добавлено новых заданий: {new_count}'
    except Exception as e:
        return f'Ошибка при парсинге: {str(e)}', 500

@app.route('/health')
def health():
    """Проверка работоспособности (для мониторинга)"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
