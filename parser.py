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
        # --- 1. Подключаемся к FlareSolverr ---
        # URL и порт, на котором он будет работать внутри контейнера
        self.flare_url = os.getenv('FLARESOLVERR_URL', 'http://localhost:8191')
        self.session = requests.Session()

    def _request_via_flare(self, method, url, data=None):
        """Универсальная функция для всех запросов через FlareSolverr"""
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000, # Увеличиваем таймаут (60 секунд)
            "cookies": self.session.cookies.get_dict()
        }
        if method.upper() == "POST":
            payload["cmd"] = "request.post"
            # FlareSolverr ожидает данные в POST как строку запроса (a=1&b=2)
            # Для этого мы передаем их в поле "postData"
            payload["postData"] = data
        # ... (остальной код без изменений) ...

    def do_login(self):
        print("Пытаемся войти через FlareSolverr...")
        # Получаем страницу логина (GET запрос)
        login_page_html = self._request_via_flare("GET", "https://freelance.ru/login")
        soup = BeautifulSoup(login_page_html, 'html.parser')
        csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
        # Формируем данные для POST запроса
        login_data = {
            '_csrf': csrf_token,
            'LoginForm[email]': self.username,
            'LoginForm[password]': self.password,
            'LoginForm[rememberMe]': '1',
        }
        # Важно! Преобразуем словарь в строку запроса
        post_data_string = '&'.join([f"{k}={v}" for k, v in login_data.items()])
        # Отправляем POST запрос также через FlareSolverr
        response_html = self._request_via_flare("POST", "https://freelance.ru/auth/login", data=post_data_string)
        # Проверяем успешность входа
        return "Ошибка авторизации" not in response_html

    # Методы parse_page и run остаются почти без изменений,
    # но теперь self.session.get/post будут идти через наш новый метод.
