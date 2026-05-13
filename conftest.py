import pytest
import requests
from config.settings import *


@pytest.fixture(scope="session")
def get_auth_token():
    tokens = {}

    def _login(role: str):

        # проверяем есть ли такая роль в settings
        if role not in accounts:
            raise ValueError(f"Неизвестная роль: {role}")

        # если токен уже получали то возвращаем из кеша
        if role in tokens:
            return tokens[role]

        email = accounts[role]["email"]
        password = accounts[role]["password"]

        print(f"\n[Auth] Запрос роли: {role}")
        print(f"[Auth] Email: {email}")

        if role.endswith("_ext"):
            login_url = f"{EXTERNAL_URL}/user/login"
            print(f"[Auth] URL: {login_url} (EXTERNAL)")
        else:
            login_url = f"{BASE_URL}/user/login"
            print(f"[Auth] URL: {login_url} (BASE)")

        payload = {
            "username": email,
            "password": password
        }

        response = requests.post(
            login_url,
            json=payload,
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"Login failed: {response.text}"

        data = response.json()

        token_info = {
            "token": data["token"],
            "role": data["role"]
        }

        # сохраняем в кеш
        tokens[role] = token_info

        return token_info

    return _login

@pytest.fixture
def lkz_token(get_auth_token):
    """Токен пользователя LKZ (заказчик)"""
    return get_auth_token("lkz")["token"]

@pytest.fixture
def lke_token(get_auth_token):
    """Токен пользователя LKE (исполнитель)"""
    return get_auth_token("lke")["token"]

@pytest.fixture
def lkp_token(get_auth_token):
    """Токен пользователя LKP (подрядчик)"""
    return get_auth_token("lkp")["token"]

@pytest.fixture
def lkz_ext_token(get_auth_token):
    return get_auth_token("lkz_ext")["token"]

@pytest.fixture
def lke_ext_token(get_auth_token):
    return get_auth_token("lke_ext")["token"]

@pytest.fixture
def lkp_ext_token(get_auth_token):
    return get_auth_token("lkp_ext")["token"]

@pytest.fixture
def auth_token(request, get_auth_token):
    role = request.param
    return get_auth_token(role)["token"]

@pytest.fixture
def auth_token_ext(request, get_auth_token):
    role = request.param
    return get_auth_token(role)["token"]

@pytest.fixture
def auth_token_base(request, get_auth_token):
    role = request.param
    return get_auth_token(role)["token"]

def pytest_addoption(parser):
    parser.addoption(
        "--cargo-count",
        action="store",
        default="300",  # Значение по умолчанию
        help="Количество грузомест для генерации в тестах"
    )

@pytest.fixture
def cargo_count(request):
    return int(request.config.getoption("--cargo-count"))




@pytest.fixture(scope="session")
def get_auth_token_prod():
    tokens = {}

    def _login(role: str):

        # проверяем есть ли такая роль в settings
        if role not in accounts_prod:
            raise ValueError(f"Неизвестная роль: {role}")

        # если токен уже получали то возвращаем из кеша
        if role in tokens:
            return tokens[role]

        email = accounts_prod[role]["email"]
        password = accounts_prod[role]["password"]

        print(f"\n[Auth] Запрос роли: {role}")
        print(f"[Auth] Email: {email}")

        # всегда используем домен 'ru' для PROD
        if role.endswith("_ext"):
            login_url = f"{make_external_url('ru')}/user/login"
            print(f"[Auth] URL: {login_url} (EXTERNAL / RU)")
        else:
            login_url = f"{make_base_url('ru')}/user/login"
            print(f"[Auth] URL: {login_url} (BASE / RU)")

        payload = {
            "username": email,
            "password": password
        }

        response = requests.post(
            login_url,
            json=payload,
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"Login failed: {response.text}"

        data = response.json()

        token_info = {
            "token": data["token"],
            "role": data["role"]
        }

        # сохраняем в кеш
        tokens[role] = token_info

        return token_info

    return _login

@pytest.fixture
def lkz_token_prod(get_auth_token_prod):
    return get_auth_token_prod("lkz")["token"]

# @pytest.fixture
# def lke_token_prod(get_auth_token_prod):
#     return get_auth_token_prod("lke")["token"]

@pytest.fixture
def lkp_token_prod(get_auth_token_prod):
    return get_auth_token_prod("lkp")["token"]

@pytest.fixture
def lkz_ext_token_prod(get_auth_token_prod):
    return get_auth_token_prod("lkz_ext")["token"]

# @pytest.fixture
# def lke_ext_token_prod(get_auth_token_prod):
#     return get_auth_token_prod("lke_ext")["token"]

@pytest.fixture
def lkp_ext_token_prod(get_auth_token_prod):
    return get_auth_token_prod("lkp_ext")["token"]




@pytest.fixture(scope="session")
def get_auth_token_dev():
    tokens = {}

    def _login(role: str):

        # проверяем есть ли такая роль в settings
        if role not in accounts_dev:
            raise ValueError(f"Неизвестная роль: {role}")

        # если токен уже получали то возвращаем из кеша
        if role in tokens:
            return tokens[role]

        email = accounts_dev[role]["email"]
        password = accounts_dev[role]["password"]

        print(f"\n[Auth] Запрос роли: {role}")
        print(f"[Auth] Email: {email}")

        # всегда используем домен 'dev' для DEV
        if role.endswith("_ext"):
            login_url = f"{make_external_url('dev')}/user/login"
            print(f"[Auth] URL: {login_url} (EXTERNAL / DEV)")
        else:
            login_url = f"{make_base_url('dev')}/user/login"
            print(f"[Auth] URL: {login_url} (BASE / DEV)")

        payload = {
            "username": email,
            "password": password
        }

        response = requests.post(
            login_url,
            json=payload,
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"Login failed: {response.text}"

        data = response.json()

        token_info = {
            "token": data["token"],
            "role": data["role"]
        }

        # сохраняем в кеш
        tokens[role] = token_info

        return token_info

    return _login

@pytest.fixture
def lkz_token_dev(get_auth_token_dev):
    return get_auth_token_dev("lkz")["token"]

# @pytest.fixture
# def lke_token_dev(get_auth_token_dev):
#     return get_auth_token_dev("lke")["token"]

@pytest.fixture
def lkp_token_dev(get_auth_token_dev):
    return get_auth_token_dev("lkp")["token"]

@pytest.fixture
def lkz_ext_token_dev(get_auth_token_dev):
    return get_auth_token_dev("lkz_ext")["token"]

# @pytest.fixture
# def lke_ext_token_dev(get_auth_token_dev):
#     return get_auth_token_dev("lke_ext")["token"]

@pytest.fixture
def lkp_ext_token_dev(get_auth_token_dev):
    return get_auth_token_dev("lkp_ext")["token"]
