import allure
import pytest
import random
import json
from pages.gm_page import *
from pages.task_page import *
from pages.cdr_page import *
from pages.td_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Добавление Заданий с фактическим ГМ в черновик Заявки")
@pytest.mark.parametrize("auth_token_ext", ["lkz_ext"], indirect=True)
@pytest.mark.parametrize("auth_token_base", ["lkz"], indirect=True)
def test_update1_cdr_with_task_lkz(auth_token_ext, auth_token_base, cargo_count=40):

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

    print(f"\n🔥 Всего создано Заданий: {len(task_ids)}")

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
            comment=f"Заявка для добавления Заданий"
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"

    time.sleep(2)

    # Обновление заявки
    with allure.step("Обновление заявки"):
        cdr_update = cdr_client.update_delivery_request(
            cdr_id=cdr_id,
            client_identifier=None,
            cargo_places=None,
            shipment_tasks=shipment_tasks_for_cdr,
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
        )

    time.sleep(2)

    # Проверка статуса Заявки
    with allure.step("Проверка деталки заявки"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "draft"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    time.sleep(2)

    # Проверка статусов Заданий
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

                    for field in ["weight", "volume", "quantity"]:
                        value = task_info.get(field)
                        assert value is not None and value > 0, \
                            f"{field} некорректный: {value}"

                    assert task_info.get("cost") is not None, \
                        f"cost отсутствует"

                    types = task_info.get("types")
                    assert isinstance(types, dict) and len(types) > 0, \
                        f"types пустой или не dict"

                    dep_point = task_info.get("departurePoint")
                    arr_point = task_info.get("arrivalPoint")

                    assert dep_point and dep_point.get("id") == departure_point_id, \
                        f"departurePoint.id != {departure_point_id}"

                    assert arr_point and arr_point.get("id") == arrival_point_id, \
                        f"arrivalPoint.id != {arrival_point_id}"

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


                    # бек присылает тип упаковки то как массив то как объект vz-10994


                    print(f"🔍 DEBUG: cdr_response type = {type(cdr_response)}")
                    print(f"🔍 DEBUG: cdr_response = {cdr_response}")
                    assert cdr_response, f"cdr_response пустой! Заявка CDR не была создана или не собралась"

                    # Если cdr_response список, берём первый элемент
                    if isinstance(cdr_response, list):
                        cdr_data = cdr_response[0]
                    else:
                        cdr_data = cdr_response

                    # # проверяем что задание привязалось к нашей заявке
                    assert cdr_data.get("id") in cdr_ids_in_task, \
                        f"Задание не привязано к созданной заявке {cdr_data.get('id')}"

                    assert task_info.get("isCargoPlacesEnabled") is True, \
                        f"isCargoPlacesEnabled != True"

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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Добавление Заданий с фактическим ГМ в принятую Заявку")
def test_update2_cdr_with_task_lkz(
        lkz_ext_token,
        lkz_token,
        lkp_token,
        cargo_count=30):

    gm_client = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

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

    task_client = ShipmentTaskClient(BASE_URL, lkz_token)

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
    with allure.step("Создание и публикация Заявки"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)

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
            comment=f"Заявка для добавления Заданий",
            producer_id=3486,
            rate=5500000,
            selecting_strategy="rate",
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"

    time.sleep(2)

    # Принятие заявки
    with allure.step("Принятие обязательств подрядчиком"):
        cdr_client_lkp = CargoDeliveryRequestClient(BASE_URL, lkp_token)

        take_response = cdr_client_lkp.take_cdr(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Принятие обязательств не удалось"
        print(f"✅ Обязательства приняты подрядчиком для заявки {cdr_id}")

    time.sleep(5)

    # Обновление заявки
    with allure.step("Обновление заявки"):
        cdr_update = cdr_client.update_active_delivery_request(
            cdr_id=cdr_id,
            shipment_tasks=shipment_tasks_for_cdr,
            route=[
                {"position": 1, "point": departure_point_id, "isLoadingWork": True, "isUnloadingWork": False},
                {"position": 2, "point": arrival_point_id, "isLoadingWork": False, "isUnloadingWork": True}
            ],
        )

    time.sleep(5)

    # Принятие changeRequests
    with allure.step("Принятие изменений"):

        # Получаем детали заявки
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "confirmed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Проверяем наличие массива changeRequests
        assert "changeRequests" in cdr_details, \
            f"В деталке заявки отсутствует поле 'changeRequests'. Ответ: {cdr_details}"

        change_requests = cdr_details.get("changeRequests", [])
        assert isinstance(change_requests, list), \
            f"Поле 'outgoingEntities' должно быть списком. Получено: {type(change_requests)}"

        # Собираем id всех чейндж реквестов
        change_request_ids = [cr.get("id") for cr in change_requests if "id" in cr]
        print(f"Найдено changeRequests: {len(change_request_ids)}")

        # Принимаем все чейндж реквесты
        responses = [
            cdr_client_lkp.process_change_request(cr_id, "accept")
            for cr_id in change_request_ids
        ]

        time.sleep(5)

    # # Проверка ГМ                                                                                                      ошибка статусов ГМ vz-10971
    # with allure.step("Проверка статусов грузомест"):
    #     gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)
    #
    #     # Проверяем случайные 10 грузомест
    #     failed_validations = []
    #     ids_to_check = (
    #         random.sample(cargo_place_ids, 10)
    #         if len(cargo_place_ids) > 10
    #         else cargo_place_ids
    #     )
    #
    #     for cargo_id in ids_to_check:
    #         with allure.step(f"Проверка грузоместа {cargo_id}"):
    #             try:
    #                 gm_info = gm_client_base.get_cargo_place_info(cargo_id)
    #                 assert gm_info, f"ГМ {cargo_id}: пустой ответ"
    #
    #                 assert gm_info.get("status") == "waiting_for_sending", \
    #                     f"ГМ {cargo_id}: Ожидался статус 'waiting_for_sending', получен: '{gm_info.get('status')}'"
    #
    #                 bar_code = gm_info.get("barCode")
    #                 assert bar_code and len(bar_code) > 0, \
    #                     f"ГМ {cargo_id}: barCode пустое"
    #
    #                 external_id = gm_info.get("externalId")
    #                 assert external_id and len(external_id) > 0, \
    #                     f"ГМ {cargo_id}: externalId пустое"
    #
    #                 is_planned = gm_info.get("isPlanned")
    #                 assert is_planned == False, \
    #                     f"ГМ {cargo_id}: Ожидалось isPlanned=False, получено: {is_planned}"
    #
    #                 weight = gm_info.get("weight")
    #                 assert weight is not None and weight > 0, \
    #                     f"ГМ {cargo_id}: weight пустое или некорректное"
    #
    #                 volume = gm_info.get("volume")
    #                 assert volume is not None and volume > 0, \
    #                     f"ГМ {cargo_id}: volume пустое или некорректное"
    #
    #                 # Проверка что массив cargoDeliveryRequests содержит ID заявки
    #                 cargo_delivery_requests = gm_info.get("cargoDeliveryRequests", [])
    #                 cdr_ids_in_gm = [cdr["id"] for cdr in cargo_delivery_requests if "id" in cdr]
    #                 assert cdr_id in cdr_ids_in_gm, \
    #                     f"ГМ {cargo_id}: Заявка {cdr_id} не найдена в грузоместе. Найдено: {cdr_ids_in_gm}"
    #
    #                 print(f"✅ ГМ {cargo_id}: все проверки пройдены")
    #
    #             except AssertionError as e:
    #                 failed_validations.append(f"ГМ {cargo_id}: {str(e)}")
    #                 print(f"❌ ГМ {cargo_id}: {str(e)}")
    #
    #             except Exception as e:
    #                 failed_validations.append(f"ГМ {cargo_id}: Ошибка запроса - {str(e)}")
    #                 print(f"❌ ГМ {cargo_id}: Ошибка запроса - {str(e)}")
    #
    #             time.sleep(1)
    #
    #     assert not failed_validations, (
    #             "Найдены ошибки в грузоместах:\n" + "\n".join(failed_validations)
    #     )

    # Проверка статуса Заявки
    with allure.step("Проверка деталки заявки"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "confirmed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    time.sleep(2)

    # Проверка статусов Заданий
    with allure.step("Проверка Заданий"):
        task_client_base = ShipmentTaskClient(BASE_URL, lkz_token)

        failed_validations = []

        # Берем случайные 10 Заданий
        ids_to_check = (
            random.sample(task_ids, 10)
            if len(task_ids) > 10
            else task_ids
        )

        for task_id in ids_to_check:
            with allure.step(f"Проверка Задания {task_id}"):
                try:
                    task_info = task_client_base.get_shipment_task_info(task_id)
                    assert task_info, f"Задание {task_id}: пустой ответ"

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

                    for field in ["weight", "volume", "quantity"]:
                        value = task_info.get(field)
                        assert value is not None and value > 0, \
                            f"{field} некорректный: {value}"

                    assert task_info.get("cost") is not None, \
                        f"cost отсутствует"

                    types = task_info.get("types")
                    assert isinstance(types, dict) and len(types) > 0, \
                        f"types пустой или не dict"

                    dep_point = task_info.get("departurePoint")
                    arr_point = task_info.get("arrivalPoint")

                    assert dep_point and dep_point.get("id") == departure_point_id, \
                        f"departurePoint.id != {departure_point_id}"

                    assert arr_point and arr_point.get("id") == arrival_point_id, \
                        f"arrivalPoint.id != {arrival_point_id}"

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


                    # бек присылает тип упаковки то как массив то как объект vz-10994


                    print(f"🔍 DEBUG: cdr_response type = {type(cdr_response)}")
                    print(f"🔍 DEBUG: cdr_response = {cdr_response}")
                    assert cdr_response, f"cdr_response пустой! Заявка CDR не была создана или не собралась"

                    # Если cdr_response список, берём первый элемент
                    if isinstance(cdr_response, list):
                        cdr_data = cdr_response[0]
                    else:
                        cdr_data = cdr_response

                    # # проверяем что задание привязалось к нашей заявке
                    assert cdr_data.get("id") in cdr_ids_in_task, \
                        f"Задание не привязано к созданной Заявке {cdr_data.get('id')}"

                    assert task_info.get("isCargoPlacesEnabled") is True, \
                        f"isCargoPlacesEnabled != True"

                    print(f"✅ Задание {task_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"Задание {task_id}: {str(e)}")
                    print(f"❌ Задание {task_id}: {str(e)}")

                except Exception as e:
                    failed_validations.append(f"Задание {task_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ Задание {task_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        assert not failed_validations, (
                "Найдены ошибки в Заданиях:\n" + "\n".join(failed_validations)
        )


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Добавление Заданий с фактическим ГМ в исполняемую Заявку")
def test_update3_cdr_with_task_lkz(
        lkz_ext_token,
        lkz_token,
        lkp_token,
        cargo_count=70):

    gm_client = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

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

    task_client = ShipmentTaskClient(BASE_URL, lkz_token)

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
    with allure.step("Создание и публикация Заявки"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)

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
            comment=f"Заявка для добавления Заданий",
            producer_id=3486,
            rate=5500000,
            selecting_strategy="rate",
            to_start_at_from=(datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"

    time.sleep(2)

    # Принятие заявки
    with allure.step("Принятие обязательств подрядчиком"):
        cdr_client_lkp = CargoDeliveryRequestClient(BASE_URL, lkp_token)

        take_response = cdr_client_lkp.take_cdr(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Принятие обязательств не удалось"
        print(f"✅ Обязательства приняты подрядчиком для заявки {cdr_id}")

    time.sleep(3)

    # Создание рейса
    with allure.step("ЧАСТЬ 4: Создание рейса"):
        td_client_lkp = TruckDeliveryClient(BASE_URL, lkp_token)
        trip_response = td_client_lkp.create_trip(
            cdr_id=[cdr_id],
            trip_type="truck",
            producer_id=3486
        )

        # Извлекаем id рейса
        td_id = trip_response.get("id")
        assert td_id, f"Нет id рейса в ответе: {trip_response}"

        print(f"✅ Рейс создан: ID={td_id}")

    time.sleep(2)

    # Названичение водителя/ТС
    with allure.step("Назначение водителя и ТС на рейс"):
        appoint_response = td_client_lkp.appoint_transport(
            td_id=td_id,
            driver_id=6091,
            vehicle_id=10571
        )

        assert appoint_response == [], \
            f"Ожидался пустой массив, получено: {appoint_response}"

        print(f"✅ Водитель и ТС назначены на рейс {td_id}")

    time.sleep(3)

    # Начало исполнения рейса
    with allure.step("Старт исполнения рейса"):
        start_response = td_client_lkp.start_td(td_id=td_id)

        # Attach ответа
        with allure.step("Ответ API (start trip)"):
            allure.attach(
                json.dumps(start_response, indent=2, ensure_ascii=False),
                name="Ответ API (start trip)",
                attachment_type=allure.attachment_type.JSON
            )

        print(f"✅ Рейс {td_id} запущен в исполнение")

    time.sleep(3)

    # Проверка Заявки
    with allure.step("Проверка деталки Заявки"):
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "execution"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    # Проверка рейса
    with allure.step("Проверка деталки рейса"):
        td_details = td_client_lkp.get_td_details(td_id)

        expected_td_status = "execution"
        actual_td_status = td_details.get("status")

        assert actual_td_status == expected_td_status, \
            f"Ожидался статус рейса '{expected_td_status}', получен: '{actual_td_status}'"

        print(f"✅ Статус рейса: {actual_td_status}")

    time.sleep(3)

    # Обновление заявки
    with allure.step("Обновление заявки"):
        cdr_update = cdr_client.update_active_delivery_request(
            cdr_id=cdr_id,
            shipment_tasks=shipment_tasks_for_cdr,
            route=[
                {"position": 1, "point": departure_point_id, "isLoadingWork": True, "isUnloadingWork": False},
                {"position": 2, "point": arrival_point_id, "isLoadingWork": False, "isUnloadingWork": True}
            ],
        )

    time.sleep(3)

    # Принятие changeRequests
    with allure.step("Принятие изменений"):

        # Получаем детали заявки
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "execution"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Проверяем наличие массива changeRequests
        assert "changeRequests" in cdr_details, \
            f"В деталке заявки отсутствует поле 'changeRequests'. Ответ: {cdr_details}"

        change_requests = cdr_details.get("changeRequests", [])
        assert isinstance(change_requests, list), \
            f"Поле 'outgoingEntities' должно быть списком. Получено: {type(change_requests)}"

        # Собираем id всех чейндж реквестов
        change_request_ids = [cr.get("id") for cr in change_requests if "id" in cr]
        print(f"Найдено changeRequests: {len(change_request_ids)}")

        # Принимаем все чейндж реквесты
        responses = [
            cdr_client_lkp.process_change_request(cr_id, "accept")
            for cr_id in change_request_ids
        ]

        time.sleep(5)

    # Проверка статуса Заявки
    with allure.step("Проверка деталки заявки"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "execution"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    time.sleep(2)

    # Проверка статусов Заданий
    with allure.step("Проверка Заданий"):
        task_client_base = ShipmentTaskClient(BASE_URL, lkz_token)

        failed_validations = []

        # Берем случайные 10 Заданий
        ids_to_check = (
            random.sample(task_ids, 10)
            if len(task_ids) > 10
            else task_ids
        )

        for task_id in ids_to_check:
            with allure.step(f"Проверка Задания {task_id}"):
                try:
                    task_info = task_client_base.get_shipment_task_info(task_id)
                    assert task_info, f"Задание {task_id}: пустой ответ"

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

                    for field in ["weight", "volume", "quantity"]:
                        value = task_info.get(field)
                        assert value is not None and value > 0, \
                            f"{field} некорректный: {value}"

                    assert task_info.get("cost") is not None, \
                        f"cost отсутствует"

                    types = task_info.get("types")
                    assert isinstance(types, dict) and len(types) > 0, \
                        f"types пустой или не dict"

                    dep_point = task_info.get("departurePoint")
                    arr_point = task_info.get("arrivalPoint")

                    assert dep_point and dep_point.get("id") == departure_point_id, \
                        f"departurePoint.id != {departure_point_id}"

                    assert arr_point and arr_point.get("id") == arrival_point_id, \
                        f"arrivalPoint.id != {arrival_point_id}"

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


                    # бек присылает тип упаковки то как массив то как объект                                            vz-10994


                    # Если cdr_response список, берём первый элемент
                    if isinstance(cdr_response, list):
                        cdr_data = cdr_response[0]
                    else:
                        cdr_data = cdr_response

                    # # проверяем что задание привязалось к нашей заявке
                    assert cdr_data.get("id") in cdr_ids_in_task, \
                        f"Задание не привязано к созданной Заявке {cdr_data.get('id')}"

                    assert task_info.get("isCargoPlacesEnabled") is True, \
                        f"isCargoPlacesEnabled != True"

                    print(f"✅ Задание {task_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"Задание {task_id}: {str(e)}")
                    print(f"❌ Задание {task_id}: {str(e)}")

                except Exception as e:
                    failed_validations.append(f"Задание {task_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ Задание {task_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        assert not failed_validations, (
                "Найдены ошибки в Заданиях:\n" + "\n".join(failed_validations)
        )





































