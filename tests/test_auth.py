import allure
import pytest


@allure.story("Smoke test")
@allure.feature("Авторизация")
@allure.description("Проверка успешной авторизации: получение токена и роли.")
@pytest.mark.parametrize("role", ["lkz", "lke", "lkp"])
def test_get_access_token(role, get_auth_token):
    with allure.step(f"Авторизация под ролью '{role}'"):
        auth_data = get_auth_token(role)
        token_str = auth_data["token"]
        role_id = auth_data["role"]

    with allure.step("Валидация токена"):
        # Токен — строка вида "Bearer <JWT>"
        assert isinstance(token_str, str), "Токен должен быть строкой"
        assert len(token_str) > 7, "Токен должен быть непустым и содержать 'Bearer '"
        assert token_str.startswith("Bearer "), "Токен должен начинаться с 'Bearer '"

        # Проверяем, что после 'Bearer ' идёт JWT (xxx.yyy.zzz)
        jwt_part = token_str[7:]  # убираем "Bearer "
        assert jwt_part.count('.') == 2, "JWT должен содержать 2 точки (xxx.yyy.zzz)"

    with allure.step("Валидация роли"):
        assert isinstance(role_id, int), "Роль должна быть целым числом"
        assert role_id > 0, "ID роли должен быть положительным"