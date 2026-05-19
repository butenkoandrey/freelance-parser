import re
import requests
from bs4 import BeautifulSoup
from time import sleep
from models import db, Project

class FreelanceParser:
    def __init__(self, login, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.username = login   # ← переименовали, чтобы не конфликтовать с методом login()
        self.password = password

    def do_login(self):         # ← метод переименован
        resp = self.session.get('https://freelance.ru/login')
        soup = BeautifulSoup(resp.text, 'html.parser')
        csrf = soup.find('meta', {'name': 'csrf-token'})['content']
        payload = {
            '_csrf': csrf,
            'LoginForm[email]': self.username,
            'LoginForm[password]': self.password,
            'LoginForm[rememberMe]': 1
        }
        resp = self.session.post('https://freelance.ru/auth/login', data=payload)
        return resp.ok

    def parse_page(self, page_num=1):
        url = f'https://freelance.ru/project/search?page={page_num}'
        resp = self.session.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        projects = []
        for card in soup.select('.project-item-default-card'):
            link_tag = card.select_one('.title a')
            if not link_tag:
                continue
            href = link_tag.get('href')
            match = re.search(r'-(\d+)\.html', href)
            if not match:
                continue
            project_id = match.group(1)
            title = link_tag.get_text(strip=True)
            url_full = 'https://freelance.ru' + href
            desc_tag = card.select_one('.description')
            description = desc_tag.get_text(strip=True) if desc_tag else ''
            cost_tag = card.select_one('.cost')
            cost = cost_tag.get_text(strip=True) if cost_tag else 'Договорная'
            category_tag = card.select_one('.specs-list b')
            category = category_tag.get_text(strip=True) if category_tag else ''
            time_tag = card.select_one('.publish-time time')
            published = time_tag['datetime'] if time_tag and time_tag.get('datetime') else None
            projects.append({
                'project_id': int(project_id),
                'title': title,
                'url': url_full,
                'description': description,
                'cost': cost,
                'category': category,
                'published_at': published
            })
        return projects

    def run(self, max_pages=5):
        self.do_login()          # ← вызываем метод, а не строку
        new_count = 0
        for page in range(1, max_pages + 1):
            print(f'Парсинг страницы {page}...')
            projects = self.parse_page(page)
            for p in projects:
                exists = Project.query.get(p['project_id'])
                if not exists:
                    proj = Project(**p)
                    db.session.add(proj)
                    new_count += 1
            db.session.commit()
            sleep(2)
        return new_count