"""Стабильные идентификаторы; source_file задаётся относительно корня архива."""
import hashlib
from pathlib import PurePosixPath


def normalize_source_file(source_file):
    value = str(source_file).replace("\\", "/")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ":" in value or ".." in path.parts or str(path) == ".":
        raise ValueError("source_file должен быть относительным путём внутри архива")
    return path.as_posix()


def make_dataset_id(source_file, data_block):
    key = f"{normalize_source_file(source_file)}:{data_block}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_record_id(dataset_id, point_number):
    return hashlib.sha256(f"{dataset_id}:{point_number}".encode("utf-8")).hexdigest()

def make_component_id(compound):
    key = compound.get("sStandardInChIKey")
    if key and len(key) == 27:
        return key
    inchi = compound.get("sStandardInChI")
    if inchi:
        return hashlib.sha256(inchi.encode("utf-8")).hexdigest()
    names = compound.get("sCommonName") or ""
    name = next(iter(names), "") if isinstance(names, list) else names
    value = name + (compound.get("sFormulaMolec") or "")
    return "UNRESOLVED_" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_mixture_id(component_ids):
    return hashlib.sha256(";".join(sorted(component_ids)).encode("utf-8")).hexdigest()
