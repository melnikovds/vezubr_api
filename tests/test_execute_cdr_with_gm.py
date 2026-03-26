import allure
import pytest
import json
import random
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
            client_identifier=f"CDR-PUBLISH-{datetime.now().strftime('%d%m%Y-%H%M%S')}",
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
