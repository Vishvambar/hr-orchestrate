from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .image_utils import (
    build_openai_compatible_image_content,
    guess_mime_type,
    image_id_from_path,
    normalize_image_for_api,
)


class VisionProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class VisionAttempt:
    provider: str
    model: str
    success: bool
    error: str = ""
    latency_seconds: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    image_count: int = 0


@dataclass(slots=True)
class VisionReviewResult:
    parsed: dict[str, Any]
    provider: str
    model: str
    raw_text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    attempts: list[VisionAttempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [asdict(attempt) for attempt in self.attempts]
        return data


class VisionProvider(Protocol):
    name: str

    def configured_model(self) -> str: ...

    def review_json(
        self,
        prompt_text: str,
        image_paths: list[Path],
    ) -> VisionReviewResult: ...


@dataclass(slots=True)
class OpenAICompatibleVisionProvider:
    name: str
    api_key_env: str
    model_env: str
    base_url: str
    default_model: str
    timeout_seconds: float = 20.0
    max_tokens: int = 1200
    default_headers: dict[str, str] | None = None
    image_detail: str = "auto"

    def configured_model(self) -> str:
        return os.getenv(self.model_env, self.default_model)

    def review_json(
        self,
        prompt_text: str,
        image_paths: list[Path],
    ) -> VisionReviewResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise VisionProviderError(
                "OpenAI SDK is required for GitHub/OpenRouter vision providers. Run: pip install -e .[openai]"
            ) from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise VisionProviderError(f"{self.api_key_env} is not set.")

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": self.base_url,
        }
        if self.default_headers:
            client_kwargs["default_headers"] = self.default_headers
        client = OpenAI(**client_kwargs)

        model = self.configured_model()
        started = time.perf_counter()
        messages = [
            {
                "role": "user",
                "content": build_openai_compatible_image_content(
                    prompt_text, image_paths, image_detail=self.image_detail
                ),
            }
        ]
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "timeout": self.timeout_seconds,
        }

        try:
            response = client.chat.completions.create(**request)
        except Exception as exc:  # noqa: BLE001
            if _looks_like_response_format_issue(exc):
                request.pop("response_format", None)
                response = client.chat.completions.create(**request)
            else:
                raise VisionProviderError(str(exc)) from exc

        content = response.choices[0].message.content or "{}"
        parsed = _parse_json_object(content)
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        latency_seconds = time.perf_counter() - started
        return VisionReviewResult(
            parsed=parsed,
            provider=self.name,
            model=model,
            raw_text=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            attempts=[
                VisionAttempt(
                    provider=self.name,
                    model=model,
                    success=True,
                    latency_seconds=round(latency_seconds, 3),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    image_count=len(image_paths),
                )
            ],
        )


@dataclass(slots=True)
class LocalConservativeVisionProvider:
    name: str = "local_conservative"
    model: str = "no_api_key_schema_fallback"

    def configured_model(self) -> str:
        return self.model

    def review_json(
        self,
        prompt_text: str,
        image_paths: list[Path],
    ) -> VisionReviewResult:
        started = time.perf_counter()
        parsed = {
            "evidence_standard_met": False,
            "evidence_standard_met_reason": "No vision API provider was configured, so the local fallback cannot inspect image contents.",
            "risk_flags": ["manual_review_required"],
            "issue_type": "unknown",
            "object_part": "unknown",
            "claim_status": "not_enough_information",
            "claim_status_justification": "Automated visual review was unavailable because no vision provider API key was configured.",
            "supporting_image_ids": [],
            "valid_image": False,
            "severity": "unknown",
        }
        raw_text = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        return VisionReviewResult(
            parsed=parsed,
            provider=self.name,
            model=self.model,
            raw_text=raw_text,
            prompt_tokens=max(1, len(prompt_text) // 4),
            completion_tokens=max(1, len(raw_text) // 4),
            attempts=[
                VisionAttempt(
                    provider=self.name,
                    model=self.model,
                    success=True,
                    latency_seconds=round(time.perf_counter() - started, 3),
                    prompt_tokens=max(1, len(prompt_text) // 4),
                    completion_tokens=max(1, len(raw_text) // 4),
                    image_count=len(image_paths),
                )
            ],
        )


@dataclass(slots=True)
class GeminiVisionProvider:
    name: str = "gemini"
    api_key_env: str = "GEMINI_API_KEY"
    model_env: str = "GEMINI_MODEL"
    default_model: str = "gemini-2.5-flash"
    timeout_seconds: float = 25.0
    max_tokens: int = 1200

    def configured_model(self) -> str:
        return os.getenv(self.model_env, self.default_model)

    def review_json(
        self,
        prompt_text: str,
        image_paths: list[Path],
    ) -> VisionReviewResult:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise VisionProviderError(f"{self.api_key_env} is not set.")
        model = self.configured_model()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(model, safe='.-_')}:generateContent?key={urllib.parse.quote(api_key)}"
        )

        parts: list[dict[str, Any]] = [{"text": prompt_text}]
        for image_path in image_paths:
            normalized_path = normalize_image_for_api(image_path)
            image_id = image_id_from_path(image_path)
            parts.append(
                {
                    "text": f"Image ID: {image_id}. Use this exact ID when this image supports the decision."
                }
            )
            parts.append(
                {
                    "inline_data": {
                        "mime_type": guess_mime_type(normalized_path),
                        "data": base64.b64encode(normalized_path.read_bytes()).decode(
                            "ascii"
                        ),
                    }
                }
            )

        response_schema = {
            "type": "object",
            "properties": {
                "evidence_standard_met": {"type": "boolean"},
                "evidence_standard_met_reason": {"type": "string"},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
                "issue_type": {"type": "string"},
                "object_part": {"type": "string"},
                "claim_status": {"type": "string"},
                "claim_status_justification": {"type": "string"},
                "supporting_image_ids": {"type": "array", "items": {"type": "string"}},
                "valid_image": {"type": "boolean"},
                "severity": {"type": "string"},
            },
            "required": [
                "evidence_standard_met",
                "evidence_standard_met_reason",
                "risk_flags",
                "issue_type",
                "object_part",
                "claim_status",
                "claim_status_justification",
                "supporting_image_ids",
                "valid_image",
                "severity",
            ],
        }
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            raise VisionProviderError(f"HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            raise VisionProviderError(str(exc)) from exc

        data = json.loads(body)
        content_parts = (
            data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        )
        text = "\n".join(
            part.get("text", "") for part in content_parts if part.get("text")
        )
        if not text:
            raise VisionProviderError(f"Gemini returned no text content: {body[:300]}")
        try:
            parsed = _parse_json_object(text)
        except VisionProviderError as exc:
            raise VisionProviderError(
                f"Gemini returned non-JSON content: {text[:300]}"
            ) from exc
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount")
        completion_tokens = usage.get("candidatesTokenCount")
        latency_seconds = time.perf_counter() - started
        return VisionReviewResult(
            parsed=parsed,
            provider=self.name,
            model=model,
            raw_text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            attempts=[
                VisionAttempt(
                    provider=self.name,
                    model=model,
                    success=True,
                    latency_seconds=round(latency_seconds, 3),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    image_count=len(image_paths),
                )
            ],
        )


@dataclass(slots=True)
class GroqVisionProvider:
    name: str
    model: str
    api_key_env: str = "GROQ_API_KEY"
    timeout_seconds: float = 25.0
    max_tokens: int = 1200
    image_detail: str = "auto"

    def configured_model(self) -> str:
        return self.model

    def review_json(
        self,
        prompt_text: str,
        image_paths: list[Path],
    ) -> VisionReviewResult:
        try:
            from groq import Groq
        except ImportError as exc:
            raise VisionProviderError(
                "Groq SDK is required for Groq vision providers. Run: pip install groq"
            ) from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise VisionProviderError(f"{self.api_key_env} is not set.")

        client = Groq(api_key=api_key)
        started = time.perf_counter()
        
        # Format images
        content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for image_path in image_paths:
            normalized_path = normalize_image_for_api(image_path)
            image_id = image_id_from_path(image_path)
            content_parts.append({"type": "text", "text": f"Image ID: {image_id}. Use this exact ID when this image supports the decision."})
            
            mime_type = guess_mime_type(normalized_path)
            b64 = base64.b64encode(normalized_path.read_bytes()).decode("ascii")
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64}"
                }
            })

        messages = [
            {
                "role": "user",
                "content": content_parts,
            }
        ]

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_completion_tokens=self.max_tokens,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise VisionProviderError(str(exc)) from exc

        content = response.choices[0].message.content or "{}"
        
        # Robust Parsing: Strip <think> tags completely before parsing
        cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        try:
            parsed = _parse_json_object(cleaned_content)
        except VisionProviderError as exc:
             raise VisionProviderError(f"Groq returned invalid JSON after cleaning: {cleaned_content[:300]}") from exc

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        latency_seconds = time.perf_counter() - started
        
        return VisionReviewResult(
            parsed=parsed,
            provider=self.name,
            model=self.model,
            raw_text=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            attempts=[
                VisionAttempt(
                    provider=self.name,
                    model=self.model,
                    success=True,
                    latency_seconds=round(latency_seconds, 3),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    image_count=len(image_paths),
                )
            ],
        )

@dataclass(slots=True)
class SequentialVisionRouter:
    providers: list[VisionProvider]
    cooldown_seconds: float = 15.0
    max_cycles: int = 2
    last_attempts: list[VisionAttempt] = field(default_factory=list)

    def review(self, prompt_text: str, image_paths: list[Path]) -> VisionReviewResult:
        if not self.providers:
            raise VisionProviderError("No vision providers are configured.")

        self.last_attempts = []
        failures: list[str] = []
        for cycle in range(1, self.max_cycles + 1):
            for provider in self.providers:
                started = time.perf_counter()
                try:
                    result = provider.review_json(prompt_text, image_paths)
                    self.last_attempts.extend(result.attempts)
                    result.attempts = list(self.last_attempts)
                    return result
                except VisionProviderError as exc:
                    latency_seconds = time.perf_counter() - started
                    failure = VisionAttempt(
                        provider=provider.name,
                        model=provider.configured_model(),
                        success=False,
                        error=str(exc),
                        latency_seconds=round(latency_seconds, 3),
                        image_count=len(image_paths),
                    )
                    self.last_attempts.append(failure)
                    failures.append(f"{provider.name}: {exc}")
                    continue

            if cycle < self.max_cycles:
                time.sleep(self.cooldown_seconds)

        raise VisionProviderError(
            "All configured vision providers failed after sequential failover: "
            + " | ".join(failures)
        )

    def last_attempts_as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(attempt) for attempt in self.last_attempts]


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


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = _clean_json_content(content)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start == -1:
        raise VisionProviderError("Vision model response did not contain valid JSON.")

    brace_count = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(cleaned)):
        char = cleaned[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i
                    break

    if end == -1:
        # Fallback to last } if brace counting fails due to malformed inner JSON
        end = cleaned.rfind("}")
        
    if start == -1 or end == -1:
        raise VisionProviderError("Vision model response did not contain a complete JSON object.")
        
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise VisionProviderError(f"Vision model response contained invalid JSON: {exc}") from exc
        
    if not isinstance(parsed, dict):
        raise VisionProviderError("Vision model response JSON was not an object.")
    return parsed


def make_sequential_vision_router(*, max_tokens: int = 1200) -> SequentialVisionRouter:
    available: dict[str, VisionProvider] = {}
    image_detail = os.getenv("ORCH_IMAGE_DETAIL", "auto")

    if os.getenv("GROQ_API_KEY"):
        available["groq_qwen"] = GroqVisionProvider(
            name="groq_qwen",
            model="qwen/qwen3.6-27b",
            max_tokens=max_tokens,
            image_detail=image_detail,
        )
        available["groq_llama"] = GroqVisionProvider(
            name="groq_llama",
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_tokens=max_tokens,
            image_detail=image_detail,
        )

    if os.getenv("GITHUB_TOKEN"):
        available["github_models"] = OpenAICompatibleVisionProvider(
            name="github_models",
            api_key_env="GITHUB_TOKEN",
            model_env="GITHUB_MODEL",
            base_url="https://models.github.ai/inference",
            default_model="gpt-4o",
            max_tokens=max_tokens,
            image_detail=image_detail,
        )
    if os.getenv("GEMINI_API_KEY"):
        available["gemini"] = GeminiVisionProvider(
            max_tokens=max_tokens,
        )
    if os.getenv("OPENROUTER_API_KEY"):
        headers = {}
        if os.getenv("OPENROUTER_HTTP_REFERER"):
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_HTTP_REFERER", "")
        if os.getenv("OPENROUTER_TITLE"):
            headers["X-Title"] = os.getenv("OPENROUTER_TITLE", "")
        available["openrouter"] = OpenAICompatibleVisionProvider(
            name="openrouter",
            api_key_env="OPENROUTER_API_KEY",
            model_env="OPENROUTER_MODEL",
            base_url="https://openrouter.ai/api/v1",
            default_model="openai/gpt-4o-mini",
            max_tokens=max_tokens,
            default_headers=headers or None,
            image_detail=image_detail,
        )

    order = [
        item.strip()
        for item in os.getenv(
            "ORCH_PROVIDER_ORDER", "github_models,gemini,openrouter"
        ).split(",")
        if item.strip()
    ]
    providers = [available[name] for name in order if name in available]
    providers.extend(
        provider for name, provider in available.items() if name not in order
    )

    if not providers:
        providers.append(LocalConservativeVisionProvider())

    return SequentialVisionRouter(
        providers=providers,
        cooldown_seconds=float(os.getenv("ORCH_VISION_COOLDOWN_SECONDS", "15")),
        max_cycles=int(os.getenv("ORCH_VISION_MAX_CYCLES", "2")),
    )
