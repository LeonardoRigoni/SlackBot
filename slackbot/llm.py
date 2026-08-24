from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from slackbot.config import Settings


@dataclass(frozen=True)
class LlmDecision:
    target_channel: str | None
    keyword: str | None
    confidence: float
    priority: str
    summary: str
    needs_more_info: bool
    questions: list[str]
    reason: str


class LlmRouter(Protocol):
    def decide(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> LlmDecision:
        pass


class PromptBuilderMixin:
    def _build_prompt(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> str:
        generated_questions_policy = (
            "Você pode criar perguntas adicionais se as regras não forem suficientes. "
            "Mesmo assim, faça apenas perguntas indispensáveis para encaminhar o chamado."
            if allow_generated_questions
            else "Não crie perguntas novas. Use apenas perguntas explicitamente listadas nas regras."
        )
        return f"""
Você é um classificador de chamados de Slack.

Escolha exatamente um canal permitido ou retorne null se não houver segurança.
Canais permitidos: {", ".join(allowed_channels)}

Critérios para perguntas:
- Faça perguntas apenas quando a resposta for realmente necessária para encaminhar o chamado.
- Não pergunte algo que a mensagem do usuário já respondeu.
- Não peça para o usuário classificar tecnicamente o problema se isso exigir conhecimento especializado.
- Se o canal estiver claro e já houver informação suficiente para triagem inicial, use "needs_more_info": false e "questions": [].
- Quando ALLOW_LLM_GENERATED_QUESTIONS estiver desabilitado pela política, o campo "questions" deve conter apenas textos exatamente iguais a perguntas listadas nas regras.

Critérios para prioridade:
- Use "Alta" para impacto urgente ou sensível, como produção parada, cliente impactado, vazamento, incidente de segurança, sem acesso essencial, prazo crítico, apresentação/reunião próxima ou bloqueio de trabalho.
- Use "Média" para problemas importantes sem urgência explícita.
- Use "Baixa" para dúvidas, solicitações simples ou demandas sem bloqueio.

Resumo operacional:
- Gere um resumo curto e acionável para quem receberá o chamado.
- Não repita saudações.
- Preserve sinais de urgência e impacto.

Regras:
{rules_prompt}

Política de perguntas:
{generated_questions_policy}

Mensagem do usuário:
{message}

Responda apenas com JSON válido neste formato:
{{
  "target_channel": "chamados-ti",
  "keyword": "vpn",
  "confidence": 0.87,
  "priority": "Alta",
  "summary": "Usuário sem acesso à VPN para acessar sistema interno.",
  "needs_more_info": true,
  "questions": ["pergunta 1"],
  "reason": "motivo curto"
}}
""".strip()


class OllamaRouter(PromptBuilderMixin):
    def __init__(self, base_url: str, model: str) -> None:
        from ollama import Client

        self.client = Client(host=base_url)
        self.model = model

    def decide(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> LlmDecision:
        prompt = self._build_prompt(message, rules_prompt, allowed_channels, allow_generated_questions)
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            format="json",
            options={"temperature": 0.1},
        )
        content = _ollama_response_text(response)
        logging.info("Ollama raw response preview: %r", content[:500])
        return parse_decision_json(content, allowed_channels)


class OpenAIRouter(PromptBuilderMixin):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install OpenAI support with: pip install -r requirements-cloud.txt") from exc

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def decide(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> LlmDecision:
        prompt = self._build_prompt(message, rules_prompt, allowed_channels, allow_generated_questions)
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={"format": {"type": "json_object"}},
            temperature=0.1,
        )
        content = getattr(response, "output_text", "") or _extract_openai_output_text(response)
        logging.info("OpenAI raw response preview: %r", content[:500])
        return parse_decision_json(content, allowed_channels)


class AnthropicRouter(PromptBuilderMixin):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Install Anthropic support with: pip install -r requirements-cloud.txt") from exc

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def decide(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> LlmDecision:
        prompt = self._build_prompt(message, rules_prompt, allowed_channels, allow_generated_questions)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        content = _anthropic_response_text(response)
        logging.info("Anthropic raw response preview: %r", content[:500])
        return parse_decision_json(content, allowed_channels)


class GeminiRouter(PromptBuilderMixin):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install Gemini support with: pip install -r requirements-cloud.txt") from exc

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def decide(
        self,
        message: str,
        rules_prompt: str,
        allowed_channels: list[str],
        allow_generated_questions: bool,
    ) -> LlmDecision:
        try:
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install Gemini support with: pip install -r requirements-cloud.txt") from exc

        prompt = self._build_prompt(message, rules_prompt, allowed_channels, allow_generated_questions)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        content = getattr(response, "text", "")
        logging.info("Gemini raw response preview: %r", content[:500])
        return parse_decision_json(content, allowed_channels)


def build_llm_router(settings: Settings) -> LlmRouter:
    if settings.llm_provider == "ollama":
        return OllamaRouter(settings.ollama_base_url, settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIRouter(settings.openai_api_key, settings.llm_model)
    if settings.llm_provider == "anthropic":
        return AnthropicRouter(settings.anthropic_api_key, settings.llm_model)
    if settings.llm_provider == "gemini":
        return GeminiRouter(settings.gemini_api_key, settings.llm_model)
    raise RuntimeError("LLM_PROVIDER must be one of: ollama, openai, anthropic, gemini")


def _ollama_response_text(response: Any) -> str:
    response_text = _value(response, "response")
    if response_text:
        return str(response_text)

    message = _value(response, "message")
    if message:
        message_content = _value(message, "content")
        if message_content:
            return str(message_content)
        message_thinking = _value(message, "thinking")
        if message_thinking:
            return str(message_thinking)

    thinking = _value(response, "thinking")
    if thinking:
        return str(thinking)

    return ""


def _value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_openai_output_text(response: Any) -> str:
    output = _value(response, "output") or []
    chunks: list[str] = []
    for item in output:
        for content in _value(item, "content") or []:
            text = _value(content, "text")
            if text:
                chunks.append(str(text))
    return "".join(chunks)


def _anthropic_response_text(response: Any) -> str:
    chunks: list[str] = []
    for block in _value(response, "content") or []:
        text = _value(block, "text")
        if text:
            chunks.append(str(text))
    return "".join(chunks)


def parse_decision_json(content: str, allowed_channels: list[str]) -> LlmDecision:
    data = _load_json_object(content)
    target_channel = data.get("target_channel")
    if target_channel not in allowed_channels:
        target_channel = None

    keyword = data.get("keyword")
    if keyword is not None:
        keyword = str(keyword).strip() or None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    questions = data.get("questions", [])
    if not isinstance(questions, list):
        questions = []

    return LlmDecision(
        target_channel=target_channel,
        keyword=keyword,
        confidence=max(0.0, min(1.0, confidence)),
        priority=_normalize_priority(data.get("priority")),
        summary=str(data.get("summary", "")).strip(),
        needs_more_info=bool(data.get("needs_more_info", False)),
        questions=[str(question).strip() for question in questions if str(question).strip()],
        reason=str(data.get("reason", "")).strip(),
    )


def _normalize_priority(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"alta", "alto", "high"}:
        return "Alta"
    if normalized in {"baixa", "baixo", "low"}:
        return "Baixa"
    return "Média"


def _load_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if not stripped:
        raise ValueError("LLM returned an empty response")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = json.loads(_extract_first_json_object(stripped))

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    return data


def _extract_first_json_object(content: str) -> str:
    start = content.find("{")
    if start == -1:
        raise ValueError(f"LLM response did not contain a JSON object: {content[:200]!r}")

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]

    raise ValueError(f"LLM response contained an incomplete JSON object: {content[:200]!r}")
