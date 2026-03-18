import allure
import pytest
import json
from pages.cargo_create_or_update_list_page import CargoPlaceCreateOrUpdateListClient
from config.settings import BASE_URL


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание и выполнение Заявки с указанным количеством грузомест")
@pytest.mark.parametrize("auth_token", ["lkz"], indirect=True)
def test_create_trip_with_cargo_places(auth_token, cargo_count):
    """
    Тест создания Заявки с динамическим количеством грузомест

    Args:
        auth_token: Токен авторизации (из фикстуры conftest)
        cargo_count: Количество грузомест (из аргумента командной строки --cargo-count)
    """
    client = CargoPlaceCreateOrUpdateListClient(BASE_URL, auth_token)

    # Генерация грузомест с использованием cargo_count из conftest
    with allure.step(f"Генерация {cargo_count} грузомест"):
        cargo_list = client.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext"  # можно тоже вынести в параметризацию при необходимости
        )

    # Создание/обновление грузомест
    with allure.step("Отправка запроса на создание/обновление грузомест"):
        response = client.create_or_update_cargo_places_list(cargo_list)

    # Проверка ответа
    with allure.step("Проверка структуры ответа"):
        assert response.get("status") == "ok", f"Ожидался 'ok', получен: {response.get('status')}"
        data = response.get("data", [])
        assert len(data) == cargo_count, f"Ожидалось {cargo_count} ГМ, получено: {len(data)}"

    # Attach логов
    with allure.step("Детали запроса и ответа"):
        allure.attach(
            json.dumps({"request": {"data": cargo_list}}, indent=2, ensure_ascii=False),
            name="Запрос (create-or-update-list)",
            attachment_type=allure.attachment_type.JSON
        )
        allure.attach(
            json.dumps(response, indent=2, ensure_ascii=False),
            name="Ответ API (create-or-update-list)",
            attachment_type=allure.attachment_type.JSON
        )

    print(f"\n✅ Успешно создано {cargo_count} грузомест")