import allure
import pytest
import random
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
    with allure.step("Создание черновика заявки"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, auth_token_base)

        cdr_response = cdr_client.create_delivery_request(
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
            comment=f"черновик заявки с {cargo_count} ГМ",
            shipment_tasks=shipment_tasks_for_cdr
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"

    time.sleep(2)

    # Проверяем случайные 10 Заданий
    with allure.step("Проверка заданий"):
        task_client_base = ShipmentTaskClient(BASE_URL, auth_token_base)

        failed_validations = []

        # Берем случайные 10 заданий
        ids_to_check = (
            random.sample(task_ids, 10)
            if len(task_ids) > 10
            else task_ids
        )

        for task_id in ids_to_check:
            with allure.step(f"Проверка задания {task_id}"):
                try:
                    task_info = task_client_base.get_shipment_task_info(task_id)
                    assert task_info, f"Задание {task_id}: пустой ответ"

                    # -------------------------------
                    # 🔹 БАЗОВЫЕ ПОЛЯ
                    # -------------------------------
                    assert task_info.get("id") == task_id, \
                        f"id не совпадает: {task_info.get('id')} != {task_id}"

                    assert task_info.get("status") == "in_progress", \
                        f"status != in_progress (получен {task_info.get('status')})"

                    assert task_info.get("shipBy") == "vezubr", \
                        f"shipBy != vezubr"

                    assert task_info.get("number"), \
                        f"number пустой"

                    assert task_info.get("createdAt"), \
                        f"createdAt отсутствует"

                    # -------------------------------
                    # 🔹 ЧИСЛОВЫЕ ПОЛЯ
                    # -------------------------------
                    for field in ["weight", "volume", "quantity"]:
                        value = task_info.get(field)
                        assert value is not None and value > 0, \
                            f"{field} некорректный: {value}"

                    # cost может быть 0 — это норм
                    assert task_info.get("cost") is not None, \
                        f"cost отсутствует"

                    # -------------------------------
                    # 🔹 TYPES
                    # -------------------------------
                    types = task_info.get("types")
                    assert isinstance(types, dict) and len(types) > 0, \
                        f"types пустой или не dict"

                    # -------------------------------
                    # 🔹 ТОЧКИ
                    # -------------------------------
                    dep_point = task_info.get("departurePoint")
                    arr_point = task_info.get("arrivalPoint")

                    assert dep_point and dep_point.get("id") == departure_point_id, \
                        f"departurePoint.id != {departure_point_id}"

                    assert arr_point and arr_point.get("id") == arrival_point_id, \
                        f"arrivalPoint.id != {arrival_point_id}"

                    # -------------------------------
                    # 🔹 ГРУЗОМЕСТА
                    # -------------------------------
                    cargo_places = task_info.get("cargoPlaces", [])
                    assert len(cargo_places) > 0, \
                        f"нет cargoPlaces"

                    assert len(cargo_places) <= 20, \
                        f"больше 20 ГМ: {len(cargo_places)}"

                    cargo_ids_in_task = []
                    for cp in cargo_places:
                        assert "id" in cp, f"у ГМ нет id"
                        assert "externalId" in cp and cp["externalId"], \
                            f"у ГМ {cp.get('id')} пустой externalId"

                        cargo_ids_in_task.append(cp["id"])

                    # все ГМ должны быть из нашего списка
                    unexpected_ids = [
                        cid for cid in cargo_ids_in_task if cid not in cargo_place_ids
                    ]
                    assert not unexpected_ids, \
                        f"найдены чужие ГМ: {unexpected_ids}"

                    # -------------------------------
                    # 🔹 СВЯЗЬ С ЗАЯВКОЙ (CDR)
                    # -------------------------------
                    cdr_list = task_info.get("cargoDeliveryRequests", [])
                    assert len(cdr_list) > 0, \
                        f"нет cargoDeliveryRequests"

                    cdr_ids_in_task = []

                    for cdr in cdr_list:
                        inner = cdr.get("cargoDeliveryRequest")
                        assert inner, f"нет cargoDeliveryRequest внутри"

                        assert "id" in inner, f"нет id у CDR"
                        assert "requestNr" in inner, f"нет requestNr у CDR"

                        cdr_ids_in_task.append(inner["id"])

                    # проверяем что задание привязалось к нашей заявке
                    assert cdr_response.get("id") in cdr_ids_in_task, \
                        f"задание не привязано к созданной заявке {cdr_response.get('id')}"

                    # -------------------------------
                    # 🔹 SUMMARY
                    # -------------------------------
                    summary = task_info.get("cargoPlacesSummary")
                    assert summary, "нет cargoPlacesSummary"

                    for key in [
                        "waitingForSendingCount",
                        "sentCount",
                        "notSentCount",
                        "receivedCount"
                    ]:
                        assert key in summary, f"нет {key} в summary"

                    total_summary = sum(summary.values())

                    assert total_summary == len(cargo_places), \
                        f"summary ({total_summary}) != количеству ГМ ({len(cargo_places)})"

                    # -------------------------------
                    # 🔹 ФЛАГИ
                    # -------------------------------
                    assert task_info.get("isCargoPlacesEnabled") is True, \
                        f"isCargoPlacesEnabled != True"

                    # -------------------------------
                    print(f"✅ Задание {task_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"Задание {task_id}: {str(e)}")
                    print(f"❌ Задание {task_id}: {str(e)}")

                except Exception as e:
                    failed_validations.append(f"Задание {task_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ Задание {task_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        assert not failed_validations, (
                "Найдены ошибки в заданиях:\n" + "\n".join(failed_validations)
        )

    with allure.step("Проверка грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, auth_token_base)

        # Проверяем случайные 10 грузомест
        failed_validations = []
        ids_to_check = (
            random.sample(cargo_place_ids, 10)
            if len(cargo_place_ids) > 10
            else cargo_place_ids
        )

        for cargo_id in ids_to_check:
            with allure.step(f"Проверка грузоместа {cargo_id}"):
                try:
                    gm_info = gm_client_base.get_cargo_place_info(cargo_id)
                    assert gm_info, f"ГМ {cargo_id}: пустой ответ"

                    assert gm_info.get("status") == "new", \
                        f"ГМ {cargo_id}: Ожидался статус 'new', получен: '{gm_info.get('status')}'"

                    bar_code = gm_info.get("barCode")
                    assert bar_code and len(bar_code) > 0, \
                        f"ГМ {cargo_id}: barCode пустое"

                    external_id = gm_info.get("externalId")
                    assert external_id and len(external_id) > 0, \
                        f"ГМ {cargo_id}: externalId пустое"

                    is_planned = gm_info.get("isPlanned")
                    assert is_planned == False, \
                        f"ГМ {cargo_id}: Ожидалось isPlanned=False, получено: {is_planned}"

                    weight = gm_info.get("weight")
                    assert weight is not None and weight > 0, \
                        f"ГМ {cargo_id}: weight пустое или некорректное"

                    volume = gm_info.get("volume")
                    assert volume is not None and volume > 0, \
                        f"ГМ {cargo_id}: volume пустое или некорректное"

                    # Проверка что массив cargoDeliveryRequests содержит ID заявки
                    cargo_delivery_requests = gm_info.get("cargoDeliveryRequests", [])
                    cdr_ids_in_gm = [cdr["id"] for cdr in cargo_delivery_requests if "id" in cdr]
                    assert cdr_id in cdr_ids_in_gm, \
                        f"ГМ {cargo_id}: Заявка {cdr_id} не найдена в грузоместе. Найдено: {cdr_ids_in_gm}"

                    print(f"✅ ГМ {cargo_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"ГМ {cargo_id}: {str(e)}")
                    print(f"❌ ГМ {cargo_id}: {str(e)}")

                except Exception as e:
                    failed_validations.append(f"ГМ {cargo_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ ГМ {cargo_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        assert not failed_validations, (
                "Найдены ошибки в грузоместах:\n" + "\n".join(failed_validations)
        )

    # Проверка статуса Заявки
    with allure.step("Проверка деталки заявки"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "draft"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")










