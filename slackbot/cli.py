from __future__ import annotations

import argparse

from slackbot.config import load_settings
from slackbot.llm import build_llm_router
from slackbot.router import MessageRouter
from slackbot.rules import load_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa o roteamento de uma mensagem sem Slack.")
    parser.add_argument("message", help="Mensagem do chamado")
    args = parser.parse_args()

    settings = load_settings()
    rules = load_rules(settings.rules_path)
    router = MessageRouter(
        llm=build_llm_router(settings),
        rules=rules,
        confidence_threshold=settings.confidence_threshold,
        auto_route_confidence_threshold=settings.auto_route_confidence_threshold,
        allow_llm_generated_questions=settings.allow_llm_generated_questions,
    )
    result = router.route(args.message)

    print(f"canal: {result.target_channel or 'manual'}")
    print(f"palavra_chave: {result.keyword or 'não identificada'}")
    print(f"confiança: {result.confidence:.2f}")
    print(f"confirmacao: {'sim' if result.requires_confirmation else 'não'}")
    print(f"prioridade: {result.priority}")
    print(f"resumo: {result.summary}")
    print(f"motivo: {result.reason}")
    if result.questions:
        print("perguntas:")
        for question in result.questions:
            print(f"- {question}")


if __name__ == "__main__":
    main()
