"""Извлечение чисел и их описаний без интерпретации как T/P/x/y."""

from reader import as_list


def variable_info(item):
    variable_id = item.get("VariableID", {})
    variable_types = variable_id.get("VariableType", {})
    type_name = next((k for k in variable_types if k != "tml_elements"), None)

    return {
        "type": type_name,
        "description": variable_types.get(type_name) if type_name else None,
        "phase": item.get("VarPhaseID", {}).get("eVarPhase"),
        "nOrgNum": variable_id.get("RegNum", {}).get("nOrgNum"),
    }


def property_info(item):
    groups = item.get("Property-MethodID", {}).get("PropertyGroup", {})
    group_name = next((k for k in groups if k != "tml_elements"), None)
    group_data = groups.get(group_name, {}) if group_name else {}

    return {
        "group": group_name,
        "description": group_data.get("ePropName"),
        "phase": item.get("PropPhaseID", {}).get("ePropPhase"),
        "nOrgNum": item.get("RegNum", {}).get("nOrgNum"),
    }


def get_definitions(block):
    """Номера Variable/Property -> описания величин."""
    variables = {}
    for item in as_list(block.get("Variable")):
        number = item["nVarNumber"]
        if number in variables:
            raise ValueError(f"Повторяется nVarNumber={number}")
        variables[number] = variable_info(item)

    properties = {}
    for item in as_list(block.get("Property")):
        number = item["nPropNumber"]
        if number in properties:
            raise ValueError(f"Повторяется nPropNumber={number}")
        properties[number] = property_info(item)

    return variables, properties


def get_constraints(block):
    """Постоянные условия, применимые ко всем NumValues данного блока."""
    constraints = []

    for item in as_list(block.get("Constraint")):
        constraint_id = item.get("ConstraintID", {})
        types = constraint_id.get("ConstraintType", {})
        names = [key for key in types if key != "tml_elements"]

        if len(names) != 1:
            raise ValueError(f"Неоднозначный ConstraintType: {types}")

        name = names[0]
        constraints.append({
            "type": name,
            "description": types[name],
            "phase": item.get("ConstraintPhaseID", {}).get("eConstraintPhase"),
            "nOrgNum": constraint_id.get("RegNum", {}).get("nOrgNum"),
            "value": item.get("nConstraintValue"),
        })

    return constraints


def extract_points(block):
    """Собрать значения в рамках каждого NumValues, сохранив описания."""
    variables, properties = get_definitions(block)
    points = []

    for point_number, raw_point in enumerate(as_list(block.get("NumValues")), 1):
        point = {"point_number": point_number, "variables": [], "properties": []}

        for item in as_list(raw_point.get("VariableValue")):
            number = item["nVarNumber"]
            if number not in variables:
                raise ValueError(f"Точка {point_number}: неизвестный nVarNumber={number}")
            point["variables"].append({
                "number": number,
                "value": item.get("nVarValue"),
                **variables[number],
            })

        for item in as_list(raw_point.get("PropertyValue")):
            number = item["nPropNumber"]
            if number not in properties:
                raise ValueError(f"Точка {point_number}: неизвестный nPropNumber={number}")
            point["properties"].append({
                "number": number,
                "value": item.get("nPropValue"),
                "uncertainty": item.get("CombinedUncertainty"),
                **properties[number],
            })

        points.append(point)

    return points
