"""Загрузка и проверка входных данных. Без обращения к LLM: недостающие поля определяет код."""
import json
from dataclasses import dataclass, field
from pathlib import Path

FIELD_LABELS = {
    "name": "название товара",
    "manufacturer": "производитель",
    "specs": "характеристики (specs)",
    "description": "описание",
}


class InputError(Exception):
    """Файл не читается или не является JSON."""


@dataclass
class Product:
    name: str
    manufacturer: str
    specs: dict[str, str]
    description: str
    missing_fields: list[str] = field(default_factory=list)
    empty_specs: list[str] = field(default_factory=list)

    def as_prompt_dict(self) -> dict:
        return {
            "name": self.name,
            "manufacturer": self.manufacturer or "данных нет",
            "specs": {k: (v or "данных нет") for k, v in self.specs.items()},
            "description": self.description or "данных нет",
        }


def load_raw(path: Path) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"не удалось прочитать файл: {e}") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"некорректный JSON (строка {e.lineno}, позиция {e.colno}): {e.msg}") from e
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list) and data:
        return data
    raise InputError("ожидается JSON-объект товара или непустой список объектов")


def _clean(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse_product(raw) -> tuple[Product | None, str | None]:
    """Возвращает (товар, None) или (None, причина отказа)."""
    if not isinstance(raw, dict):
        return None, "товар должен быть JSON-объектом"
    name = _clean(raw.get("name"))
    if not name:
        return None, "поле name пустое или отсутствует: без названия карточку не создать"

    raw_specs = raw.get("specs")
    if raw_specs is None:
        raw_specs = {}
    if not isinstance(raw_specs, dict):
        return None, "поле specs должно быть объектом вида {\"характеристика\": \"значение\"}"
    specs = {_clean(k): _clean(v) for k, v in raw_specs.items() if _clean(k)}
    description = _clean(raw.get("description"))
    manufacturer = _clean(raw.get("manufacturer"))

    if not any(specs.values()) and not description:
        return None, "нет ни характеристик, ни описания: карточку не на чем строить"

    missing = []
    if not manufacturer:
        missing.append(FIELD_LABELS["manufacturer"])
    if not any(specs.values()):
        missing.append(FIELD_LABELS["specs"])
    if not description:
        missing.append(FIELD_LABELS["description"])
    empty_specs = [k for k, v in specs.items() if not v]
    return Product(name, manufacturer, specs, description, missing, empty_specs), None
