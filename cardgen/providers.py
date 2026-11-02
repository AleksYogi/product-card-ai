"""Провайдеры LLM. Оба возвращают текст ответа; разбор и проверку JSON делает generator.

anthropic    - прямой API Anthropic, ответ по JSON-схеме (output_config.format).
closerouter  - OpenAI-совместимый посредник. Structured output у него не используем
               (см. урок смена-llm-провайдера): схема уходит в промпт, ответ проверяет код.
"""
import json
import os

import anthropic
import openai

from .prompts import RESPONSE_SCHEMA, SYSTEM_PROMPT

DEFAULTS = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-opus-5-5"),
    "closerouter": ("CLOSEROUTER_API_KEY", "anthropic/claude-sonnet-5.5"),
}
CLOSEROUTER_URL = "https://api.closerouter.dev/v1"


class LLMError(Exception):
    """Ошибка обращения к модели, понятная пользователю."""


def default_model(provider: str) -> str:
    return DEFAULTS[provider][1]


class AnthropicProvider:
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic(timeout=120.0, max_retries=3)

    def complete(self, messages: list[dict]) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=8000, system=SYSTEM_PROMPT, messages=messages,
                output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
            )
        except anthropic.AuthenticationError as e:
            raise LLMError("API отклонил ключ (401): проверьте ANTHROPIC_API_KEY") from e
        except anthropic.NotFoundError as e:
            raise LLMError(f"модель {self.model} не найдена (404)") from e
        except anthropic.RateLimitError as e:
            raise LLMError("превышен лимит запросов (429), повторите позже") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"нет связи с API: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"ошибка API {e.status_code}: {e.message}") from e
        if resp.stop_reason == "refusal":
            raise LLMError("модель отказалась отвечать на этот запрос")
        if resp.stop_reason == "max_tokens":
            raise LLMError("ответ обрезан по max_tokens")
        return next((b.text for b in resp.content if b.type == "text"), "")


class CloseRouterProvider:
    SCHEMA_HINT = (
        "\n\nФОРМАТ ОТВЕТА. Верни только один JSON-объект, без markdown и пояснений, "
        "строго по этой JSON-схеме:\n" + json.dumps(RESPONSE_SCHEMA, ensure_ascii=False)
    )

    def __init__(self, model: str):
        self.model = model
        self.client = openai.OpenAI(
            base_url=os.environ.get("CLOSEROUTER_URL", CLOSEROUTER_URL),
            api_key=os.environ["CLOSEROUTER_API_KEY"], timeout=120.0, max_retries=3,
        )

    def complete(self, messages: list[dict]) -> str:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT + self.SCHEMA_HINT}, *messages]
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs, temperature=0, max_tokens=8000)
        except openai.AuthenticationError as e:
            raise LLMError("роутер отклонил ключ (401): проверьте CLOSEROUTER_API_KEY") from e
        except openai.NotFoundError as e:
            raise LLMError(f"модель {self.model} не найдена (404)") from e
        except openai.RateLimitError as e:
            raise LLMError("превышен лимит запросов (429), повторите позже") from e
        except openai.APIConnectionError as e:
            raise LLMError(f"нет связи с API: {e}") from e
        except openai.APIStatusError as e:
            raise LLMError(f"ошибка API {e.status_code}: {e.message}") from e
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            raise LLMError("ответ обрезан по max_tokens")
        return choice.message.content or ""


def make_provider(name: str, model: str | None = None):
    if name not in DEFAULTS:
        raise LLMError(f"неизвестный провайдер {name!r}: доступны {', '.join(DEFAULTS)}")
    key_var, default = DEFAULTS[name]
    if not os.environ.get(key_var):
        raise LLMError(f"не задан {key_var}: скопируйте .env.example в .env и впишите ключ")
    cls = AnthropicProvider if name == "anthropic" else CloseRouterProvider
    return cls(model or default)
