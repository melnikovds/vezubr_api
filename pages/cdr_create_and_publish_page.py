import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class CargoDeliveryRequestClient:
    """
    Клиент для работы с эндпоинтом /cargo-delivery-requests/create-and-publish
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
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

        if response.status_code != 200:
            print(f"❌ Ошибка создания заявки: {response.status_code}")
            print(f"Ответ: {response.text}")
            print(f"Запрос: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            response.raise_for_status()

        result = response.json()
        print(f"✅ Заявка создана: ID={result.get('id')}, requestNr={result.get('requestNr')}")
        return result