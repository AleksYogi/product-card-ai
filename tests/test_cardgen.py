import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cardgen import checks, generator, render, validate

EX = Path(__file__).parent.parent / "examples"


def fake_client(*payloads):
    """Провайдер-заглушка: отдаёт ответы по очереди (dict -> JSON, str как есть)."""
    it = iter(payloads)

    class P:
        model = "fake"

        def complete(self, messages):
            x = next(it)
            return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)

    return P()


def good_raw(desc_len=900, **over):
    raw = {
        "seo_title": "Манометр DM 02 0–1,6 МПа G1/2",
        "seo_description": "а" * desc_len,
        "description_specs": [],
        "missing_specs": ["рабочая температура"],
        "search_queries": ["манометр dm 02", "манометр 1,6 мпа", "манометр g1/2"],
        "commercial_block": {"suitable_for": ["монтажные организации"], "tasks_solved": ["контроль давления"]},
        "clarifications": [],
    }
    raw.update(over)
    return raw


def product(name="Манометр DM 02"):
    p, why = validate.parse_product(json.loads((EX / "input/manometer_dm02.json").read_text()))
    assert why is None
    return p


def test_broken_json():
    with pytest.raises(validate.InputError, match="некорректный JSON"):
        validate.load_raw(EX / "bad/broken.json")


def test_empty_and_wrong_types():
    items = validate.load_raw(EX / "bad/empty_fields.json")
    reasons = [validate.parse_product(i)[1] for i in items]
    assert "name" in reasons[0]
    assert "specs" in reasons[1]
    assert "нет ни характеристик" in reasons[2]
    assert validate.parse_product("строка")[1] is not None


def test_missing_fields_detected_by_code():
    raw = json.loads((EX / "input/thermometer_demo.json").read_text())
    p, _ = validate.parse_product(raw)
    assert p.missing_fields == ["производитель"]
    assert set(p.empty_specs) == {"класс точности", "интерфейсы"}
    assert p.as_prompt_dict()["specs"]["интерфейсы"] == "данных нет"


def test_unknown_numbers_flagged():
    p = product()
    ok = good_raw()
    assert checks.unknown_numbers(ok, checks.source_numbers(p.as_prompt_dict())) == []
    bad = good_raw(seo_title="Манометр DM 02 16 бар")
    assert checks.unknown_numbers(bad, checks.source_numbers(p.as_prompt_dict())) == ["16"]


def test_description_spec_needs_real_quote():
    desc = "Корпус из стали, рабочая температура до 60 °C."
    items = [
        {"name": "t", "value": "до 60 °C", "quote": "рабочая температура до 60 °C"},
        {"name": "fake", "value": "IP65", "quote": "степень защиты IP65"},
        {"name": "wrongnum", "value": "до 80 °C", "quote": "рабочая температура до 60 °C"},
    ]
    kept, dropped = checks.verified_description_specs(items, desc)
    assert [k["name"] for k in kept] == ["t"]
    assert dropped == ["fake", "wrongnum"]


def test_pipeline_ok_and_markdown():
    card = generator.generate_card(fake_client(good_raw()), product())
    assert card["seo_description_length"] == 900
    assert {"name": "класс точности", "value": "1,5", "source": "specs"} in card["key_specs"]
    md = render.to_markdown(card)
    assert "рабочая температура | данных нет" in md


def test_retry_on_length_then_ok():
    card = generator.generate_card(fake_client(good_raw(desc_len=300), good_raw()), product())
    assert card["warnings"] == []


def test_length_still_wrong_gives_warning():
    card = generator.generate_card(fake_client(good_raw(300), good_raw(300)), product())
    assert card["status"] == "needs_clarification"
    assert any("seo_description" in w for w in card["warnings"])


def test_tolerant_json_parsing():
    wrapped = "Вот результат:\n```json\n" + json.dumps(good_raw(), ensure_ascii=False) + "\n```"
    assert generator.generate_card(fake_client(wrapped), product())["seo_description_length"] == 900


@pytest.mark.parametrize("bad", ["просто текст", "{не json}", json.dumps({"seo_title": "x"})])
def test_bad_model_output_raises(bad):
    with pytest.raises(generator.LLMError):
        generator.generate_card(fake_client(bad), product())
