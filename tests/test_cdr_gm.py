import allure
import pytest
import json
from pages.cargo_create_or_update_list_page import *
from pages.cdr_create_and_publish_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание Заявки с указанным количеством грузомест (скорее всего превысят параметры ТС по весу и объёму)")
@pytest.mark.parametrize("auth_token_ext", ["lkz_ext"], indirect=True)
@pytest.mark.parametrize("auth_token_base", ["lkz"], indirect=True)
def test_create_cdr_with_cargo_places_lkz(auth_token_ext, auth_token_base, cargo_count):
    """
    Тест создания Заявки с динамическим количеством грузомест

    Args:
        auth_token_ext: Токен внешней системы для создания грузомест
        auth_token_base: Токен внутренней системы для создания заявки
        cargo_count: Количество грузомест (из аргумента командной строки --cargo-count)
    """
    client = CargoPlaceCreateOrUpdateListClient(EXTERNAL_URL, auth_token_ext)

    # Генерация грузомест
    with allure.step(f"Генерация {cargo_count} грузомест"):
        cargo_list = client.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            departure_external_id='AUTO 003',
            delivery_external_id='AUTO 004',
            use_predefined_addresses=False
        )

    # Создание грузомест
    with allure.step(f"Создание {cargo_count} грузомест"):
        responses = client.create_cargo_places_batch(
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

    # Преобразование ID в формат для CDR
    with allure.step("Формирование cargoPlaces для заявки"):
        departure_point_id = 19104
        arrival_point_id = 19105

        cargo_places_for_cdr = [
            {
                "id": cargo_id,
                "arrivalPoint": arrival_point_id,
                "departurePoint": departure_point_id
            }
            for cargo_id in cargo_place_ids
        ]

        print(f"📋 Сформировано {len(cargo_places_for_cdr)} cargoPlaces для CDR")

    # Создание Заявки (CDR)
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
            comment=f"Тестовая заявка с {cargo_count} ГМ",
            producer_id=3486,
            rate=100000,
            selecting_strategy="rate",
            cargo_places=cargo_places_for_cdr
        )

    # Проверка ответа
    with allure.step("Проверка ответа"):
        assert cdr_response.get("id") is not None, "CDR не создан: отсутствует ID"
        assert cdr_response.get("requestNr") is not None, "CDR не создан: отсутствует requestNr"
        print(f"✅ Заявка создана: ID={cdr_response.get('id')}, requestNr={cdr_response.get('requestNr')}")

    # Attach логов
    with allure.step("Детали запроса и ответа"):
        allure.attach(
            json.dumps({"total_cargo_places": cargo_count, "cargo_place_ids": cargo_place_ids[:10]}, indent=2,
                       ensure_ascii=False),
            name="Статистика грузомест",
            attachment_type=allure.attachment_type.JSON
        )
        allure.attach(
            json.dumps(cargo_places_for_cdr[:5], indent=2, ensure_ascii=False),
            name="cargoPlaces (первые 5)",
            attachment_type=allure.attachment_type.JSON
        )
        allure.attach(
            json.dumps(cdr_response, indent=2, ensure_ascii=False),
            name="Ответ API (CDR)",
            attachment_type=allure.attachment_type.JSON
        )

    print(f"\n✅ Успешно создано {cargo_count} грузомест и заявка CDR")






# @allure.story("Smoke test")
# @allure.feature("CDR")
# @allure.description("Создание и выполнение Заявки с указанным количеством грузомест")
# @pytest.mark.parametrize("auth_token", ["lkz_ext"], indirect=True)
# def test_create_and_execute_cdr_with_cargo_places_lkz(auth_token, cargo_count):
