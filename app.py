from flask import Flask, render_template
from models import db, Project
from parser import FreelanceParser
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///freelancer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# Данные для авторизации (лучше через переменные окружения)
LOGIN = os.environ.get('FREELANCE_LOGIN', 'ваш_логин')
PASSWORD = os.environ.get('FREELANCE_PASSWORD', 'ваш_пароль')

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    projects = Project.query.order_by(Project.created_at.desc()).paginate(page=page, per_page=per_page)
    return render_template('index.html', projects=projects)

@app.route('/run_parser')
def run_parser():
    parser = FreelanceParser(LOGIN, PASSWORD)
    new = parser.run(max_pages=3)   # первые 3 страницы
    return f'Добавлено новых заданий: {new}'

if __name__ == '__main__':
    app.run(debug=True)
