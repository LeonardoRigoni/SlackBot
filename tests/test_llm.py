from types import SimpleNamespace

from slackbot.llm import _anthropic_response_text, _extract_openai_output_text, _ollama_response_text, parse_decision_json


def test_parse_decision_json_rejects_unknown_channel():
    decision = parse_decision_json(
        """
        {
          "target_channel": "outro-canal",
          "keyword": "vpn",
          "confidence": 0.9,
          "priority": "Alta",
          "summary": "Usuário sem acesso à VPN.",
          "needs_more_info": false,
          "questions": [],
          "reason": "teste"
        }
        """,
        ["chamados-ti"],
    )

    assert decision.target_channel is None
    assert decision.keyword == "vpn"
    assert decision.priority == "Alta"
    assert decision.summary == "Usuário sem acesso à VPN."


def test_parse_decision_json_clamps_confidence():
    decision = parse_decision_json(
        """
        {
          "target_channel": "chamados-ti",
          "keyword": "vpn",
          "confidence": 2,
          "priority": "Baixa",
          "summary": "Teste.",
          "needs_more_info": false,
          "questions": [],
          "reason": "teste"
        }
        """,
        ["chamados-ti"],
    )

    assert decision.confidence == 1.0


def test_parse_decision_json_extracts_json_from_extra_text():
    decision = parse_decision_json(
        """
        Aqui está:
        ```json
        {
          "target_channel": "chamados-ti",
          "keyword": "notebook",
          "confidence": 0.8,
          "priority": "Alta",
          "summary": "Notebook não inicializa antes de apresentação.",
          "needs_more_info": true,
          "questions": ["Qual o modelo?"],
          "reason": "problema no notebook"
        }
        ```
        """,
        ["chamados-ti"],
    )

    assert decision.target_channel == "chamados-ti"
    assert decision.keyword == "notebook"
    assert decision.questions == ["Qual o modelo?"]


def test_ollama_response_text_uses_thinking_when_response_is_empty():
    response = SimpleNamespace(response="", thinking='{"ok": true}')

    assert _ollama_response_text(response) == '{"ok": true}'


def test_ollama_response_text_prefers_message_content():
    response = SimpleNamespace(
        response="",
        thinking='{"wrong": true}',
        message=SimpleNamespace(content='{"ok": true}', thinking="reasoning"),
    )

    assert _ollama_response_text(response) == '{"ok": true}'


def test_extract_openai_output_text_reads_content_blocks():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                content=[
                    SimpleNamespace(text='{"ok": '),
                    SimpleNamespace(text="true}"),
                ]
            )
        ]
    )

    assert _extract_openai_output_text(response) == '{"ok": true}'


def test_anthropic_response_text_reads_text_blocks():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text='{"ok": '),
            SimpleNamespace(type="text", text="true}"),
        ]
    )

    assert _anthropic_response_text(response) == '{"ok": true}'
