"""Вывод карточки в Markdown для копирования."""


def to_markdown(c: dict) -> str:
    L = [f"# {c['product_name']}", ""]
    flag = "требует уточнений" if c["status"] != "ok" else "готов к проверке"
    L += [f"Статус черновика: **{flag}**. Производитель: {c['manufacturer']}.", ""]

    if c["clarifications"] or c["warnings"]:
        L += ["## Что проверить перед публикацией", ""]
        L += [f"- {x}" for x in c["clarifications"]]
        L += [f"- ВНИМАНИЕ: {x}" for x in c["warnings"]]
        L.append("")

    L += ["## SEO-заголовок", "", c["seo_title"], "", f"({c['seo_title_length']} симв.)", ""]
    L += ["## SEO-описание", "", c["seo_description"], "", f"({c['seo_description_length']} симв.)", ""]

    L += ["## Ключевые характеристики", "", "| Характеристика | Значение | Источник |", "|---|---|---|"]
    src = {"specs": "specs", "description": "из описания"}
    L += [f"| {s['name']} | {s['value']} | {src[s['source']]} |" for s in c["key_specs"]]
    L += [f"| {a} | данных нет | нужно запросить |" for a in c["absent_specs"]]
    L.append("")

    L += ["## Поисковые запросы", ""] + [f"- {q}" for q in c["search_queries"]] + [""]
    cb = c["commercial_block"]
    L += ["## Для менеджера", "", "**Кому подходит:**"] + [f"- {x}" for x in cb["suitable_for"]]
    L += ["", "**Какие задачи решает:**"] + [f"- {x}" for x in cb["tasks_solved"]] + [""]
    return "\n".join(L)
