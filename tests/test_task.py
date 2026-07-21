import allure
import pytest
import json
from pages.gm_page import *
from pages.task_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("Задание")
@allure.description("Создание задания с фактическими грузоместами")
@pytest.mark.parametrize("cargo_count", [10])
def test_shipment_task_create_with_gm_lkz(lkz_token, lkz_ext_token, cargo_count):

    client = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

    # генерация параметров грузомест
    with allure.step(f"Генерация {cargo_count} грузомест"):
        cargo_list = client.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            use_predefined_addresses=False,
            departure_external_id="AUTO 005",
            delivery_external_id="AUTO 006"
        )

    # пакетное создание грузомест
    with allure.step("Отправка запроса на создание грузомест"):
        with allure.step(f"Создание {cargo_count} грузомест (батчами по 100)"):
            responses = client.create_cargo_places_batch(
                cargo_places=cargo_list,
                batch_size=100  # максимум 100 за запрос
            )

    # сбор id грузомест
    with allure.step("Сбор ID созданных грузомест"):
        cargo_place_ids = []

        for batch_idx, response in enumerate(responses, 1):
            batch_data = response.get("data", [])
            batch_ids = [item["id"] for item in batch_data if "id" in item]
            cargo_place_ids.extend(batch_ids)

        print(f"\n✅ Всего собрано {len(cargo_place_ids)} ID грузомест")

    # создание задания
    with allure.step("Создание задания с грузоместами"):
        task_client = ShipmentTaskClient(BASE_URL, lkz_token)

        task_id = task_client.create_shipment_task(cargo_place_ids)

        assert task_id is not None

    with allure.step("Получение деталки задания"):
        task_data = task_client.get_shipment_task_info(task_id)

    with allure.step("Проверка статуса задания"):
        assert task_data["status"] == "created", \
            f"Ожидался статус 'created', получен {task_data['status']}"

    with allure.step("Проверка, что все грузоместа прикрепились"):
        response_ids = [gm["id"] for gm in task_data.get("cargoPlaces", [])]

        assert set(response_ids) == set(cargo_place_ids), \
            f"""
            Несоответствие грузомест:
            Ожидались: {cargo_place_ids}
            Получены: {response_ids}
            """

    with allure.step("Проверка количества грузомест"):
        assert len(task_data.get("cargoPlaces", [])) == len(cargo_place_ids)

    assert isinstance(task_data.get("types"), list)


