# Пример запуска теста с 50 грузоместами
pytest tests/test_cargo_create_or_update_list_lkz.py --cargo-count 50

или

python -m pytest -s -v -k test_create_cdr_with_cargo_places_lkz --cargo-count 50
