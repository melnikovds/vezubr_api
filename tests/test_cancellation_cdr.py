import allure
import pytest
import json
from pages.gm_page import *
from pages.cdr_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Отмена Заявки с грузоместами Заказчиком (без созданного Рейса)")
@pytest.mark.parametrize("cargo_count", [50])
def test_cancel1_cdr_with_cargo_places_lkz(
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
            client_identifier=f"CDR-CANCEL-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
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

    time.sleep(3)

    with allure.step("ЧАСТЬ 4: Отмена заявки Заказчиком"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)

        take_response = cdr_client.cancel_cdr_lkz(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Отмена заявки не удалась"
        print(f"✅ Заявка {cdr_id} отменена")

    time.sleep(2)

    with allure.step("ЧАСТЬ 5: Проверка деталки заявки ЛКЗ"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)

        expected_status = "canceled_by_client"
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

    with allure.step("ЧАСТЬ 6: Проверка деталки заявки ЛКП"):
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "canceled_by_client"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    with allure.step("ЧАСТЬ 7: Проверка статусов грузомест"):
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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Отмена Заявки с грузоместами Заказчиком (с созданным Рейсом)")
@pytest.mark.parametrize("cargo_count", [50])
def test_cancel2_cdr_with_cargo_places_lkz(
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
            client_identifier=f"CDR-CANCEL-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
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

    with allure.step("ЧАСТЬ 6: Отмена заявки Заказчиком"):
        cdr_client = CargoDeliveryRequestClient(BASE_URL, lkz_token)

        take_response = cdr_client.cancel_cdr_lkz(cdr_id)

        # Проверка ответа
        assert take_response is not None, "Отмена заявки не удалась"
        print(f"✅ Заявка {cdr_id} отменена")

    time.sleep(2)

    with allure.step("ЧАСТЬ 7: Проверка деталки заявки ЛКЗ"):
        cdr_details = cdr_client.get_cdr_details(cdr_id)

        expected_status = "canceled_by_client"
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

    with allure.step("ЧАСТЬ 8: Проверка деталки заявки ЛКП"):
        cdr_details = cdr_client_lkp.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"

        expected_status = "canceled_by_client"
        actual_status = cdr_details.get("status")
        assert actual_status == expected_status, \
            f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
        print(f"✅ Статус заявки: {actual_status}")

    with allure.step("ЧАСТЬ 9: Проверка деталки рейса"):
        td_details = cdr_client_lkp.get_td_details(td_id)

        expected_td_status = "canceled"
        actual_td_status = td_details.get("status")

        assert actual_td_status == expected_td_status, \
            f"Ожидался статус рейса '{expected_td_status}', получен: '{actual_td_status}'"

        print(f"✅ Статус рейса: {actual_td_status}")

    time.sleep(3)

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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Отмена Заявки с грузоместами Подрядчиком (без созданного Рейса)")
@pytest.mark.parametrize("cargo_count", [100])
def test_cancel3_cdr_with_cargo_places_lkz(
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
            client_identifier=f"CDR-CANCEL-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
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


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Отмена Заявки с грузоместами Подрядчиком (с созданным Рейсом)")
@pytest.mark.parametrize("cargo_count", [100])
def test_cancel4_cdr_with_cargo_places_lkz(
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
            client_identifier=f"CDR-CANCEL-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
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