from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
class OpenAIProvider:
    model: str
    name: str = "openai"

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
                "OpenAI extra not installed. Run: pip install -e .[openai]"
            ) from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")

        client = OpenAI(api_key=api_key)
        system_prompt, user_prompt = build_messages(
            contract, row, query, hits, base=project_root()
        )
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return _parse_json_object(content)


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


def _parse_json_object(content: str) -> dict[str, str]:
    content = content.strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1:
            raise ProviderError("Model response did not contain valid JSON.")
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ProviderError("Model response JSON was not an object.")
    return {str(key): str(value) for key, value in parsed.items()}


def make_provider(name: str, model: str | None) -> Provider:
    normalized = name.lower()
    if normalized == "rule-based":
        return RuleBasedProvider()
    if normalized == "openai":
        return OpenAIProvider(model=model or os.getenv("ORCH_MODEL", "gpt-4.1-mini"))
    if normalized == "anthropic":
        return AnthropicProvider(
            model=model or os.getenv("ORCH_MODEL", "claude-3-7-sonnet-latest")
        )
    raise ProviderError(f"Unsupported provider: {name}")
