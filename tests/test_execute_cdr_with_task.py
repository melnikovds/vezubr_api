import allure
import pytest
import json
from pages.gm_page import *
from pages.task_page import *
from pages.cdr_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Исполнение Заявки с Заданиями с фактическим ГМ")
@pytest.mark.parametrize("auth_token_ext", ["lkz_ext"], indirect=True)
@pytest.mark.parametrize("auth_token_base", ["lkz"], indirect=True)
def test_execute_cdr_with_task_lkz(auth_token_ext, auth_token_base, cargo_count=110):

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

    # Создание Заданий
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


    # Преобразование ID в формат для CDR
    with allure.step("Формирование shipmentTasks для заявки"):
        departure_point_id = 19104
        arrival_point_id = 19105

        shipment_tasks_for_cdr = [
            {
                "id": task_id,
                "arrivalPoint": arrival_point_id,
                "departurePoint": departure_point_id
            }
            for task_id in task_ids
        ]

        print(f"📋 Сформировано {len(shipment_tasks_for_cdr)} cargoPlaces для CDR")

    # Создание Заявки
    with allure.step("Создание и публикация заявки"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, auth_token_base)

        cdr_response = cdr_client.create_and_publish_delivery_request(
            delivery_type="auto",
            delivery_sub_type="ftl",
            body_types=[3, 4, 7, 8],
            vehicle_type_id=1,
            order_type=1,
            point_change_type=2,
            route=[
                {
                    "requiredArriveAtFrom": None,
                    "requiredArriveAtTill": None,
                    "position": 1,
                    "point": departure_point_id,
                    "isLoadingWork": True,
                    "isUnloadingWork": False
                },
                {
                    "requiredArriveAtFrom": None,
                    "requiredArriveAtTill": None,
                    "position": 2,
                    "point": arrival_point_id,
                    "isLoadingWork": False,
                    "isUnloadingWork": True
                }
            ],
            comment=f"Заявка с Заданиями и {cargo_count} ГМ",
            client_identifier=f"CDR-WITH-TASKS-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
            producer_id=3486,
            rate=450000,
            selecting_strategy="rate",
            shipment_tasks=shipment_tasks_for_cdr
        )





