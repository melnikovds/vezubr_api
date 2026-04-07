import allure
import pytest
import json
import random
from datetime import datetime, timedelta, timezone
from pages.gm_page import *
from pages.cdr_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Выполнение Заявки с грузоместами")
@pytest.mark.parametrize("cargo_count", [200])
def test_execute_cdr_with_cargo_places_lkz(
    lkz_ext_token,
    lkz_token,
    lkp_token,
    cargo_count
):
    with allure.step("ЧАСТЬ 1: Создание грузомест"):
        gm_client_ext = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

        cargo_list = gm_client_ext.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            use_predefined_addresses=False,
            departure_external_id='AUTO 005',
            delivery_external_id='AUTO 006'
        )

        responses = gm_client_ext.create_cargo_places_batch(cargo_list, batch_size=100)
        assert responses, "Не получен ответ при создании грузомест"

        cargo_place_ids = []
        for response in responses:
            assert "data" in response, f"Нет поля data: {response}"
            batch_ids = [item["id"] for item in response.get("data", []) if "id" in item]
            assert batch_ids, f"Нет id в ответе: {response}"
            cargo_place_ids.extend(batch_ids)

        print(f"✅ Создано {len(cargo_place_ids)} грузомест")

    with allure.step("ЧАСТЬ 2: Создание заявки"):
        cargo_places_for_cdr = [
            {"id": cid, "arrivalPoint": 27032, "departurePoint": 27030}
            for cid in cargo_place_ids
        ]

        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)
        cdr_response = cdr_client.create_and_publish_delivery_request(
            delivery_type="auto",
            delivery_sub_type="ftl",
            body_types=[3, 4, 7, 8],
            vehicle_type_id=1,
            order_type=1,
            point_change_type=2,
            route=[
                {"position": 1, "point": 27030, "isLoadingWork": True, "isUnloadingWork": False},
                {"position": 2, "point": 27032, "isLoadingWork": False, "isUnloadingWork": True}
            ],
            comment=f"Тестовая заявка с {cargo_count} ГМ",
            client_identifier=f"CDR-EXECUTION-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
            producer_id=3486,
            rate=100000,
            selecting_strategy="rate",
            cargo_places=cargo_places_for_cdr
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"
        print(f"✅ Заявка создана: ID={cdr_id}")

    with allure.step("ЧАСТЬ 3: Принятие обязательств подрядчиком"):
        cdr_client_lkp = CargoDeliveryRequestClient(BASE_URL, lkp_token)

        take_response = cdr_client_lkp.take_cdr(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Принятие обязательств не удалось"
        print(f"✅ Обязательства приняты подрядчиком для заявки {cdr_id}")

        # Attach ответа
        with allure.step("Ответ API (take)"):
            allure.attach(
                json.dumps(take_response, indent=2, ensure_ascii=False),
                name="Ответ API (take CDR)",
                attachment_type=allure.attachment_type.JSON
            )

    with allure.step("ЧАСТЬ 4: Проверка статуса заявки"):
        # Небольшая задержка для репликации данных
        print("⏳ Ожидание 2 секунды для обновления статуса...")
        time.sleep(2)
        # Получаем детали заявки
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "confirmed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Attach деталей
        with allure.step("Детали заявки"):
            allure.attach(
                json.dumps({
                    "cdr_id": cdr_id,
                    "status": actual_status,
                    "requestNr": cdr_details.get("requestNr")
                }, indent=2, ensure_ascii=False),
                name="Статус заявки после принятия",
                attachment_type=allure.attachment_type.JSON
            )

    with allure.step("ЧАСТЬ 5: Проверка статусов грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)

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

                    assert gm_info.get("status") == "waiting_for_sending", \
                        f"ГМ {cargo_id}: Ожидался статус 'waiting_for_sending', получен: '{gm_info.get('status')}'"

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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Выполнение Заявки с грузоместами")
@pytest.mark.parametrize("cargo_count", [10])
def test_execute2_cdr_with_cargo_places_lkz(
    lkz_ext_token,
    lkz_token,
    lkp_token,
    cargo_count
):
    with allure.step("ЧАСТЬ 1: Создание грузомест"):
        gm_client_ext = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

        cargo_list = gm_client_ext.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            use_predefined_addresses=False,
            departure_external_id='AUTO 005',
            delivery_external_id='AUTO 006'
        )

        responses = gm_client_ext.create_cargo_places_batch(cargo_list, batch_size=100)
        assert responses, "Не получен ответ при создании грузомест"

        cargo_place_ids = []
        for response in responses:
            assert "data" in response, f"Нет поля data: {response}"
            batch_ids = [item["id"] for item in response.get("data", []) if "id" in item]
            assert batch_ids, f"Нет id в ответе: {response}"
            cargo_place_ids.extend(batch_ids)

        print(f"✅ Создано {len(cargo_place_ids)} грузомест")

    with allure.step("ЧАСТЬ 2: Создание заявки"):
        cargo_places_for_cdr = [
            {"id": cid, "arrivalPoint": 27032, "departurePoint": 27030}
            for cid in cargo_place_ids
        ]

        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)
        cdr_response = cdr_client.create_and_publish_delivery_request(
            delivery_type="auto",
            delivery_sub_type="ftl",
            body_types=[3, 4, 7, 8],
            vehicle_type_id=1,
            order_type=1,
            point_change_type=2,
            route=[
                {"position": 1, "point": 27030, "isLoadingWork": True, "isUnloadingWork": False},
                {"position": 2, "point": 27032, "isLoadingWork": False, "isUnloadingWork": True}
            ],
            comment=f"Тестовая заявка с {cargo_count} ГМ",
            client_identifier=f"CDR-EXECUTION-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
            producer_id=3486,
            rate=100000,
            selecting_strategy="rate",
            cargo_places=cargo_places_for_cdr
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"
        print(f"✅ Заявка создана: ID={cdr_id}")

    with allure.step("ЧАСТЬ 3: Принятие обязательств подрядчиком"):
        cdr_client_lkp = CargoDeliveryRequestClient(BASE_URL, lkp_token)

        take_response = cdr_client_lkp.take_cdr(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Принятие обязательств не удалось"
        print(f"✅ Обязательства приняты подрядчиком для заявки {cdr_id}")

        # Attach ответа
        with allure.step("Ответ API (take)"):
            allure.attach(
                json.dumps(take_response, indent=2, ensure_ascii=False),
                name="Ответ API (take CDR)",
                attachment_type=allure.attachment_type.JSON
            )

    time.sleep(1)

    with allure.step("ЧАСТЬ 4: Создание рейса"):
        trip_response = cdr_client_lkp.create_trip(
            cdr_id=[cdr_id],
            trip_type="truck",
            producer_id=3486
        )

        # Извлекаем id рейса
        td_id = trip_response.get("id")
        assert td_id, f"Нет id рейса в ответе: {trip_response}"

        print(f"✅ Рейс создан: ID={td_id}")

    time.sleep(1)

    with allure.step("ЧАСТЬ 5: Назначение водителя и ТС на рейс"):
        appoint_response = cdr_client_lkp.appoint_transport(
            td_id=td_id,
            driver_id=5123,
            vehicle_id=10219
        )

        assert appoint_response == [], \
            f"Ожидался пустой массив, получено: {appoint_response}"

        print(f"✅ Водитель и ТС назначены на рейс {td_id}")

    time.sleep(3)

    with allure.step("ЧАСТЬ 6: Проверка деталки заявки"):

        # Получаем детали заявки
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "confirmed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Проверяем наличие массива outgoingEntities
        assert "outgoingEntities" in cdr_details, \
            f"В деталке заявки отсутствует поле 'outgoingEntities'. Ответ: {cdr_details}"

        outgoing_entities = cdr_details.get("outgoingEntities", [])
        assert isinstance(outgoing_entities, list), \
            f"Поле 'outgoingEntities' должно быть списком. Получено: {type(outgoing_entities)}"

        # Ищем рейс с нашим td_id
        found_td = None
        for entity in outgoing_entities:
            if entity.get("id") == td_id:
                found_td = entity
                break

        assert found_td is not None, \
            f"Рейс {td_id} не найден в outgoingEntities. Список: {outgoing_entities}"

        assert found_td.get("type") == "delivery", \
            f"Ожидался type='delivery', получен: '{found_td.get('type')}'"

        assert found_td.get("status") == "waiting_for_execution", \
            f"Ожидался status='waiting_for_execution', получен: '{found_td.get('status')}'"

    with allure.step("ЧАСТЬ 7: Проверка деталки рейса"):
        td_details = cdr_client_lkp.get_td_details(td_id)

        expected_td_status = "waiting_for_execution"
        actual_td_status = td_details.get("status")

        assert actual_td_status == expected_td_status, \
            f"Ожидался статус рейса '{expected_td_status}', получен: '{actual_td_status}'"

        print(f"✅ Статус рейса: {actual_td_status}")

        # Attach результатов
        with allure.step("Детали рейса"):
            allure.attach(
                json.dumps({
                    "td_id": td_id,
                    "status": actual_td_status,
                    "driver_id": td_details.get("driver", {}).get("id") if td_details.get("driver") else None,
                    "vehicle_id": td_details.get("vehicle", {}).get("id") if td_details.get("vehicle") else None
                }, indent=2, ensure_ascii=False),
                name="Статус рейса",
                attachment_type=allure.attachment_type.JSON
            )

    with allure.step("ЧАСТЬ 8: Проверка статусов грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)

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

                    assert gm_info.get("status") == "waiting_for_sending", \
                        f"ГМ {cargo_id}: Ожидался статус 'waiting_for_sending', получен: '{gm_info.get('status')}'"

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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Выполнение Заявки с грузоместами")
@pytest.mark.parametrize("cargo_count", [10])
def test_execute3_cdr_with_cargo_places_lkz(
    lkz_ext_token,
    lkz_token,
    lkp_token,
    cargo_count
):
    with allure.step("ЧАСТЬ 1: Создание грузомест"):
        gm_client_ext = CargoPlaceClient(EXTERNAL_URL, lkz_ext_token)

        cargo_list = gm_client_ext.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            use_predefined_addresses=False,
            departure_external_id='AUTO 005',
            delivery_external_id='AUTO 006'
        )

        responses = gm_client_ext.create_cargo_places_batch(cargo_list, batch_size=100)
        assert responses, "Не получен ответ при создании грузомест"

        cargo_place_ids = []
        for response in responses:
            assert "data" in response, f"Нет поля data: {response}"
            batch_ids = [item["id"] for item in response.get("data", []) if "id" in item]
            assert batch_ids, f"Нет id в ответе: {response}"
            cargo_place_ids.extend(batch_ids)

        print(f"✅ Создано {len(cargo_place_ids)} грузомест")

    with allure.step("ЧАСТЬ 2: Создание заявки"):
        cargo_places_for_cdr = [
            {"id": cid, "arrivalPoint": 27032, "departurePoint": 27030}
            for cid in cargo_place_ids
        ]

        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)
        cdr_response = cdr_client.create_and_publish_delivery_request(
            delivery_type="auto",
            delivery_sub_type="ftl",
            body_types=[3, 4, 7, 8],
            vehicle_type_id=1,
            order_type=1,
            point_change_type=2,
            route=[
                {"position": 1, "point": 27030, "isLoadingWork": True, "isUnloadingWork": False},
                {"position": 2, "point": 27032, "isLoadingWork": False, "isUnloadingWork": True}
            ],
            comment=f"Тестовая заявка с {cargo_count} ГМ",
            client_identifier=f"CDR-EXECUTION-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
            producer_id=3486,
            rate=100000,
            selecting_strategy="rate",
            cargo_places=cargo_places_for_cdr
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"Нет id заявки в ответе: {cdr_response}"
        print(f"✅ Заявка создана: ID={cdr_id}")

    with allure.step("ЧАСТЬ 3: Принятие обязательств подрядчиком"):
        cdr_client_lkp = CargoDeliveryRequestClient(BASE_URL, lkp_token)

        take_response = cdr_client_lkp.take_cdr(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Принятие обязательств не удалось"
        print(f"✅ Обязательства приняты подрядчиком для заявки {cdr_id}")

        # Attach ответа
        with allure.step("Ответ API (take)"):
            allure.attach(
                json.dumps(take_response, indent=2, ensure_ascii=False),
                name="Ответ API (take CDR)",
                attachment_type=allure.attachment_type.JSON
            )

    time.sleep(1)

    with allure.step("ЧАСТЬ 4: Создание рейса"):
        trip_response = cdr_client_lkp.create_trip(
            cdr_id=[cdr_id],
            trip_type="truck",
            producer_id=3486
        )

        # Извлекаем id рейса
        td_id = trip_response.get("id")
        assert td_id, f"Нет id рейса в ответе: {trip_response}"

        print(f"✅ Рейс создан: ID={td_id}")

    time.sleep(1)

    with allure.step("ЧАСТЬ 5: Назначение водителя и ТС на рейс"):
        appoint_response = cdr_client_lkp.appoint_transport(
            td_id=td_id,
            driver_id=5129,
            vehicle_id=10366
        )

        assert appoint_response == [], \
            f"Ожидался пустой массив, получено: {appoint_response}"

        print(f"✅ Водитель и ТС назначены на рейс {td_id}")

    time.sleep(3)

    with allure.step("ЧАСТЬ 6: Старт исполнения рейса"):
        start_response = cdr_client_lkp.start_td(td_id=td_id)

        # Attach ответа
        with allure.step("Ответ API (start trip)"):
            allure.attach(
                json.dumps(start_response, indent=2, ensure_ascii=False),
                name="Ответ API (start trip)",
                attachment_type=allure.attachment_type.JSON
            )

        print(f"✅ Рейс {td_id} запущен в исполнение")

    time.sleep(3)

    with allure.step("ЧАСТЬ 7: Проверка деталки заявки"):
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "execution"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Проверяем наличие массива outgoingEntities
        assert "outgoingEntities" in cdr_details, \
            f"В деталке заявки отсутствует поле 'outgoingEntities'. Ответ: {cdr_details}"

        outgoing_entities = cdr_details.get("outgoingEntities", [])
        assert isinstance(outgoing_entities, list), \
            f"Поле 'outgoingEntities' должно быть списком. Получено: {type(outgoing_entities)}"

        # Ищем рейс с нашим td_id
        found_td = None
        for entity in outgoing_entities:
            if entity.get("id") == td_id:
                found_td = entity
                break

        assert found_td is not None, \
            f"Рейс {td_id} не найден в outgoingEntities. Список: {outgoing_entities}"

        assert found_td.get("type") == "delivery", \
            f"Ожидался type='delivery', получен: '{found_td.get('type')}'"

        assert found_td.get("status") == "execution", \
            f"Ожидался status='execution', получен: '{found_td.get('status')}'"

    with allure.step("ЧАСТЬ 8: Проверка деталки рейса"):
        td_details = cdr_client_lkp.get_td_details(td_id)

        expected_td_status = "execution"
        actual_td_status = td_details.get("status")

        assert actual_td_status == expected_td_status, \
            f"Ожидался статус рейса '{expected_td_status}', получен: '{actual_td_status}'"

        print(f"✅ Статус рейса: {actual_td_status}")

    with allure.step("ЧАСТЬ 9: Выполнение работ на первом адресе"):

        # Вычисляем время (на 8 и 7 часов меньше текущего)
        now = datetime.now(timezone.utc)
        started_at = (now - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
        completed_at = (now - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"   Текущее время: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        print(f"   startedAt: {started_at} (-8 часов)")
        print(f"   completedAt: {completed_at} (-7 часов)")

        # Обновляем статус точки 1
        point_response = cdr_client_lkp.update_point_status(
            td_id=td_id,
            position=1,
            started_at=started_at,
            completed_at=completed_at
        )

        # Attach ответа
        with allure.step("Ответ API (update point status)"):
            allure.attach(
                json.dumps(point_response, indent=2, ensure_ascii=False),
                name="Ответ API (update point status)",
                attachment_type=allure.attachment_type.JSON
            )

        with allure.step("Статистика выполнения работ"):
            allure.attach(
                json.dumps({
                    "td_id": td_id,
                    "position": 1,
                    "started_at": started_at,
                    "completed_at": completed_at
                }, indent=2, ensure_ascii=False),
                name="Время выполнения работ на точке 1",
                attachment_type=allure.attachment_type.JSON
            )

        print(f"✅ Работы на первом адресе выполнены")

    time.sleep(2)

    with allure.step("ЧАСТЬ 10: Проверка статусов грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)

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

                    assert gm_info.get("status") == "sent", \
                        f"ГМ {cargo_id}: Ожидался статус 'sent', получен: '{gm_info.get('status')}'"

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

    with allure.step("ЧАСТЬ 11: Выполнение работ на втором адресе"):

        # Вычисляем время
        now = datetime.now(timezone.utc)
        started_at = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        completed_at = (now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"   Текущее время: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        print(f"   startedAt: {started_at} (-8 часов)")
        print(f"   completedAt: {completed_at} (-7 часов)")

        # Обновляем статус точки 2
        point_response = cdr_client_lkp.update_point_status(
            td_id=td_id,
            position=2,
            started_at=started_at,
            completed_at=completed_at
        )

        # Attach ответа
        with allure.step("Ответ API (update point status)"):
            allure.attach(
                json.dumps(point_response, indent=2, ensure_ascii=False),
                name="Ответ API (update point status)",
                attachment_type=allure.attachment_type.JSON
            )

        with allure.step("Статистика выполнения работ"):
            allure.attach(
                json.dumps({
                    "td_id": td_id,
                    "position": 2,
                    "started_at": started_at,
                    "completed_at": completed_at
                }, indent=2, ensure_ascii=False),
                name="Время выполнения работ на точке 1",
                attachment_type=allure.attachment_type.JSON
            )

    time.sleep(2)

    with allure.step("ЧАСТЬ 12: Проверка деталки заявки ЛКП"):
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "completed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        # Проверяем наличие массива outgoingEntities
        assert "outgoingEntities" in cdr_details, \
            f"В деталке заявки отсутствует поле 'outgoingEntities'. Ответ: {cdr_details}"

        outgoing_entities = cdr_details.get("outgoingEntities", [])
        assert isinstance(outgoing_entities, list), \
            f"Поле 'outgoingEntities' должно быть списком. Получено: {type(outgoing_entities)}"

        # Ищем рейс с нашим td_id
        found_td = None
        for entity in outgoing_entities:
            if entity.get("id") == td_id:
                found_td = entity
                break

        assert found_td is not None, \
            f"Рейс {td_id} не найден в outgoingEntities. Список: {outgoing_entities}"

        assert found_td.get("type") == "delivery", \
            f"Ожидался type='delivery', получен: '{found_td.get('type')}'"

        assert found_td.get("status") == "completed", \
            f"Ожидался status='completed', получен: '{found_td.get('status')}'"

    with allure.step("ЧАСТЬ 13: Проверка деталки заявки ЛКЗ"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)

        expected_status = "completed"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус заявки '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

        request_nr = cdr_details.get("requestNr")
        assert request_nr and isinstance(request_nr, str) and len(request_nr) > 0, \
            f"Поле requestNr пустое или некорректное: {request_nr}"
        print(f"✅ Номер заявки: {request_nr}")

        expected_strategy = "rate"
        actual_strategy = cdr_details.get("selectingStrategy")
        assert actual_strategy == expected_strategy, \
            f"Ожидалась selectingStrategy '{expected_strategy}', получена: '{actual_strategy}'"
        print(f"✅ Тип публикации: {actual_strategy}")

        cargo_summary = cdr_details.get("cargoPlacesSummary", {})
        assert "totalCount" in cargo_summary, \
            f"Отсутствует поле totalCount в cargoPlacesSummary: {cargo_summary}"
        assert "receivedCount" in cargo_summary, \
            f"Отсутствует поле receivedCount в cargoPlacesSummary: {cargo_summary}"

        total_count = cargo_summary.get("totalCount")
        received_count = cargo_summary.get("receivedCount")

        # Проверяем что значения числовые
        assert isinstance(total_count, int) and total_count > 0, \
            f"totalCount должно быть положительным числом: {total_count}"
        assert isinstance(received_count, int) and received_count > 0, \
            f"receivedCount должно быть положительным числом: {received_count}"

        # Проверяем что значения соответствуют cargo_count из теста
        assert total_count == cargo_count, \
            f"Ожидалось totalCount={cargo_count}, получено: {total_count}"
        assert received_count == cargo_count, \
            f"Ожидалось receivedCount={cargo_count}, получено: {received_count}"

        print(f"✅ cargoPlacesSummary: totalCount={total_count}, receivedCount={received_count}")

    with allure.step("ЧАСТЬ 14: Проверка деталки рейса"):
        td_details = cdr_client_lkp.get_td_details(td_id)

        expected_td_status = "completed"
        actual_td_status = td_details.get("status")

        assert actual_td_status == expected_td_status, \
            f"Ожидался статус рейса '{expected_td_status}', получен: '{actual_td_status}'"

        print(f"✅ Статус рейса: {actual_td_status}")

    time.sleep(3)

    with allure.step("ЧАСТЬ 15: Проверка статусов грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)

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

                    assert gm_info.get("status") == "received", \
                        f"ГМ {cargo_id}: Ожидался статус 'received', получен: '{gm_info.get('status')}'"

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

                    # Проверка что массив cargoDeliveryRequests не содержит ID заявки
                    cargo_delivery_requests = gm_info.get("cargoDeliveryRequests", [])
                    cdr_ids_in_gm = [cdr["id"] for cdr in cargo_delivery_requests if "id" in cdr]

                    assert cdr_id not in cdr_ids_in_gm, \
                        f"ГМ {cargo_id}: Заявка {cdr_id} найдена в грузоместе, но не должна быть. Найдено: {cdr_ids_in_gm}"

                    print(f"ГМ {cargo_id}: cargoDeliveryRequests не содержит заявку {cdr_id}")

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














