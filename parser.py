# parser.py
import re
import time
import cloudscraper
from bs4 import BeautifulSoup
from models import db, Project

class FreelanceParser:
    def __init__(self, login, password):
        self.username = login
        self.password = password
        # Создаём сессию с расширенными настройками для обхода Cloudflare
        self.session = self._create_session()

    def _create_session(self):
        """Создаёт сессию cloudscraper с эмуляцией реального браузера"""
        scraper = cloudscraper.create_scraper(
            interpreter='nodejs',          # используем Node.js для выполнения JS (если доступен)
            delay=15,                      # задержка перед запросом (имитация человека)
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True
            }
        )
        # Полный набор заголовков, как у реального Chrome
        scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        return scraper

    def do_login(self, retries=3):
        """Авторизация на сайте с повторными попытками"""
        for attempt in range(retries):
            try:
                # 1. Загружаем страницу входа
                login_url = 'https://freelance.ru/login'
                resp = self.session.get(login_url, timeout=30)
                if resp.status_code != 200:
                    raise Exception(f'HTTP {resp.status_code} при загрузке страницы логина')

                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 2. Ищем CSRF-токен
                csrf = None
                meta = soup.find('meta', {'name': 'csrf-token'})
                if meta and meta.get('content'):
                    csrf = meta['content']
                else:
                    input_csrf = soup.find('input', {'name': '_csrf'})
                    if input_csrf and input_csrf.get('value'):
                        csrf = input_csrf['value']

                if not csrf:
                    # Возможно, Cloudflare ещё не пропустил – пробуем снова
                    raise Exception('CSRF токен не найден. Возможно, страница ещё не загрузилась.')

                # 3. Отправляем POST-запрос с данными формы
                login_post_url = 'https://freelance.ru/auth/login'
                payload = {
                    '_csrf': csrf,
                    'LoginForm[email]': self.username,
                    'LoginForm[password]': self.password,
                    'LoginForm[rememberMe]': '1',
                }
                headers = {
                    'Origin': 'https://freelance.ru',
                    'Referer': login_url,
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
                time.sleep(2)  # небольшая пауза перед отправкой
                resp = self.session.post(login_post_url, data=payload, headers=headers, timeout=30)

                # 4. Проверяем успешность входа
                if resp.status_code == 302 or 'PHPSESSID' in self.session.cookies:
                    return True
                else:
                    raise Exception(f'Не удалось войти. Статус: {resp.status_code}')
            
            except Exception as e:
                print(f'Попытка {attempt+1} из {retries} не удалась: {e}')
                if attempt < retries - 1:
                    time.sleep(5)  # ждём перед повторной попыткой
                else:
                    raise Exception(f'Не удалось авторизоваться после {retries} попыток: {e}')

    def parse_page(self, page_num=1):
        """Парсинг одной страницы с проектами"""
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
        """Запуск парсинга: авторизация + обход страниц + сохранение новых проектов"""
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
            time.sleep(2)  # пауза между запросами
        return new_count
