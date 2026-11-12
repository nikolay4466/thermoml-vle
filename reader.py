"""Чтение ThermoML JSON и выбор экспериментальных блоков."""

import json
from pathlib import Path


def as_list(value):
    """Привести поле ThermoML к списку (XML->JSON: dict или list)."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_blocks(data):
    return as_list(data.get("PureOrMixtureData"))


def get_block(data, block_number):
    """Найти блок по исходному nPureOrMixtureDataNumber, а не по индексу списка."""
    found = [
        block for block in get_blocks(data)
        if block.get("nPureOrMixtureDataNumber") == block_number
    ]
    if len(found) != 1:
        raise ValueError(
            f"Ожидался один блок с номером {block_number}, найдено: {len(found)}"
        )
    return found[0]
