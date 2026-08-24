from slackbot.llm import LlmDecision
from slackbot.router import MessageRouter
from slackbot.rules import parse_rules


def decision(**overrides):
    defaults = {
        "target_channel": "chamados-ti",
        "keyword": "vpn",
        "confidence": 0.9,
        "priority": "Média",
        "summary": "Resumo do chamado.",
        "needs_more_info": False,
        "questions": [],
        "reason": "teste",
    }
    defaults.update(overrides)
    return LlmDecision(**defaults)


class FakeLlm:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, **kwargs):
        return self.decision


def test_router_uses_only_configured_questions_selected_by_llm():
    rules = parse_rules(
        """
## chamados-ti

Descrição:
Suporte.

Palavras-chave:
- vpn
  Perguntar:
  - Qual erro aparece?
"""
    )
    router = MessageRouter(
        llm=FakeLlm(
            decision(
                needs_more_info=True,
                questions=["Qual erro aparece?"],
                reason="vpn",
            )
        ),
        rules=rules,
        confidence_threshold=0.65,
        auto_route_confidence_threshold=0.85,
        allow_llm_generated_questions=True,
    )

    result = router.route("VPN caiu")

    assert result.target_channel == "chamados-ti"
    assert result.questions == ["Qual erro aparece?"]


def test_router_does_not_force_configured_questions_when_llm_says_no_more_info():
    rules = parse_rules(
        """
## chamados-ti

Descrição:
Suporte.

Palavras-chave:
- notebook
  Perguntar:
  - Qual o patrimônio, modelo ou identificação do equipamento?
"""
    )
    router = MessageRouter(
        llm=FakeLlm(
            decision(
                keyword="notebook",
                confidence=0.95,
                needs_more_info=False,
                questions=[],
                reason="mensagem suficiente",
            )
        ),
        rules=rules,
        confidence_threshold=0.65,
        auto_route_confidence_threshold=0.85,
        allow_llm_generated_questions=False,
    )

    result = router.route("Meu notebook não inicializa")

    assert result.target_channel == "chamados-ti"
    assert result.questions == []


def test_router_requires_manual_choice_when_confidence_is_low():
    rules = parse_rules(
        """
## chamados-ti

Descrição:
Suporte.

Palavras-chave:
- vpn
"""
    )
    router = MessageRouter(
        llm=FakeLlm(
            decision(
                confidence=0.4,
                needs_more_info=False,
                questions=[],
                reason="incerto",
            )
        ),
        rules=rules,
        confidence_threshold=0.65,
        auto_route_confidence_threshold=0.85,
        allow_llm_generated_questions=False,
    )

    result = router.route("Ajuda")

    assert result.requires_manual_choice is True
    assert result.target_channel is None


def test_router_requires_confirmation_when_confidence_is_medium():
    rules = parse_rules(
        """
## chamados-ti

Descrição:
Suporte.

Palavras-chave:
- vpn
"""
    )
    router = MessageRouter(
        llm=FakeLlm(decision(confidence=0.75)),
        rules=rules,
        confidence_threshold=0.65,
        auto_route_confidence_threshold=0.85,
        allow_llm_generated_questions=False,
    )

    result = router.route("VPN caiu")

    assert result.requires_manual_choice is False
    assert result.requires_confirmation is True
    assert result.target_channel == "chamados-ti"
