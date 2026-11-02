"""Вызов LLM и сборка итоговой карточки."""
import json

from . import checks
from .prompts import RESPONSE_SCHEMA, SYSTEM_PROMPT, retry_message, user_message
from .validate import Product

from .providers import LLMError  # noqa: F401  (реэкспорт для CLI и тестов)

_REQUIRED = {
    "seo_title": str, "seo_description": str, "description_specs": list, "missing_specs": list,
    "search_queries": list, "commercial_block": dict, "clarifications": list,
}


def parse_response(text: str) -> dict:
    """Достаёт JSON из ответа (терпит ```-обёртку и лишний текст) и проверяет форму."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("модель вернула ответ без JSON")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"модель вернула невалидный JSON: {e}") from e
    for key, typ in _REQUIRED.items():
        if not isinstance(data.get(key), typ):
            raise LLMError(f"в ответе модели нет поля {key} нужного типа")
    cb = data["commercial_block"]
    if not all(isinstance(cb.get(k), list) for k in ("suitable_for", "tasks_solved")):
        raise LLMError("в commercial_block нет suitable_for / tasks_solved")
    for it in data["description_specs"]:
        if not (isinstance(it, dict) and all(isinstance(it.get(k), str) for k in ("name", "value", "quote"))):
            raise LLMError("description_specs: элемент без name/value/quote")
    return data


def _call(provider, messages: list[dict]) -> dict:
    return parse_response(provider.complete(messages))


def generate_card(provider, product: Product) -> dict:
    prompt_dict = product.as_prompt_dict()
    messages = [{"role": "user", "content": user_message(prompt_dict)}]
    raw = _call(provider, messages)

    problems = checks.length_problems(raw)
    if problems:  # одна попытка исправления, дальше честное предупреждение
        messages += [
            {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
            {"role": "user", "content": retry_message(problems)},
        ]
        raw = _call(provider, messages)
        problems = checks.length_problems(raw)

    warnings = [f"не удалось уложиться в ограничения: {p}" for p in problems]

    unknown = checks.unknown_numbers(raw, checks.source_numbers(prompt_dict))
    if unknown:
        warnings.append("в тексте есть числа, которых нет во входных данных, проверьте вручную: " + ", ".join(unknown))

    desc_specs, dropped = checks.verified_description_specs(raw["description_specs"], product.description)
    if dropped:
        warnings.append("отброшены характеристики без подтверждающей цитаты: " + ", ".join(dropped))

    key_specs = [{"name": k, "value": v or "данных нет", "source": "specs"} for k, v in product.specs.items()]
    key_specs += [{**{"name": s["name"], "value": s["value"]}, "source": "description"} for s in desc_specs]

    clarifications = list(raw["clarifications"])
    clarifications = [f"нет поля: {m}" for m in product.missing_fields] + clarifications
    clarifications += [f"пустое значение характеристики: {k}" for k in product.empty_specs]

    status = "needs_clarification" if (clarifications or warnings) else "ok"
    return {
        "status": status,
        "product_name": product.name,
        "manufacturer": product.manufacturer or "данных нет",
        "seo_title": raw["seo_title"],
        "seo_title_length": len(raw["seo_title"]),
        "seo_description": raw["seo_description"],
        "seo_description_length": len(raw["seo_description"]),
        "key_specs": key_specs,
        "absent_specs": [m for m in raw["missing_specs"]],
        "search_queries": raw["search_queries"],
        "commercial_block": raw["commercial_block"],
        "clarifications": clarifications,
        "warnings": warnings,
        "model": provider.model,
    }
