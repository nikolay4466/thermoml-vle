"""Интерпретация извлечённых ThermoML-величин как T, P и составов фаз.

Это промежуточная реализация: пока нет нормализации порядка компонентов,
проверок полноты VLE, конвертации произвольных единиц и итоговых CSV.
"""

from extractor import extract_points, get_constraints


def put_value(point, field, value, source, org_num=None):
    """Добавить значение, не перезаписывая противоречащие измерения."""
    if value is None:
        point["unmapped"].append({"source": source, "reason": "Нет числа"})
        return

    if field in ("x_by_orgnum", "y_by_orgnum"):
        target = point[field]
        key = f"{field}[{org_num}]"
        value_key = org_num
    else:
        target = point
        key = field
        value_key = field

    old = target.get(value_key)
    if old is not None and abs(old - value) > 1e-8:
        raise ValueError(f"Противоречие для {key}: {old} и {value} ({source})")

    target[value_key] = value
    point["origins"].setdefault(key, []).append(source)


def add_quantity(point, item, source):
    """Преобразовать знакомые типы величин в T, P, x, y; незнакомые сохранить."""
    kind = item.get("type")
    description = (item.get("description") or "").strip().lower()
    phase = (item.get("phase") or "").strip().lower()
    org_num = item.get("nOrgNum")
    value = item.get("value")

    if (kind == "eTemperature" and description == "temperature, k") or description == "boiling temperature, k":
        put_value(point, "temperature_K", value, source)
    elif (kind == "ePressure" and description == "pressure, kpa") or description == "vapor or sublimation pressure, kpa":
        put_value(point, "pressure_kPa", value, source)
    elif kind in (None, "eComponentComposition") and description == "mole fraction":
        if org_num is not None and phase in ("liquid", "gas", "vapor"):
            field = "x_by_orgnum" if phase == "liquid" else "y_by_orgnum"
            put_value(point, field, value, source, org_num)
        else:
            point["unmapped"].append({
                "source": source,
                "item": item,
                "reason": "Не указаны фаза или компонент",
            })
    else:
        point["unmapped"].append({
            "source": source,
            "item": item,
            "reason": "Неизвестный тип величины",
        })


def extract_physical_points(block):
    """Собрать T, P и составы для каждого NumValues без потери источников."""
    raw_points = extract_points(block)
    constraints = get_constraints(block)
    results = []

    for raw in raw_points:
        point = {
            "raw_measurements": raw,
            "raw_constraints": constraints,
            "point_number": raw["point_number"],
            "temperature_K": None,
            "pressure_kPa": None,
            "x_by_orgnum": {},
            "y_by_orgnum": {},
            "origins": {},
            "unmapped": [],
        }

        for i, constraint in enumerate(constraints, 1):
            add_quantity(point, constraint, f"Constraint {i}")

        for variable in raw["variables"]:
            add_quantity(point, variable, f"VariableValue {variable['number']}")

        for prop in raw["properties"]:
            add_quantity(point, prop, f"PropertyValue {prop['number']}")

        results.append(point)

    return results
