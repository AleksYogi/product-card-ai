"""Проверки результата модели кодом: длины, выдуманные числа, цитаты из описания."""
import json
import re

TITLE_MAX = 70
DESC_MIN, DESC_MAX = 800, 1200
QUERIES_MIN, QUERIES_MAX = 3, 5

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUM.findall(text)}


def source_numbers(prompt_dict: dict) -> set[str]:
    return numbers(json.dumps(prompt_dict, ensure_ascii=False))


def length_problems(card: dict) -> list[str]:
    problems = []
    t, d = len(card["seo_title"]), len(card["seo_description"])
    if t > TITLE_MAX:
        problems.append(f"seo_title {t} символов, нужно не больше {TITLE_MAX}")
    if not DESC_MIN <= d <= DESC_MAX:
        problems.append(f"seo_description {d} символов, нужно {DESC_MIN}-{DESC_MAX}")
    if not QUERIES_MIN <= len(card["search_queries"]) <= QUERIES_MAX:
        problems.append(f"search_queries: {len(card['search_queries'])} шт., нужно {QUERIES_MIN}-{QUERIES_MAX}")
    return problems


def _all_generated_text(card: dict) -> str:
    cb = card["commercial_block"]
    parts = [card["seo_title"], card["seo_description"], *card["search_queries"],
             *cb["suitable_for"], *cb["tasks_solved"]]
    return "\n".join(parts)


def unknown_numbers(card: dict, allowed: set[str]) -> list[str]:
    return sorted(numbers(_all_generated_text(card)) - allowed, key=float)


def verified_description_specs(items: list[dict], description: str) -> tuple[list[dict], list[str]]:
    """Оставляет только характеристики, чья цитата дословно есть в описании, а числа значения есть в цитате."""
    norm = " ".join(description.split())
    kept, dropped = [], []
    for it in items:
        quote = " ".join(it["quote"].split())
        if quote and quote in norm and numbers(it["value"]) <= numbers(quote):
            kept.append(it)
        else:
            dropped.append(it["name"])
    return kept, dropped
