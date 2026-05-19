# parser.py
import re
import time
import requests
from bs4 import BeautifulSoup
from models import db, Project
import os

class FreelanceParser:
    def __init__(self, login, password):
        self.username = login
        self.password = password
        # Адрес FlareSolverr (внутри контейнера доступен на localhost:8191)
        self.flare_url = os.getenv('FLARESOLVERR_URL', 'http://localhost:8191')
        self.session = requests.Session()
        # Заголовки, которые будем передавать в FlareSolverr
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }

    def _request_via_flare(self, method, url, data=None, referer=None):
        """Отправляет запрос через FlareSolverr, возвращает HTML и обновляет cookies"""
        payload = {
            "cmd": "request.get" if method.upper() == "GET" else "request.post",
            "url": url,
            "maxTimeout": 60000,  # 60 секунд на решение Cloudflare
            "cookies": self.session.cookies.get_dict()
        }
        if method.upper() == "POST" and data:
            payload["cmd"] = "request.post"
            payload["postData"] = data
        if referer:
            payload["headers"] = {"Referer": referer}

        # Отправляем запрос к FlareSolverr
        resp = requests.post(f"{self.flare_url}/v1", json=payload, timeout=70)
        result = resp.json()
        if result.get("status") != "ok":
            raise Exception(f"FlareSolverr ошибка: {result.get('message')}")

        solution = result["solution"]
        # Обновляем куки сессии
        self.session.cookies.update(solution.get("cookies", {}))
        # Возвращаем HTML страницы
        return solution.get("response", "")

    def do_login(self):
        print("Авторизация через FlareSolverr...")
        # 1. Получаем страницу логина
        login_html = self._request_via_flare("GET", "https://freelance.ru/login")
        soup = BeautifulSoup(login_html, 'html.parser')
        csrf = None
        meta = soup.find('meta', {'name': 'csrf-token'})
        if meta and meta.get('content'):
            csrf = meta['content']
        else:
            inp = soup.find('input', {'name': '_csrf'})
            if inp and inp.get('value'):
                csrf = inp['value']
        if not csrf:
            raise Exception("Не удалось найти CSRF-токен на странице логина")

        # 2. Формируем POST-данные
        login_data = {
            '_csrf': csrf,
            'LoginForm[email]': self.username,
            'LoginForm[password]': self.password,
            'LoginForm[rememberMe]': '1',
        }
        # Превращаем словарь в строку вида key1=value1&key2=value2
        post_data_str = '&'.join([f"{k}={v}" for k, v in login_data.items()])

        # 3. Отправляем POST-запрос через FlareSolverr
        response_html = self._request_via_flare(
            "POST",
            "https://freelance.ru/auth/login",
            data=post_data_str,
            referer="https://freelance.ru/login"
        )

        # 4. Проверяем успешность входа: если в ответе нет признаков ошибки, считаем успехом
        if "Неверный логин или пароль" in response_html or "Ошибка авторизации" in response_html:
            raise Exception("Ошибка авторизации: неверный логин/пароль")
        print("Авторизация успешна!")
        return True

    def parse_page(self, page_num=1):
        url = f'https://freelance.ru/project/search?page={page_num}'
        html = self._request_via_flare("GET", url)
        soup = BeautifulSoup(html, 'html.parser')
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
