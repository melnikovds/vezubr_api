import pytest
import requests
from config.settings import BASE_URL, TIMEOUT, accounts


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

        payload = {
            "username": email,
            "password": password
        }

        response = requests.post(
            f"{BASE_URL}/user/login",
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

def pytest_addoption(parser):
    parser.addoption(
        "--cargo-count",
        action="store",
        default="100",  # Значение по умолчанию
        help="Количество грузомест для генерации в тестах"
    )

@pytest.fixture
def cargo_count(request):
    return int(request.config.getoption("--cargo-count"))
