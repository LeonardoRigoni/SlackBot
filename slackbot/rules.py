from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class KeywordRule:
    keyword: str
    questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChannelRule:
    name: str
    description: str
    keywords: list[KeywordRule]


SECTION_RE = re.compile(r"^##\s+(?P<name>chamados-[a-z0-9-]+)\s*$")
KEYWORD_RE = re.compile(r"^-\s+(?P<keyword>[^:]+?)\s*$")
QUESTION_RE = re.compile(r"^\s*-\s+(?P<question>.+?)\s*$")


def load_rules(path: str | Path) -> list[ChannelRule]:
    text = Path(path).read_text(encoding="utf-8")
    return parse_rules(text)


def parse_rules(text: str) -> list[ChannelRule]:
    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        match = SECTION_RE.match(line)
        if match:
            if current_name:
                sections.append((current_name, current_lines))
            current_name = match.group("name")
            current_lines = []
        elif current_name:
            current_lines.append(line.rstrip())

    if current_name:
        sections.append((current_name, current_lines))

    return [_parse_section(name, lines) for name, lines in sections]


def _parse_section(name: str, lines: list[str]) -> ChannelRule:
    description_lines: list[str] = []
    keywords: list[KeywordRule] = []
    current_keyword: str | None = None
    current_questions: list[str] = []
    mode = "description"
    in_questions = False

    def flush_keyword() -> None:
        nonlocal current_keyword, current_questions
        if current_keyword:
            keywords.append(KeywordRule(keyword=current_keyword, questions=current_questions))
        current_keyword = None
        current_questions = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.lower() in {"descrição:", "descricao:"}:
            mode = "description"
            in_questions = False
            continue
        if line.lower() in {"palavras-chave:", "palavras chave:", "keywords:"}:
            mode = "keywords"
            in_questions = False
            continue
        if mode == "description":
            description_lines.append(line)
            continue
        if mode == "keywords":
            keyword_match = KEYWORD_RE.match(raw_line)
            if keyword_match and not raw_line.startswith("  "):
                flush_keyword()
                current_keyword = keyword_match.group("keyword").strip()
                in_questions = False
                continue
            if line.lower() in {"perguntar:", "perguntas:"}:
                in_questions = True
                continue
            question_match = QUESTION_RE.match(raw_line)
            if current_keyword and in_questions and question_match:
                current_questions.append(question_match.group("question").strip())

    flush_keyword()
    return ChannelRule(
        name=name,
        description="\n".join(description_lines).strip(),
        keywords=keywords,
    )


def rules_to_prompt(rules: list[ChannelRule]) -> str:
    parts: list[str] = []
    for rule in rules:
        keyword_lines = []
        for keyword in rule.keywords:
            if keyword.questions:
                qs = " | perguntas: " + "; ".join(keyword.questions)
            else:
                qs = ""
            keyword_lines.append(f"- {keyword.keyword}{qs}")
        parts.append(
            f"Canal: {rule.name}\n"
            f"Descrição: {rule.description}\n"
            f"Palavras-chave:\n" + "\n".join(keyword_lines)
        )
    return "\n\n".join(parts)


def find_keyword_rule(rules: list[ChannelRule], channel_name: str, keyword: str | None) -> KeywordRule | None:
    if not keyword:
        return None
    normalized = keyword.strip().lower()
    for channel in rules:
        if channel.name != channel_name:
            continue
        for keyword_rule in channel.keywords:
            if keyword_rule.keyword.lower() == normalized:
                return keyword_rule
    return None
