import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class CargoDeliveryRequestClient:
    """
    Клиент для работы с эндпоинтами Реквестов
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def create_and_publish_delivery_request(
            self,
            delivery_type: str = "auto",
            delivery_sub_type: str = "ftl",
            body_types: List[int] = None,
            vehicle_type_id: int = 1,
            order_type: int = 1,
            point_change_type: int = 2,
            route: List[Dict] = None,
            comment: str = "Тестовая заявка",
            client_identifier: str = None,
            to_start_at_from: str = None,
            producer_id: int = None,
            rate: int = 1000000,
            selecting_strategy: str = "rate",
            cargo_places: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Создание и публикация заявки на доставку груза

        Args:
            cargo_places: Список грузомест в формате [{"id": 123, "arrivalPoint": 1, "departurePoint": 2}, ...]
        """
        if body_types is None:
            body_types = [3, 4, 7, 8]

        if route is None:
            route = []

        if to_start_at_from is None:
            to_start_at_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if client_identifier is None:
            client_identifier = f"CDR-{datetime.now().strftime('%d%m%Y-%H%M%S')}"

        payload = {
            "deliveryType": delivery_type,
            "deliverySubType": delivery_sub_type,
            "parameters": {
                "orderCategory": 1,
                "bodyTypes": body_types,
                "isDangerousGoods": False,
                "vehicleTypeId": vehicle_type_id,
                "isCornerPillarRequired": False,
                "isStrapRequired": False,
                "isChainRequired": False,
                "isNetRequired": False,
                "isTarpaulinRequired": False,
                "isWheelChockRequired": False,
                "isGPSMonitoringRequired": False,
                "isWoodenFloorRequired": False,
                "isDoppelstockRequired": False,
                "isTakeOutPackageRequired": False,
                "isDriverLoaderRequired": False,
                "orderType": order_type,
                "isHydroliftRequired": False,
                "isPalletJackRequired": False,
                "isConicsRequired": False,
                "isThermographRequired": False,
                "isLiftingValidationRequired": False,
                "pointChangeType": point_change_type,
                "isSanitaryPassportRequired": False,
                "isSanitaryBookRequired": False,
                "requiredDocuments": [],
                "route": route
            },
            "shipmentTasks": [],
            "responsibleEmployees": [],
            "comment": comment,
            "clientIdentifier": client_identifier,
            "innerComment": None,
            "toStartAtFrom": to_start_at_from,
            "toStartAtTill": None,
            "cargoPlaces": cargo_places or [],
            "newCargoPlaces": [],
            "additionalServices": [],
            "parametersForProducers": {
                "shares": [
                    {
                        "producer": producer_id,
                        "rate": rate
                    }
                ],
                "selectingStrategy": selecting_strategy
            }
        }

        if cargo_places:
            payload["parameters"]["cargoPlaces"] = cargo_places

        print(f" Payload для создания заявки на доставку:")
        print(f"   clientIdentifier: {client_identifier}")
        print(f"   deliverySubType: {delivery_sub_type}")
        print(f"   route points: {len(route)}")
        if cargo_places:
            print(f"   cargoPlaces: {len(cargo_places)}")

        response = requests.post(
            f"{self.base_url}/cargo-delivery-requests/create-and-publish",
            headers=self.headers,
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, \
            f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        assert "id" in result and result.get("id") is not None, \
            f"Отсутствует поле 'id' в ответе. Ответ: {result}"

        assert "requestNr" in result and result.get("requestNr") is not None, \
            f"Отсутствует поле 'requestNr' в ответе. Ответ: {result}"

        assert "status" in result, \
            f"Отсутствует поле 'status' в ответе. Ответ: {result}"

        print(
            f"✅ Заявка создана: ID={result.get('id')}, requestNr={result.get('requestNr')}, status={result.get('status')}")

        return result

    def create_delivery_request(
            self,
            delivery_type: str = "auto",
            delivery_sub_type: str = "ftl",
            body_types: List[int] = None,
            vehicle_type_id: int = 1,
            order_type: int = 1,
            point_change_type: int = 2,
            route: List[Dict] = None,
            comment: str = "Тестовая заявка",
            client_identifier: str = None,
            to_start_at_from: str = None,
            cargo_places: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Создание черновика заявки на доставку груза

        Args:
            cargo_places: Список грузомест в формате [{"id": 123, "arrivalPoint": 1, "departurePoint": 2}, ...]
        """
        if body_types is None:
            body_types = [3, 4, 7, 8]

        if route is None:
            route = []

        if to_start_at_from is None:
            to_start_at_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if client_identifier is None:
            client_identifier = f"CDR-draft-{datetime.now().strftime('%d%m%Y-%H%M%S')}"

        payload = {
            "deliveryType": delivery_type,
            "deliverySubType": delivery_sub_type,
            "parameters": {
                "orderCategory": 1,
                "bodyTypes": body_types,
                "isDangerousGoods": False,
                "vehicleTypeId": vehicle_type_id,
                "isCornerPillarRequired": False,
                "isStrapRequired": False,
                "isChainRequired": False,
                "isNetRequired": False,
                "isTarpaulinRequired": False,
                "isWheelChockRequired": False,
                "isGPSMonitoringRequired": False,
                "isWoodenFloorRequired": False,
                "isDoppelstockRequired": False,
                "isTakeOutPackageRequired": False,
                "isDriverLoaderRequired": False,
                "orderType": order_type,
                "isHydroliftRequired": False,
                "isPalletJackRequired": False,
                "isConicsRequired": False,
                "isThermographRequired": False,
                "isLiftingValidationRequired": False,
                "pointChangeType": point_change_type,
                "isSanitaryPassportRequired": False,
                "isSanitaryBookRequired": False,
                "requiredDocuments": [],
                "route": route
            },
            "shipmentTasks": [],
            "responsibleEmployees": [],
            "comment": comment,
            "clientIdentifier": client_identifier,
            "innerComment": None,
            "toStartAtFrom": to_start_at_from,
            "toStartAtTill": None,
            "cargoPlaces": cargo_places or [],
            "newCargoPlaces": [],
            "additionalServices": [],
        }

        if cargo_places:
            payload["parameters"]["cargoPlaces"] = cargo_places

        print(f" Payload для создания заявки на доставку:")
        print(f"   clientIdentifier: {client_identifier}")
        print(f"   deliverySubType: {delivery_sub_type}")
        print(f"   route points: {len(route)}")
        if cargo_places:
            print(f"   cargoPlaces: {len(cargo_places)}")

        response = requests.post(
            f"{self.base_url}/cargo-delivery-requests/create",
            headers=self.headers,
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, \
            f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        assert "id" in result and result.get("id") is not None, \
            f"Отсутствует поле 'id' в ответе. Ответ: {result}"

        assert "requestNr" in result and result.get("requestNr") is not None, \
            f"Отсутствует поле 'requestNr' в ответе. Ответ: {result}"

        print(f"✅ Черновик создан: ID={result.get('id')}, requestNr={result.get('requestNr')}")

        return result

    def get_cdr_details(self, cdr_id: str) -> Dict[str, Any]:
        """
        Получает детали заявки по ID

        Args:
            cdr_id: ID заявки (UUID)

        Returns:
            Ответ API с деталями заявки
        """
        url = f"{self.base_url}/cargo-delivery-requests/{cdr_id}/details"

        print(f"\n📋 Запрос деталки заявки: {url}")

        response = requests.get(
            url,
            headers=self.headers,
            timeout=30
        )

        assert response.status_code == 200, \
            f"Ожидался статус 200 для CDR {cdr_id}, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        assert "id" in result and result.get("id") is not None, \
            f"Отсутствует поле 'id' в ответе для CDR {cdr_id}. Ответ: {result}"

        assert result.get("id") == cdr_id, \
            f"ID в ответе ({result.get('id')}) не совпадает с запрошенным ({cdr_id})"

        assert "status" in result, \
            f"Отсутствует поле 'status' в ответе для CDR {cdr_id}. Ответ: {result}"

        assert "cargoPlaces" in result, \
            f"Отсутствует поле 'cargoPlaces' в ответе для CDR {cdr_id}. Ответ: {result}"

        print(f"✅ Получены детали CDR {cdr_id}: status={result.get('status')}")

        return result

    def take_cdr(self, cdr_id: str) -> Dict[str, Any]:
        """
        Принимает обязательства по заявке

        Args:
            cdr_id: ID заявки (UUID)

        Returns:
            Ответ API
        """
        url = f"{self.base_url}/cargo-delivery-requests/{cdr_id}/take"

        print(f"\n📋 Принятие обязательств по заявке: {url}")

        response = requests.get(
            url,
            headers=self.headers,
            timeout=30
        )

        assert response.status_code == 200, \
            f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.text}"

        result = response.json()

        if "id" in result:
            assert result.get("id") == cdr_id, \
                f"ID в ответе ({result.get('id')}) не совпадает с запрошенным ({cdr_id})"

        print(f"✅ Обязательства приняты для CDR {cdr_id}")

        return result



