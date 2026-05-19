# parser.py
import re
import time
from bs4 import BeautifulSoup
from models import db, Project
import cloudscraper  # ai-cloudscraper предоставляет этот интерфейс
import os

class FreelanceParser:
    def __init__(self, login, password):
        self.username = login
        self.password = password
        # Создаем сессию через улучшенную библиотеку
        self.session = cloudscraper.create_scraper(
            interpreter='nodejs',   # Используем NodeJS для выполнения JS
            delay=15,               # Задержка перед запросом
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        # Устанавливаем полные заголовки браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def do_login(self):
        print("Пытаемся авторизоваться через ai-cloudscraper...")
        login_url = 'https://freelance.ru/login'
        resp = self.session.get(login_url, timeout=30)
        if resp.status_code != 200:
            raise Exception(f'Ошибка загрузки страницы логина: {resp.status_code}')
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Ищем CSRF-токен
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag and meta_tag.get('content'):
            csrf_token = meta_tag['content']
        else:
            input_tag = soup.find('input', {'name': '_csrf'})
            if input_tag and input_tag.get('value'):
                csrf_token = input_tag['value']
        
        if not csrf_token:
            raise Exception('CSRF токен не найден на странице входа.')
        
        # Отправляем POST-запрос для входа
        login_post_url = 'https://freelance.ru/auth/login'
        payload = {
            '_csrf': csrf_token,
            'LoginForm[email]': self.username,
            'LoginForm[password]': self.password,
            'LoginForm[rememberMe]': '1',
        }
        headers = {
            'Origin': 'https://freelance.ru',
            'Referer': login_url,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        time.sleep(2)
        resp = self.session.post(login_post_url, data=payload, headers=headers, timeout=30)
        
        if resp.status_code == 302 or 'PHPSESSID' in self.session.cookies:
            print("Авторизация успешна!")
            return True
        else:
            raise Exception(f'Ошибка авторизации. Статус: {resp.status_code}')
    
    # Остальные методы parse_page и run остаются без изменений
    def parse_page(self, page_num=1):
        url = f'https://freelance.ru/project/search?page={page_num}'
        resp = self.session.get(url, timeout=30)
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
            time.sleep(2)
        return new_count
