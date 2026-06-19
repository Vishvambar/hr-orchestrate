from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from .contracts import ChallengeContract, RetrievalHit
from .prompts import build_messages
from .rules import (
    build_direct_justification,
    build_direct_response,
    classify_request_type,
    field_kind,
    infer_product_area,
)
from .utils import project_root


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    name: str
    model: str

    def generate(
        self,
        contract: ChallengeContract,
        row: dict[str, str],
        query: str,
        hits: list[RetrievalHit],
    ) -> dict[str, str]: ...


@dataclass(slots=True)
class RuleBasedProvider:
    name: str = "rule-based"
    model: str = "deterministic-baseline"

    def generate(
        self,
        contract: ChallengeContract,
        row: dict[str, str],
        query: str,
        hits: list[RetrievalHit],
    ) -> dict[str, str]:
        area_field = next(
            (
                field
                for field in contract.output_fields
                if field_kind(field.name) == "product_area"
            ),
            None,
        )
        request_type_field = next(
            (
                field
                for field in contract.output_fields
                if field_kind(field.name) == "request_type"
            ),
            None,
        )
        product_area = infer_product_area(
            query, hits, area_field.allowed_values if area_field else []
        )
        request_type = classify_request_type(
            query, request_type_field.allowed_values if request_type_field else []
        )

        draft: dict[str, str] = {}
        for field in contract.output_fields:
            kind = field_kind(field.name)
            if kind == "status":
                draft[field.name] = "replied"
            elif kind == "product_area":
                draft[field.name] = product_area
            elif kind == "request_type":
                draft[field.name] = request_type
            elif kind == "response":
                draft[field.name] = build_direct_response(query, hits)
            elif kind == "justification":
                draft[field.name] = build_direct_justification(hits)
        return draft


@dataclass(slots=True)
class CompatibleProviderSpec:
    name: str
    api_key_env: str
    model_env: str
    base_url: str
    default_model: str | None = None
    use_json_mode: bool = False


@dataclass(slots=True)
class OpenAICompatibleProvider:
    name: str
    api_key: str
    base_url: str
    model: str
    use_json_mode: bool = False
    max_tokens: int = 900
    retries: int = 3
    quiet_delay_seconds: float = 0.6
    backoff_seconds: float = 2.0

    def generate(
        self,
        contract: ChallengeContract,
        row: dict[str, str],
        query: str,
        hits: list[RetrievalHit],
    ) -> dict[str, str]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "OpenAI-compatible providers require the OpenAI SDK. Run: pip install -e .[openai]"
            ) from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        system_prompt, user_prompt = build_messages(
            contract, row, query, hits, base=project_root()
        )
        messages = _json_messages(system_prompt, user_prompt)

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            if attempt > 1:
                time.sleep(self.backoff_seconds * (attempt - 1))
            try:
                if attempt == 1 and self.quiet_delay_seconds > 0:
                    time.sleep(self.quiet_delay_seconds)
                content = _call_openai_compatible_chat(
                    client,
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    use_json_mode=self.use_json_mode,
                )
                return _parse_json_object(content)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ProviderError(
            f"{self.name} failed after {self.retries} attempts: {last_error}"
        )


@dataclass(slots=True)
class CompatibleFallbackProvider:
    providers: list[OpenAICompatibleProvider] = field(default_factory=list)
    name: str = "auto"
    model: str = "dynamic"
    active_index: int | None = None

    def generate(
        self,
        contract: ChallengeContract,
        row: dict[str, str],
        query: str,
        hits: list[RetrievalHit],
    ) -> dict[str, str]:
        if not self.providers:
            raise ProviderError("No compatible providers are configured.")

        ordered_indexes = list(range(len(self.providers)))
        if self.active_index is not None and 0 <= self.active_index < len(
            self.providers
        ):
            ordered_indexes.remove(self.active_index)
            ordered_indexes.insert(0, self.active_index)

        failures: list[str] = []
        for index in ordered_indexes:
            provider = self.providers[index]
            try:
                result = provider.generate(contract, row, query, hits)
                self.active_index = index
                self.name = f"auto[{provider.name}]"
                self.model = provider.model
                return result
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{provider.name}: {exc}")
                continue

        raise ProviderError("All compatible providers failed: " + " | ".join(failures))


@dataclass(slots=True)
class AnthropicProvider:
    model: str
    name: str = "anthropic"

    def generate(
        self,
        contract: ChallengeContract,
        row: dict[str, str],
        query: str,
        hits: list[RetrievalHit],
    ) -> dict[str, str]:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ProviderError(
                "Anthropic extra not installed. Run: pip install -e .[anthropic]"
            ) from exc

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set.")

        client = Anthropic(api_key=api_key)
        system_prompt, user_prompt = build_messages(
            contract, row, query, hits, base=project_root()
        )
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nMANDATORY: Return ONLY valid JSON matching the required keys. No markdown fences."
        )
        message = client.messages.create(
            model=self.model,
            temperature=0,
            max_tokens=900,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = "\n".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        return _parse_json_object(content)


def _json_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    system_content = (
        system_prompt.rstrip()
        + "\n\nMANDATORY: Return ONLY valid JSON matching the required keys. Do not output markdown fences like ```json."
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]


def _call_openai_compatible_chat(
    client: object,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    use_json_mode: bool,
) -> str:
    request: dict[str, object] = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if use_json_mode:
        request["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**request)
    except Exception as exc:  # noqa: BLE001
        if use_json_mode and _looks_like_response_format_issue(exc):
            request.pop("response_format", None)
            response = client.chat.completions.create(**request)
        else:
            raise

    content = response.choices[0].message.content or "{}"
    return content


def _looks_like_response_format_issue(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "response_format" in message
        or "json_object" in message
        or "unsupported" in message
        or "not support" in message
    )


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json|[a-zA-Z0-9_-]*)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned.strip()


def _stringify_json_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _parse_json_object(content: str) -> dict[str, str]:
    cleaned = _clean_json_content(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ProviderError("Model response did not contain valid JSON.")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ProviderError("Model response JSON was not an object.")
    return {str(key): _stringify_json_value(value) for key, value in parsed.items()}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ProviderError(f"{name} is not set.")
    return value


def _compatible_specs() -> list[CompatibleProviderSpec]:
    return [
        CompatibleProviderSpec(
            name="cerebras",
            api_key_env="CEREBRAS_API_KEY",
            model_env="CEREBRAS_MODEL",
            base_url="https://api.cerebras.ai/v1",
        ),
        CompatibleProviderSpec(
            name="groq",
            api_key_env="GROQ_API_KEY",
            model_env="GROQ_MODEL",
            base_url="https://api.groq.com/openai/v1",
        ),
        CompatibleProviderSpec(
            name="openrouter",
            api_key_env="OPENROUTER_API_KEY",
            model_env="OPENROUTER_MODEL",
            base_url="https://openrouter.ai/api/v1",
        ),
        CompatibleProviderSpec(
            name="deepseek",
            api_key_env="DEEPSEEK_API_KEY",
            model_env="DEEPSEEK_MODEL",
            base_url="https://api.deepseek.com",
        ),
        CompatibleProviderSpec(
            name="fireworks",
            api_key_env="FIREWORKS_API_KEY",
            model_env="FIREWORKS_MODEL",
            base_url="https://api.fireworks.ai/inference/v1",
        ),
        CompatibleProviderSpec(
            name="sambanova",
            api_key_env="SAMBANOVA_API_KEY",
            model_env="SAMBANOVA_MODEL",
            base_url="https://api.sambanova.ai/v1",
        ),
        CompatibleProviderSpec(
            name="xai",
            api_key_env="XAI_API_KEY",
            model_env="XAI_MODEL",
            base_url="https://api.x.ai/v1",
        ),
        CompatibleProviderSpec(
            name="openai",
            api_key_env="OPENAI_API_KEY",
            model_env="OPENAI_MODEL",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            use_json_mode=True,
        ),
    ]


def _resolve_compatible_provider(
    spec: CompatibleProviderSpec,
    model_override: str | None,
) -> OpenAICompatibleProvider:
    api_key = _require_env(spec.api_key_env)
    model_name = (
        model_override
        or os.getenv(spec.model_env)
        or os.getenv("ORCH_MODEL")
        or spec.default_model
    )
    if not model_name:
        raise ProviderError(
            f"{spec.name} model is not set. Provide --model or set {spec.model_env}."
        )
    return OpenAICompatibleProvider(
        name=spec.name,
        api_key=api_key,
        base_url=spec.base_url,
        model=model_name,
        use_json_mode=spec.use_json_mode,
    )


def _maybe_generic_compatible_provider(
    model_override: str | None,
) -> OpenAICompatibleProvider | None:
    api_key = os.getenv("OPENAI_COMPAT_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL") or os.getenv("LLM_BASE_URL")
    model_name = (
        model_override
        or os.getenv("OPENAI_COMPAT_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("ORCH_MODEL")
    )
    if not base_url or not model_name:
        raise ProviderError(
            "OPENAI_COMPAT_BASE_URL/OPENAI_COMPAT_MODEL (or LLM_BASE_URL/LLM_MODEL) must be set for provider 'compat'."
        )
    return OpenAICompatibleProvider(
        name="compat",
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        use_json_mode=False,
    )


def _auto_compatible_providers(
    model_override: str | None,
) -> list[OpenAICompatibleProvider]:
    providers: list[OpenAICompatibleProvider] = []
    generic = _maybe_generic_compatible_provider(model_override)
    if generic is not None:
        providers.append(generic)

    for spec in _compatible_specs():
        if os.getenv(spec.api_key_env):
            providers.append(_resolve_compatible_provider(spec, model_override))
    return providers


def make_provider(name: str, model: str | None) -> Provider:
    normalized = name.lower()
    if normalized == "rule-based":
        return RuleBasedProvider()
    if normalized == "anthropic":
        return AnthropicProvider(
            model=model or os.getenv("ORCH_MODEL", "claude-3-7-sonnet-latest")
        )
    if normalized == "openai":
        return _resolve_compatible_provider(
            CompatibleProviderSpec(
                name="openai",
                api_key_env="OPENAI_API_KEY",
                model_env="OPENAI_MODEL",
                base_url="https://api.openai.com/v1",
                default_model="gpt-4o-mini",
                use_json_mode=True,
            ),
            model,
        )
    if normalized in {"compat", "openai-compatible"}:
        provider = _maybe_generic_compatible_provider(model)
        if provider is None:
            raise ProviderError(
                "No generic compatible provider configured. Set OPENAI_COMPAT_API_KEY, OPENAI_COMPAT_BASE_URL, and OPENAI_COMPAT_MODEL."
            )
        return provider
    if normalized in {"auto", "auto-compatible"}:
        providers = _auto_compatible_providers(model)
        if not providers:
            raise ProviderError(
                "No compatible provider credentials found. Configure one of: OPENAI_COMPAT_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY, FIREWORKS_API_KEY, SAMBANOVA_API_KEY, XAI_API_KEY, or OPENAI_API_KEY."
            )
        return CompatibleFallbackProvider(providers=providers)
    raise ProviderError(f"Unsupported provider: {name}")
