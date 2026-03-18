import random
from typing import List, Dict, Any
import requests
from datetime import datetime, timedelta


class CargoPlaceCreateOrUpdateListClient:
    CARGO_TYPES = ["free", "pallet", "box", "bag"]

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

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
            departure_external_id: str = "Izhevsk 76-276",
            delivery_external_id: str = "Izhevsk 36-950",
            role: str = "test"
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список из count грузомест

        Args:
            count: Количество грузомест для создания
            departure_external_id: Внешний ID адреса отправления
            delivery_external_id: Внешний ID адреса доставки
            role: Роль для генерации уникальных ID

        Returns:
            Список словарей с данными грузомест
        """
        cargo_list = []
        for i in range(count):
            cargo = self.generate_cargo_place(
                departure_external_id=departure_external_id,
                delivery_external_id=delivery_external_id,
                external_id=f"EXT-GM-{role}-{i + 1:03d}",
                bar_code=f"BC-{role}-{i + 1:03d}",
                invoice_number=f"INV-{role}-{i + 1:03d}",
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

