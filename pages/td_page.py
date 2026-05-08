import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class TruckDeliveryClient:
    """
    Клиент для работы с эндпоинтами Рейсов
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def create_trip(self, cdr_id: List[str], trip_type: str = "truck", producer_id: int = 3486) -> Dict[str, Any]:
        """
        Создаёт рейс по заявкам (роль LKP)

        Args:
            cdr_id: ID заявки (UUID)
            trip_type: Тип рейса
            producer_id: ID подрядчика

        Returns:
            Ответ API с ID созданного рейса
        """
        url = f"{self.base_url}/cargo-deliveries/create"

        payload = {
            "requests": cdr_id,
            "type": trip_type,
            "producer": producer_id
        }

        print(f"\n📋 Создание рейса: {url}")
        print(f"   Заявка: {cdr_id}")
        print(f"   Тип: {trip_type}")
        print(f"   Подрядчик: {producer_id}")

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, \
            f"create_trip: Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        assert "id" in result and result.get("id") is not None, \
            f"create_trip: Отсутствует поле 'id' в ответе. Ответ: {result}"

        print(f"✅ Рейс создан: ID={result.get('id')}")

        return result

    def appoint_transport(self, td_id: str, driver_id: int, vehicle_id: int) -> Dict[str, Any]:
        """
        Назначает водителя и ТС на рейс

        Args:
            td_id: ID рейса (UUID)
            driver_id: ID водителя
            vehicle_id: ID транспортного средства

        Returns:
            Ответ API
        """
        url = f"{self.base_url}/truck-deliveries/{td_id}/transport/appoint"

        payload = {
            "driver": driver_id,
            "vehicle": vehicle_id,
            "isLiftingValidationRequired": True,
            "isAgreeWithAdditionalRequirements": False
        }

        print(f"   Водитель: {driver_id}")
        print(f"   ТС: {vehicle_id}")

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, \
            f"appoint_transport: Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()
        print(f"✅ ТС назначено на рейс {td_id}")

        return result

    def get_td_details(self, td_id: str) -> Dict[str, Any]:
        """
        Получает детали рейса по ID (роль LKP)

        Args:
            td_id: ID рейса (UUID)

        Returns:
            Ответ API с деталями рейса
        """
        url = f"{self.base_url}/truck-deliveries/{td_id}/details"

        print(f"\n📋 Запрос деталки рейса: {url}")

        response = requests.get(
            url,
            headers=self.headers,
            timeout=30
        )

        assert response.status_code == 200, \
            f"get_td_details: Ожидался статус 200 для рейса {td_id}, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        assert "status" in result, \
            f"get_td_details: Отсутствует поле 'status' в ответе для рейса {td_id}. Ответ: {result}"

        print(f"✅ Получена деталка рейса {td_id}: status={result.get('status')}")

        return result

    def start_td(self, td_id: str) -> Dict[str, Any]:
        """
        Начинает исполнение рейса (роль LKP)

        Args:
            td_id: ID рейса (UUID)

        Returns:
            Ответ API
        """
        url = f"{self.base_url}/cargo-deliveries/{td_id}/start"

        print(f"\n📋 Старт рейса: {url}")

        response = requests.post(
            url,
            headers=self.headers,
            json={},
            timeout=30
        )

        assert response.status_code == 200, \
            f"start_td: Ожидался статус 200 для рейса {td_id}, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()
        print(f"✅ Рейс {td_id} перешёл в исполнение")

        return result

    def update_point_status(self, td_id: str, position: int, started_at: str, completed_at: str) -> Dict[str, Any]:
        """
        Обновляет статус работы на точке маршрута (роль LKP)

        Args:
            td_id: ID рейса (UUID)
            position: Позиция точки в маршруте
            started_at: Время начала работ (ISO 8601)
            completed_at: Время завершения работ (ISO 8601)

        Returns:
            Ответ API
        """
        url = f"{self.base_url}/truck-deliveries/{td_id}/points/update/statuses"

        payload = {
            "points": [
                {
                    "position": position,
                    "startedAt": started_at,
                    "completedAt": completed_at
                }
            ]
        }

        print(f"\n📋 Обновление статуса точки {position} рейса {td_id}")
        print(f"   startedAt: {started_at}")
        print(f"   completedAt: {completed_at}")

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, \
            f"update_point_status: Ожидался статус 200 для точки {position} рейса {td_id}, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()
        print(f"✅ Статус точки {position} обновлён")

        return result

