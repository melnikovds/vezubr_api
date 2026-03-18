import os
from typing import Literal, cast

_RAW_DOMAIN = os.getenv("DOMAIN", "com")

if _RAW_DOMAIN not in {"dev", "com", "ru"}:
    raise ValueError(f"Недопустимое значение DOMAIN: '{_RAW_DOMAIN}'. Допустимые: dev, com, ru")

DOMAIN: Literal['dev', 'com', 'ru'] = cast(Literal['dev', 'com', 'ru'], _RAW_DOMAIN)

BASE_URL = f"https://api.vezubr.{DOMAIN}/v1/api"
EXTERNAL_URL = f"https://api.vezubr.{DOMAIN}/v1/api-ext"

TIMEOUT = 10

CLIENT_ID= 2448
FORWARDER_ID = 2447
PRODUCER_ID= 2449

accounts = {
    "lkz": {
        "email": "coppernaval@somoj.com",
        "password": "/4lken&_K`"
    },
    "lke": {
        "email": "magentadael@somoj.com",
        "password": "qmf=8E5S8("
    },
    "lkp": {
        "email": "realistic3816@somoj.com",
        "password": "3>fDSBVakL"
    },
    "lkz_ext": {
        "email": "florenzateal@powerscrews.com",
        "password": "1n-T2v4T"
    },
    "lke_ext": {
        "email": "brinnplum@dollicons.com",
        "password": "bZLFsHp9"
    },
    "lkp_ext": {
        "email": "delores9604@dollicons.com",
        "password": "SUHH5Rs7"
    },
}