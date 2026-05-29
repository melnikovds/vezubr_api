import random
import  allure
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
import requests
from datetime import datetime, timedelta
from pprint import pprint


class ShipmentTaskClient:
    """
    Клиент для работы с эндпоинтами Заданий
    """
    CARGO_TYPES = ["free", "pallet", "box", "bag"]

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def generate_shipment_task(self, cargo_place_ids, dep_point, arr_point):
        # генерация номера Задания
        current_date = datetime.now().strftime("%d%m%Y")
        random_part = str(random.randint(0, 999999)).zfill(6)
        number = f"{current_date}-{random_part}"

        # название товара
        random_words = [
            "shoes", "jacket", "laptop", "phone", "table",
            "chair", "monitor", "keyboard", "backpack", "watch"
        ]
        title = random.choice(random_words)

        return {
                "number": number,
                "title": title,
                "shipBy": "vezubr",
                "requiredSentAtFrom": None,
                "requiredSentAtTill": None,
                "requiredDeliveredAtTill": None,
                "requiredDeliveredAtFrom": None,
                "consignee": None,
                "shipper": None,
                "departurePoint": {
                    "id": dep_point
                },
                "arrivalPoint": {
                    "id": arr_point
                },
                "volume": None,
                "weight": None,
                "cost": None,
                "quantity": None,
            "cargoPlaces": [
                {"id": gm_id} for gm_id in cargo_place_ids
            ],
                "types": [],
                "isCargoPlacesEnabled": True
            }

    def create_shipment_task(
            self,
            cargo_place_ids: List[int],
            dep_point: int = 27030,
            arr_point: int = 27032
    ) -> str:

        url = f"{self.base_url}/shipment/tasks/create"

        task_data = self.generate_shipment_task(
            cargo_place_ids,
            dep_point=dep_point,
            arr_point=arr_point
        )

        payload = task_data

        response = requests.post(url, headers=self.headers, json=payload)

        assert response.status_code == 200, \
            f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        task_id = result.get("id")
        assert task_id, f"В ответе нет id: {result}"

        print(f"✅ Задание {task_id} успешно создано")

        return task_id

    def get_shipment_task(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/shipment/tasks/{task_id}"

        response = requests.get(url, headers=self.headers)

        assert response.status_code == 200, \
            f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        return response.json()










