"""Интерфейс первого студента: список словарей для проверки студентом №2."""
import csv
import json
from pathlib import Path
from identifiers import make_mixture_id
from identifiers import make_dataset_id, make_record_id, normalize_source_file
from reader import as_list, get_blocks
from composition import component_order, apply_composition
from vle_parser import extract_physical_points
from extractor import get_constraints


def load_catalog(path, links_path=None):
    path = Path(path)
    if path.is_dir():
        links_path = links_path or path / 'dataset_components.csv'
        path = path / 'datasets.csv'
    elif links_path is None and (path.parent / 'dataset_components.csv').is_file():
        links_path = path.parent / 'dataset_components.csv'

    result = load_datasets(path)
    if links_path is not None:
        links = load_component_links(links_path)
        for (source, block), metadata in result.items():
            dataset_id = make_dataset_id(source, block)
            metadata['component_links'] = links.get(dataset_id, {})
    return result


def load_component_links(path):
    with open(path, encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter=';', strict=True)
        columns = set(reader.fieldnames or ())
        position = next((name for name in ('original_position', 'source_position', 'local_position', 'component_position')
                         if name in columns), None)
        if position is None or not {'dataset_id', 'local_org_num', 'component_id'} <= columns:
            raise ValueError('dataset_components.csv требует dataset_id, local_org_num, component_id и исходную позицию')
        result = {}
        for row in reader:
            dataset_id, org, component_id = (row[key] for key in ('dataset_id', 'local_org_num', 'component_id'))
            dataset = result.setdefault(dataset_id, {})
            if not all((dataset_id, org, component_id)) or org in dataset:
                raise ValueError(f'Пустая или повторная связь компонента {org} в наборе {dataset_id}')
            dataset[org] = (component_id, int(row[position]))
        return result


def load_datasets(path):
    with open(path, encoding='utf-8-sig', newline='') as stream:
        header = stream.readline()
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=';' if header.count(';') > header.count(',') else ',')
        if not {'source_file', 'data_block'} <= set(reader.fieldnames or ()):
            raise ValueError('Каталог требует source_file и data_block')
        result = {}
        for row in reader:
            key = (normalize_source_file(row['source_file']), str(row['data_block']))
            metadata = {k: v for k, v in row.items() if v and (k in ('dataset_id', 'doi', 'mixture_id') or
                        k.startswith('component_') and k.endswith(('_id', '_orgnum', '_inchikey')))}
            if key in result and result[key] != metadata:
                raise ValueError(f'Противоречивые метаданные каталога: {key}')
            result[key] = metadata
        return result


def parse_document(data, source_file, block_number=None, catalog=None):
    source_file = normalize_source_file(source_file)
    results, seen = [], set()
    for block in get_blocks(data):
        number = block['nPureOrMixtureDataNumber']
        if str(number) in seen:
            raise ValueError(f'Повторяется номер блока {number}')
        seen.add(str(number))
        if block_number is not None and str(number) != str(block_number):
            continue
        metadata = (catalog or {}).get((source_file, str(number)))
        if catalog is not None and metadata is None:
            raise ValueError(f'Нет точного совпадения source_file/data_block в каталоге: {source_file}:{number}')
        dataset_id = make_dataset_id(source_file, number)
        if metadata and metadata.get('dataset_id', dataset_id) != dataset_id:
            raise ValueError('dataset_id каталога не соответствует соглашению SHA256')
        orgs, ids = component_order(data, block, metadata)
        component_ids = [ids[str(org)] for org in orgs]
        mixture_id = make_mixture_id(component_ids) if len(component_ids) >= 2 else None
        if metadata and metadata.get('mixture_id') and metadata['mixture_id'] != mixture_id:
            raise ValueError('mixture_id каталога не соответствует составу блока')
        phases = [phase['ePhase'] for phase in as_list(block.get('PhaseID')) if phase.get('ePhase')]
        for point in extract_physical_points(block):
            point.update(dataset_id=dataset_id, record_id=make_record_id(dataset_id, point['point_number']),
                         source_file=source_file, data_block=number,
                         doi=(data.get('Citation') or {}).get('sDOI'),
                         mixture_id=mixture_id, component_ids=component_ids, phases=phases,
                         catalog_matched=metadata is not None)
            apply_composition(point, orgs, ids)
            point['experiment_mode'] = 'unspecified'
            kinds = {c.get('type') for c in get_constraints(block)}
            if 'eTemperature' in kinds and 'ePressure' not in kinds:
                point['experiment_mode'] = 'isothermal'
            elif 'ePressure' in kinds and 'eTemperature' not in kinds:
                point['experiment_mode'] = 'isobaric'
            results.append(point)
    if block_number is not None and str(block_number) not in seen:
        raise ValueError(f'Не найден блок {block_number}')
    return results


def write_points_csv(path, points):
    fields = dict.fromkeys(('record_id', 'dataset_id', 'source_file', 'data_block',
                            'point_number', 'doi', 'mixture_id', 'component_ids', 'phases'))
    for point in points:
        fields.update(dict.fromkeys(point))
    with open(path, 'x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), delimiter=';')
        writer.writeheader()
        for point in points:
            row = point.copy()
            for key, value in point.items():
                if key in ('component_ids', 'phases'):
                    row[key] = ';'.join(value)
                elif isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(row)
