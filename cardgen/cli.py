"""Запуск: python -m cardgen файл.json [файл2.json ...] [-o output]"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import generator, providers, render, validate


def _slug(text: str) -> str:
    return re.sub(r"[^\w-]+", "_", text.lower()).strip("_")[:50] or "product"


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Черновик карточки товара КИП по JSON")
    ap.add_argument("files", nargs="+", type=Path, help="JSON с товаром или списком товаров")
    ap.add_argument("-o", "--out", type=Path, default=Path("output"), help="папка результата (по умолчанию output)")
    ap.add_argument("--provider", default=os.environ.get("CARDGEN_PROVIDER", "anthropic"),
                    choices=list(providers.DEFAULTS), help="anthropic (прямой API) или closerouter")
    ap.add_argument("--model", default=os.environ.get("CARDGEN_MODEL"), help="по умолчанию своя для провайдера")
    args = ap.parse_args(argv)

    try:
        provider = providers.make_provider(args.provider, args.model)
    except providers.LLMError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for path in args.files:
        try:
            items = validate.load_raw(path)
        except validate.InputError as e:
            print(f"[{path.name}] ОШИБКА ВХОДА: {e}", file=sys.stderr)
            failed += 1
            continue
        for i, raw in enumerate(items, 1):
            tag = f"{path.name}#{i}"
            product, why = validate.parse_product(raw)
            if product is None:
                print(f"[{tag}] ПРОПУЩЕН: {why}", file=sys.stderr)
                failed += 1
                continue
            try:
                card = generator.generate_card(provider, product)
            except providers.LLMError as e:
                print(f"[{tag}] ОШИБКА МОДЕЛИ: {e}", file=sys.stderr)
                failed += 1
                continue
            base = args.out / _slug(path.stem if len(items) == 1 else f"{path.stem}_{i}")
            base.with_suffix(".json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
            base.with_suffix(".md").write_text(render.to_markdown(card), encoding="utf-8")
            print(f"[{tag}] {card['status']} -> {base}.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
