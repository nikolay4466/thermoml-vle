"""Запуск текущей версии парсера на одном экспериментальном блоке."""
import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

from reader import load_json, get_blocks
from pipeline import parse_document, load_catalog, write_points_csv



def main():
    default_file = Path(__file__).resolve().parent / "data" / "j.fluid.2004.02.021.json"
    parser = argparse.ArgumentParser(description="Извлечение T/P/x/y из блока ThermoML JSON")
    parser.add_argument("--file", type=Path, default=default_file, help="Путь к ThermoML JSON")
    parser.add_argument("--block", type=int, help="Исходный номер блока; по умолчанию все")
    parser.add_argument("--root", type=Path, help="Корень архива для относительного source_file")
    parser.add_argument("--catalog", type=Path, help="CSV первой пары")
    parser.add_argument("--dataset-components", type=Path, help="Отдельный путь к dataset_components.csv")
    parser.add_argument("--output", type=Path, help="Путь к новому CSV с извлечёнными точками")
    args = parser.parse_args()
    if args.dataset_components and not args.catalog:
        parser.error("--dataset-components требует --catalog")
    if args.file.resolve() != default_file and args.root is None:
        parser.error("Укажите корень архива через --root")

    data = load_json(args.file)
    root = (args.root or default_file.parent.parent).resolve()
    try:
        source_file = args.file.resolve().relative_to(root).as_posix()
    except ValueError:
        parser.error("--file должен находиться внутри --root")
    points = parse_document(data, source_file, args.block,
                            load_catalog(args.catalog, args.dataset_components) if args.catalog else None)

    if args.output:
        write_points_csv(args.output, points)

    print("Всего экспериментальных блоков:", len(get_blocks(data)))
    print("Выбран блок:", args.block or "все")
    print("Экспериментальных записей:", len(points))
    if points:
        print("Первая запись:")
        print(json.dumps(points[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
