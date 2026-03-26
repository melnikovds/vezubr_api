import allure
import pytest
import json
from pages.gm_page import *
from pages.cdr_page import *
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
            name="Ответ API",
            attachment_type=allure.attachment_type.JSON
        )

    print(f"\n✅ Успешно создано {cargo_count} грузомест и заявка CDR")


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание черновика Заявки с грузоместами")
@pytest.mark.parametrize("auth_token_ext", ["lkz_ext"], indirect=True)
@pytest.mark.parametrize("auth_token_base", ["lkz"], indirect=True)
@pytest.mark.parametrize("cargo_count", [50])
def test_create_draft_cdr_with_cargo_places_lkz(auth_token_ext, auth_token_base, cargo_count):
    """
    Тест создания черновика Заявки

    Args:
        auth_token_ext: Токен внешней системы для создания грузомест
        auth_token_base: Токен внутренней системы для создания заявки
    """
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

    # Создание Заявки
    with allure.step("Создание и публикация заявки"):
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
            cargo_places=cargo_places_for_cdr
        )

    # Проверка ответа
    with allure.step("Проверка ответа"):
        assert cdr_response.get("id") is not None, "CDR не создан: отсутствует ID"
        assert cdr_response.get("requestNr") is not None, "CDR не создан: отсутствует requestNr"
        print(f"✅ Заявка создана: ID={cdr_response.get('id')}, requestNr={cdr_response.get('requestNr')}")

    print(f"\n✅ Успешно создано {cargo_count} грузомест и заявка CDR")
    time.sleep(5)

    with allure.step("Проверка статуса заявки и наличия грузомест"):
        # Получаем детали заявки
        cdr_id=cdr_response.get('id')
        cdr_details = cdr_client.get_cdr_details(cdr_id)

        with allure.step("Проверка статуса заявки"):
            expected_status = "draft"
            actual_status = cdr_details.get("status")
            assert actual_status == expected_status, \
                f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
            print(f"Статус заявки: {actual_status}")

        with allure.step("Проверка наличия всех грузомест в заявке"):
            cargo_places_in_cdr = cdr_details.get("cargoPlaces", [])
            cdr_cargo_ids = [cp["id"] for cp in cargo_places_in_cdr if "id" in cp]

            assert len(cdr_cargo_ids) == len(cargo_place_ids), \
                f"Ожидалось {len(cargo_place_ids)} ГМ в заявке, получено: {len(cdr_cargo_ids)}"

            # Проверяем что все ID присутствуют
            missing_ids = set(cargo_place_ids) - set(cdr_cargo_ids)
            assert len(missing_ids) == 0, \
                f"Отсутствуют грузоместа в заявке: {missing_ids}"

            # Проверяем что нет лишних ID
            extra_ids = set(cdr_cargo_ids) - set(cargo_place_ids)
            assert len(extra_ids) == 0, \
                f"Лишние грузоместа в заявке: {extra_ids}"

            print(f"✅ Все {len(cargo_place_ids)} грузомест присутствуют в заявке")

    with allure.step("Проверка деталей грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, auth_token_base)

        validated_count = 0
        failed_validations = []

        # Проверяем первые 10 грузомест, или все, если их меньше 10
        ids_to_check = cargo_place_ids[:10] if cargo_count > 10 else cargo_place_ids

        for cargo_id in ids_to_check:
            with allure.step(f"Проверка грузоместа {cargo_id}"):
                try:
                    gm_info = gm_client_base.get_cargo_place_info(cargo_id)

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
                        f"ГМ {cargo_id}: Заявка {cdr_id} не найдена в cargoDeliveryRequests. Найдено: {cdr_ids_in_gm}"

                    validated_count += 1
                    print(f"✅ ГМ {cargo_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"ГМ {cargo_id}: {str(e)}")
                    print(f"❌ ГМ {cargo_id}: {str(e)}")
                except Exception as e:
                    failed_validations.append(f"ГМ {cargo_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ ГМ {cargo_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        # Итоговая проверка
        assert len(failed_validations) == 0, \
            f"Не прошли проверки для {len(failed_validations)} грузомест:\n" + "\n".join(failed_validations)

        print(f"\n✅ Проверено {validated_count} грузомест, все проверки пройдены")


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание и публикация Заявки с указанным количеством грузомест")
@pytest.mark.parametrize("cargo_count", [10])
def test_create_and_publish_cdr_with_cargo_places_lkz(
    lkz_ext_token,
    lkz_token,
    cargo_count  # берётся из parametrize, а не из conftest
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
            assert "data" in response, f"В ответе нет поля data: {response}"
            batch_ids = [item["id"] for item in response.get("data", []) if "id" in item]
            assert batch_ids, f"Не удалось извлечь id грузомест из ответа: {response}"
            cargo_place_ids.extend(batch_ids)

        assert len(cargo_place_ids) == cargo_count, \
            f"Ожидалось {cargo_count} ГМ, создано: {len(cargo_place_ids)}"

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
            client_identifier=f"CDR-PUBLISH-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
            producer_id=3486,
            rate=100000,
            selecting_strategy="rate",
            cargo_places=cargo_places_for_cdr
        )

        cdr_id = cdr_response.get("id")
        assert cdr_id, f"В ответе нет id заявки: {cdr_response}"
        print(f"✅ Заявка создана: ID={cdr_id}")

    with allure.step("ЧАСТЬ 3: Проверка статуса заявки и наличия грузомест"):
        # Получаем детали заявки
        cdr_details = cdr_client.get_cdr_details(cdr_id)
        assert cdr_details, "Пустой ответ деталки заявки"
        assert "cargoPlaces" in cdr_details, "В ответе нет cargoPlaces"

        with allure.step("Проверка статуса заявки"):
            expected_status = "waiting_producer_confirmation"
            actual_status = cdr_details.get("status")
            assert actual_status == expected_status, \
                f"Ожидался статус '{expected_status}', получен: '{actual_status}'"
            print(f"✅ Статус заявки: {actual_status}")

        with allure.step("Проверка наличия всех грузомест в заявке"):
            cargo_places_in_cdr = cdr_details.get("cargoPlaces", [])
            cdr_cargo_ids = [cp["id"] for cp in cargo_places_in_cdr if "id" in cp]

            assert len(cdr_cargo_ids) == len(cargo_place_ids), \
                f"Ожидалось {len(cargo_place_ids)} ГМ в заявке, получено: {len(cdr_cargo_ids)}"

            # Проверяем что все ID присутствуют
            missing_ids = set(cargo_place_ids) - set(cdr_cargo_ids)
            assert len(missing_ids) == 0, \
                f"Отсутствуют грузоместа в заявке: {missing_ids}"

            # Проверяем что нет лишних ID
            extra_ids = set(cdr_cargo_ids) - set(cargo_place_ids)
            assert len(extra_ids) == 0, \
                f"Лишние грузоместа в заявке: {extra_ids}"

            print(f"✅ Все {len(cargo_place_ids)} грузомест присутствуют в заявке")

    with allure.step("ЧАСТЬ 4: Проверка грузомест"):
        gm_client_base = CargoPlaceClient(BASE_URL, lkz_token)

        validated_count = 0
        failed_validations = []

        # Проверяем первые 10 грузомест, или все, если их меньше 10
        ids_to_check = cargo_place_ids[:10] if cargo_count > 10 else cargo_place_ids

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

                    validated_count += 1
                    print(f"✅ ГМ {cargo_id}: все проверки пройдены")

                except AssertionError as e:
                    failed_validations.append(f"ГМ {cargo_id}: {str(e)}")
                    print(f"❌ ГМ {cargo_id}: {str(e)}")
                except Exception as e:
                    failed_validations.append(f"ГМ {cargo_id}: Ошибка запроса - {str(e)}")
                    print(f"❌ ГМ {cargo_id}: Ошибка запроса - {str(e)}")

                time.sleep(1)

        # Итоговая проверка
        assert len(failed_validations) == 0, \
            f"Не прошли проверки для {len(failed_validations)} грузомест:\n" + "\n".join(failed_validations)

        print(f"\n✅ Проверено {validated_count} грузомест, все проверки пройдены")







