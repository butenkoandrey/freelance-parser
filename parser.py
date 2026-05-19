import re
import requests
from bs4 import BeautifulSoup
from time import sleep
from models import db, Project

class FreelanceParser:
    def __init__(self, login, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.username = login
        self.password = password

    def do_login(self):
        # 1. Загружаем страницу логина
        login_url = 'https://freelance.ru/login'
        resp = self.session.get(login_url)
        if resp.status_code != 200:
            raise Exception(f'Ошибка загрузки страницы логина: {resp.status_code}')
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 2. Ищем CSRF-токен (в meta-теге или в скрытом поле формы)
        csrf = None
        meta = soup.find('meta', {'name': 'csrf-token'})
        if meta and meta.get('content'):
            csrf = meta['content']
        else:
            input_csrf = soup.find('input', {'name': '_csrf'})
            if input_csrf and input_csrf.get('value'):
                csrf = input_csrf['value']
        
        if not csrf:
            # Если не нашли – сохраняем кусок HTML для диагностики
            raise Exception(f'CSRF токен не найден. Первые 500 символов ответа:\n{resp.text[:500]}')
        
        # 3. Отправляем POST с данными авторизации
        login_post_url = 'https://freelance.ru/auth/login'
        payload = {
            '_csrf': csrf,
            'LoginForm[email]': self.username,
            'LoginForm[password]': self.password,
            'LoginForm[rememberMe]': '1',
        }
        headers = {
            'Referer': login_url,
            'Origin': 'https://freelance.ru',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        resp = self.session.post(login_post_url, data=payload, headers=headers)
        
        # 4. Проверяем успешность входа (редирект на главную или наличие куки PHPSESSID)
        if resp.status_code == 302 or 'PHPSESSID' in self.session.cookies:
            return True
        else:
            raise Exception(f'Ошибка авторизации. Статус: {resp.status_code}, тело: {resp.text[:200]}')

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

    def run(self, max_pages=3):
        self.do_login()
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
