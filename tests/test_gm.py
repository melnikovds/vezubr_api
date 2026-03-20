import allure
import pytest
import json
from pages.cargo_create_or_update_list_page import *
from pages.cdr_create_and_publish_page import *
from config.settings import *


@allure.story("Smoke test")
@allure.feature("CDR")
@allure.description("Создание выбранного количество грузомест")
@pytest.mark.parametrize("auth_token", ["lkz_ext"], indirect=True)
def test_cargo_create_or_update_list_lkz(auth_token, cargo_count):
    """
    Тест создания грузомест

    Args:
        auth_token: Токен авторизации (из фикстуры conftest)
        cargo_count: Количество грузомест (из аргумента командной строки --cargo-count)
    """
    client = CargoPlaceCreateOrUpdateListClient(EXTERNAL_URL, auth_token)

    # генерация параметров грузомест
    with allure.step(f"Генерация {cargo_count} грузомест"):
        cargo_list = client.generate_cargo_places_list(
            count=cargo_count,
            role="lkz_ext",
            use_predefined_addresses=True
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

    # проверка ответов
    with allure.step("Проверка структуры ответов"):
        # проверяем каждый батч
        for idx, response in enumerate(responses, 1):
            assert response.get("status") == "ok", f"Батч {idx}: Ожидался 'ok', получен: {response.get('status')}"
            data = response.get("data", [])
            print(f"Батч {idx}: создано {len(data)} грузомест")

        # считаем общее количество созданных грузомест
        total_created = sum(len(r.get("data", [])) for r in responses)
        assert total_created == cargo_count, f"Ожидалось {cargo_count} ГМ, создано: {total_created}"

        # проверяем структуру каждого грузоместа
        for response in responses:
            for item in response.get("data", []):
                assert "id" in item and isinstance(item["id"], int) and item["id"] > 0
                assert item.get("status") == "ok"
                assert "errors" in item and isinstance(item["errors"], list)

        # проверяем что количество ID совпадает с ожидаемым
        assert len(cargo_place_ids) == cargo_count, f"Ожидалось {cargo_count} ID, собрано: {len(cargo_place_ids)}"

        # проверяем что все ID положительные числа
        for cargo_id in cargo_place_ids:
            assert isinstance(cargo_id, int) and cargo_id > 0, f"Некорректный ID: {cargo_id}"

    # аттач логов
    with allure.step("Детали запроса и ответа"):
        allure.attach(
            json.dumps({"total_cargo_places": cargo_count, "batches": len(responses)}, indent=2, ensure_ascii=False),
            name="Общая статистика",
            attachment_type=allure.attachment_type.JSON
        )

        # Если батчей немного, можно приаттачить все ответы
        if len(responses) <= 5:
            allure.attach(
                json.dumps(responses, indent=2, ensure_ascii=False),
                name="Ответы API (все батчи)",
                attachment_type=allure.attachment_type.JSON
            )
        else:
            # Если батчей много, аттачим первый и последний
            allure.attach(
                json.dumps(responses[0], indent=2, ensure_ascii=False),
                name="Ответ API (батч 1)",
                attachment_type=allure.attachment_type.JSON
            )
            allure.attach(
                json.dumps(responses[-1], indent=2, ensure_ascii=False),
                name="Ответ API (последний батч)",
                attachment_type=allure.attachment_type.JSON
            )

    print(f"\n✅ Успешно создано {cargo_count} грузомест в {len(responses)} батча(ей)")
    # print(f"Список ID: {cargo_place_ids}")