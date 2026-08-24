from slackbot.rules import parse_rules, rules_to_prompt


def test_parse_rules_with_keyword_questions():
    rules = parse_rules(
        """
## chamados-ti

Descrição:
Suporte técnico.

Palavras-chave:
- vpn
  Perguntar:
  - Qual erro aparece?
- notebook
"""
    )

    assert len(rules) == 1
    assert rules[0].name == "chamados-ti"
    assert rules[0].description == "Suporte técnico."
    assert rules[0].keywords[0].keyword == "vpn"
    assert rules[0].keywords[0].questions == ["Qual erro aparece?"]
    assert rules[0].keywords[1].keyword == "notebook"


def test_rules_to_prompt_contains_channels_and_keywords():
    rules = parse_rules(
        """
## chamados-dados

Descrição:
BI.

Palavras-chave:
- dashboard
"""
    )

    prompt = rules_to_prompt(rules)

    assert "Canal: chamados-dados" in prompt
    assert "- dashboard" in prompt
