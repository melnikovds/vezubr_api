import allure
import pytest
import json
from pages.gm_page import *
from pages.task_page import *
from pages.cdr_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание Заявки с Заданиями с фактическим ГМ")
@pytest.mark.parametrize("auth_token_ext", ["lkz_ext"], indirect=True)
@pytest.mark.parametrize("auth_token_base", ["lkz"], indirect=True)
def test_create_cdr_with_task_lkz(auth_token_ext, auth_token_base, cargo_count=110):

    gm_client = CargoPlaceClient(EXTERNAL_URL, auth_token_ext)

    # Генерация грузомест
    with allure.step(f"Генерация {cargo_count} грузомест"):
        cargo_list = gm_client.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            departure_external_id='AUTO 003',
            delivery_external_id='AUTO 004',
            use_predefined_addresses=False
        )

    # Создание грузомест
    with allure.step(f"Создание {cargo_count} грузомест"):
        responses = gm_client.create_cargo_places_batch(
            cargo_places=cargo_list,
            batch_size=100
        )

    # Сбор всех ID грузомест
    with allure.step("Сбор ID созданных грузомест"):
        cargo_place_ids = []
        for batch_idx, response in enumerate(responses, 1):
            batch_data = response.get("data", [])
            batch_ids = [item["id"] for item in batch_data if "id" in item]
            cargo_place_ids.extend(batch_ids)
            print(f"Батч {batch_idx}: собрано {len(batch_ids)} ID")

        print(f"\n✅ Всего собрано {len(cargo_place_ids)} ID грузомест")

    task_client = ShipmentTaskClient(BASE_URL, auth_token_base)

    def chunk_list(data, size):
        for i in range(0, len(data), size):
            yield data[i:i + size]

    task_ids = []

    with allure.step("Создание заданий (максимум 20 ГМ в каждом)"):
        for idx, cargo_chunk in enumerate(chunk_list(cargo_place_ids, 20), 1):
            print(f"➡️ Создаем задание {idx} с {len(cargo_chunk)} ГМ")

            task_id = task_client.create_shipment_task(
                cargo_place_ids=cargo_chunk,
                dep_point=19104,
                arr_point=19105
            )

            task_ids.append(task_id)

            time.sleep(1)

    print(f"\n🔥 Всего создано заданий: {len(task_ids)}")

    expected_tasks = (len(cargo_place_ids) + 19) // 20
    assert len(task_ids) == expected_tasks



