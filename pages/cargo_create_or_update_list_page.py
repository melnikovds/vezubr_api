import random
import  allure
import time
from typing import List, Dict, Any, Optional, Tuple
import requests
from datetime import datetime, timedelta


class CargoPlaceCreateOrUpdateListClient:
    CARGO_TYPES = ["free", "pallet", "box", "bag"]

    VALID_EXTERNAL_ID: List[Tuple[str, str]] = [
        ("VALID_EXTERNAL_ID_001", "VALID_EXTERNAL_ID_002"),
        ("VALID_EXTERNAL_ID_003", "VALID_EXTERNAL_ID_004"),
        ("VALID_EXTERNAL_ID_005", "VALID_EXTERNAL_ID_006"),
    ]

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def _generate_unique_external_id(self) -> str:
        part1 = random.randint(1000, 9999)
        part2 = random.randint(1000, 9999)
        part3 = random.randint(100000, 999999)
        return f"{part1}-{part2}-{part3}"

    def _generate_random_dimensions(self) -> Dict[str, int]:
        length = random.randint(10, 200)
        width = random.randint(10, 150)
        height = random.randint(10, 150)
        volume = length * width * height
        weight = random.randint(500, 20000)
        quantity = random.randint(1, 50)
        return {
            "length": length,
            "width": width,
            "height": height,
            "volume": volume,
            "weight": weight,
            "quantity": quantity
        }

    def _generate_random_datetime_window(self) -> Dict[str, str]:
        base = datetime.now()
        start = base.replace(hour=9, minute=0, second=0, microsecond=0)
        end = base.replace(hour=18, minute=0, second=0, microsecond=0)
        return {
            "requiredSendAtFrom": start.isoformat(),
            "requiredSendAtTill": end.isoformat(),
            "requiredDeliveredAtFrom": (start + timedelta(days=2)).isoformat(),
            "requiredDeliveredAtTill": (end + timedelta(days=2)).isoformat(),
        }

    def generate_cargo_place(
            self,
            departure_external_id: str,
            delivery_external_id: str,
            external_id: str,
            bar_code: str,
            invoice_number: str,
            is_planned: bool = False
    ) -> Dict[str, Any]:
        dims = self._generate_random_dimensions()
        time_windows = self._generate_random_datetime_window()

        return {
            "status": "new",
            "barCode": bar_code,
            "type": random.choice(self.CARGO_TYPES),
            "departureAddressExternalId": departure_external_id,
            "deliveryAddressExternalId": delivery_external_id,
            "invoiceNumber": invoice_number,
            "invoiceNumbers": [invoice_number],
            "externalId": external_id,
            "isPlanned": is_planned,
            **dims,
            **time_windows,
            "wmsNumber": f"WMS-{external_id}",
            "invoiceDate": "2026-03-14",
            # ИНН/КПП НЕ указываем — не обязательны и могут вызвать ошибку
        }

    def generate_cargo_places_list(
            self,
            count: int,
            departure_external_id: Optional[str] = None,
            delivery_external_id: Optional[str] = None,
            role: str = "test",
            use_predefined_addresses: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список из count грузомест

        Args:
            count: Количество грузомест для создания
            departure_external_id: Внешний ID адреса отправления (если не указан - берётся из списка)
            delivery_external_id: Внешний ID адреса доставки (если не указан - берётся из списка)
            role: Роль для генерации уникальных ID
            use_predefined_addresses: Использовать ли предопределённые адреса

        Returns:
            Список словарей с данными грузомест
        """
        cargo_list = []
        for i in range(count):

            # Если нужны предопределённые адреса - берём их по циклу
            if use_predefined_addresses and self.VALID_EXTERNAL_ID:
                dep_ext, del_ext = self.VALID_EXTERNAL_ID[i % len(self.VALID_EXTERNAL_ID)]
            else:
                # Или используем переданные вручную / дефолтные
                dep_ext = departure_external_id or "AUTO 001"
                del_ext = delivery_external_id or "AUTO 002"

            external_id = self._generate_unique_external_id()

            cargo = self.generate_cargo_place(
                departure_external_id=dep_ext,
                delivery_external_id=del_ext,
                external_id=f"GM-{role}-{external_id}",
                bar_code=f"ШК-{role}-00000{random.randint(100000, 999999)}",
                invoice_number=f"INV-{role}-{random.randint(100000, 999999)}",
                is_planned=False
            )
            cargo_list.append(cargo)
        return cargo_list

    def create_or_update_cargo_places_list(self, cargo_places: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = f"{self.base_url}/cargo-place/create-or-update-list"
        payload = {"data": cargo_places}

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code != 200:
            print(f"\n❌ Ошибка create-or-update-list: {response.status_code}")
            print(f"URL: {url}")
            print(f"Тело запроса: {payload}")
            print(f"Ответ сервера: {response.text}")
            response.raise_for_status()

        return response.json()

    def create_cargo_places_batch(
            self,
            cargo_places: List[Dict[str, Any]],
            batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Создаёт грузоместа пакетами по N штук

        Args:
            cargo_places: Полный список грузомест для создания
            batch_size: Максимальное количество грузомест в одном запросе

        Returns:
            Список всех ответов от сервера (по одному на каждый батч)
        """
        all_responses = []
        total_count = len(cargo_places)
        total_batches = (total_count + batch_size - 1) // batch_size

        # Разбиваем на батчи по 100
        for i in range(0, total_count, batch_size):
            batch = cargo_places[i:i + batch_size]
            batch_number = (i // batch_size) + 1

            print(f"\n📦 Отправка батча {batch_number}/{total_batches} ({len(batch)} грузомест)")

            with allure.step(f"Батч {batch_number}/{total_batches}: Создание {len(batch)} грузомест"):
                response = self.create_or_update_cargo_places_list(batch)
                all_responses.append(response)

                # Проверка ответа для каждого батча
                assert response.get("status") == "ok", f"Батч {batch_number} не успешен: {response}"

            time.sleep(1)

        return all_responses


