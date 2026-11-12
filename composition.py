"""Явное сопоставление nOrgNum с порядком компонентов; исходные доли сохраняются."""
from reader import as_list
from identifiers import make_component_id


def component_order(data, block, metadata=None):
    compounds = {str(c['RegNum']['nOrgNum']): c for c in as_list(data.get('Compound'))}
    orgs = [c['RegNum']['nOrgNum'] for c in as_list(block.get('Component'))]
    if len(set(map(str, orgs))) != len(orgs):
        raise ValueError('Повторяется компонент блока')
    ids = {str(org): make_component_id(compounds.get(str(org), {})) for org in orgs}
    links = (metadata or {}).get('component_links')
    if links is not None:
        if len(links) != len(orgs) or set(links) != set(map(str, orgs)):
            raise ValueError('dataset_components.csv не покрывает компоненты блока')
        for position, org in enumerate(orgs, 1):
            component_id, original_position = links[str(org)]
            if original_position != position:
                raise ValueError(f'Неверная исходная позиция компонента {org}')
            if ids[str(org)] != component_id and not (
                ids[str(org)].startswith('UNRESOLVED_') and component_id.startswith('UNRESOLVED_')
            ):
                raise ValueError(f'Несовпадение component_id для компонента {org}')
            ids[str(org)] = component_id
    elif metadata and any(k.startswith('component_') for k in metadata):
        ordered = []
        for i in range(1, len(orgs) + 1):
            explicit = metadata.get(f'component_{i}_orgnum')
            key = metadata.get(f'component_{i}_inchikey') or metadata.get(f'component_{i}_id')
            matches = [n for n in orgs if (str(n) == str(explicit) if explicit is not None else
                       key and ids[str(n)] == key)]
            if len(matches) != 1:
                raise ValueError(f'Нельзя однозначно сопоставить component_{i} каталога')
            ordered.append(matches[0])
        if len(set(map(str, ordered))) != len(orgs):
            raise ValueError('Каталог повторно использует один компонент')
        for i, org in enumerate(ordered, 1):
            supplied = metadata.get(f'component_{i}_id')
            if supplied and supplied != ids[str(org)]:
                raise ValueError(f'Несовпадение component_id для компонента {org}')
    return sorted(orgs, key=lambda org: ids[str(org)]), ids


def apply_composition(point, orgs, ids):
    for i, org in enumerate(orgs, 1):
        point[f'component_{i}_orgnum'] = org
        point[f'component_{i}_id'] = ids[str(org)]
        point[f'component_{i}_status'] = 'unresolved' if ids[str(org)].startswith('UNRESOLVED_') else 'resolved'
    for phase, field in [('x', 'x_by_orgnum'), ('y', 'y_by_orgnum')]:
        values = {str(k): v for k, v in point[field].items()}
        if set(values) - set(map(str, orgs)):
            raise ValueError('Состав ссылается на компонент вне блока')
        if len(orgs) != 2:
            continue
        for i, org in enumerate(orgs, 1):
            key = f'{phase}{i}'
            point[key] = values.get(str(org))
            if point[key] is not None:
                point['origins'][key] = list(point['origins'].get(f'{field}[{org}]', []))
        for i, other in [(1, 2), (2, 1)]:
            key, other_key = f'{phase}{i}', f'{phase}{other}'
            if point[key] is None and point[other_key] is not None:
                point[key] = 1 - point[other_key]
                point['origins'][key] = [f'derived: 1 - {other_key}']
