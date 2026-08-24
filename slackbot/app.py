from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient

from slackbot.config import destination_channel_refs, load_settings, validate_settings
from slackbot.llm import build_llm_router
from slackbot.router import MessageRouter, RouteResult
from slackbot.rules import load_rules
from slackbot.state import StateStore, ThreadState


def build_app() -> tuple[App, str]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    validate_settings(settings)

    app = App(token=settings.slack_bot_token)
    menu_channel_id = _resolve_channel_id(app.client, settings.channel_menu)
    rules = load_rules(settings.rules_path)
    channel_refs = destination_channel_refs([rule.name for rule in rules])
    channel_map = {
        channel_name: _resolve_channel_id(app.client, channel_ref)
        for channel_name, channel_ref in channel_refs.items()
    }
    manual_options = _manual_options(channel_map)
    logging.info("Listening for messages in %s", menu_channel_id)
    logging.info("Destination channels: %s", channel_map)

    router = MessageRouter(
        llm=build_llm_router(settings),
        rules=rules,
        confidence_threshold=settings.confidence_threshold,
        auto_route_confidence_threshold=settings.auto_route_confidence_threshold,
        allow_llm_generated_questions=settings.allow_llm_generated_questions,
    )
    store = StateStore(settings.state_db_path)

    @app.event("message")
    def handle_message_events(event, client, logger):
        if event.get("bot_id") or event.get("subtype"):
            return
        channel_id = event.get("channel")
        text = (event.get("text") or "").strip()
        thread_ts = event.get("thread_ts") or event.get("ts")
        user_id = event.get("user", "")
        if not text:
            return

        if channel_id != menu_channel_id:
            logger.info("Ignoring message from channel %s; expected %s", channel_id, menu_channel_id)
            return

        existing_state = store.get(thread_ts)
        if existing_state and existing_state.status == "open" and event.get("thread_ts"):
            _handle_thread_reply(client, store, channel_map, manual_options, existing_state, text)
            return

        client.chat_postMessage(
            channel=menu_channel_id,
            thread_ts=thread_ts,
            text=_format_initial_message(client, user_id, settings.bot_timezone),
        )
        try:
            result = router.route(text)
        except Exception as exc:
            logger.exception("Failed to route message")
            client.chat_postMessage(
                channel=menu_channel_id,
                thread_ts=thread_ts,
                text=f"Não consegui analisar a mensagem agora. Erro: `{type(exc).__name__}`.",
            )
            return

        if result.requires_manual_choice:
            state = ThreadState(
                thread_ts=thread_ts,
                source_channel_id=menu_channel_id,
                user_id=user_id,
                original_text=text,
                priority=result.priority,
                summary=result.summary,
                status="open",
            )
            store.save(state)
            client.chat_postMessage(
                channel=menu_channel_id,
                thread_ts=thread_ts,
                text=(
                    "Não consegui identificar o canal com segurança. "
                    f"Responda nesta thread com uma opção: {_format_manual_options(manual_options)}."
                ),
            )
            return

        state = ThreadState(
            thread_ts=thread_ts,
            source_channel_id=menu_channel_id,
            user_id=user_id,
            original_text=text,
            target_channel=result.target_channel,
            keyword=result.keyword,
            priority=result.priority,
            summary=result.summary,
            questions=result.questions,
            pending_confirmation=result.requires_confirmation,
            status="open",
        )
        store.save(state)

        if result.requires_confirmation:
            client.chat_postMessage(
                channel=menu_channel_id,
                thread_ts=thread_ts,
                text=_format_confirmation_request(result, manual_options),
            )
            return

        if result.questions:
            client.chat_postMessage(
                channel=menu_channel_id,
                thread_ts=thread_ts,
                text=_format_questions(result),
            )
            return

        _route_to_destination(client, store, channel_map, state)

    return app, settings.slack_app_token


def _resolve_channel_id(client: WebClient, channel_ref: str) -> str:
    cleaned = channel_ref.strip()
    if cleaned.startswith("C") or cleaned.startswith("G"):
        return cleaned

    channel_name = cleaned.removeprefix("#")
    cursor = None
    while True:
        response = client.conversations_list(
            exclude_archived=True,
            limit=1000,
            cursor=cursor,
            types="public_channel,private_channel",
        )
        for channel in response.get("channels", []):
            if channel.get("name") == channel_name:
                return channel["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    raise RuntimeError(f"Slack channel not found or not visible to bot: {channel_ref}")


def _manual_options(channel_map: dict[str, str]) -> dict[str, str]:
    return {channel_name.removeprefix("chamados-"): channel_name for channel_name in channel_map}


def _format_manual_options(manual_options: dict[str, str]) -> str:
    return ", ".join(f"`{option}`" for option in sorted(manual_options))


def _format_initial_message(client: WebClient, user_id: str, timezone_name: str) -> str:
    greeting = _time_greeting(timezone_name)
    first_name = _first_name(client, user_id)
    return (
        f"{greeting}, {first_name}! "
        "Estou analisando sua mensagem e já dou um retorno em alguns instantes."
    )


def _time_greeting(timezone_name: str) -> str:
    try:
        now = datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        logging.warning("Invalid BOT_TIMEZONE=%s; falling back to local timezone", timezone_name)
        now = datetime.now()

    if 5 <= now.hour < 12:
        return "Bom dia"
    if 12 <= now.hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _first_name(client: WebClient, user_id: str) -> str:
    if not user_id:
        return "por aqui"

    try:
        response = client.users_info(user=user_id)
    except Exception:
        logging.exception("Failed to fetch Slack user profile for %s", user_id)
        return f"<@{user_id}>"

    user = response.get("user", {})
    profile = user.get("profile", {})
    full_name = (
        profile.get("first_name")
        or profile.get("real_name")
        or user.get("real_name")
        or user.get("name")
        or ""
    ).strip()
    if not full_name:
        return f"<@{user_id}>"
    return full_name.split()[0]


def _handle_thread_reply(
    client,
    store: StateStore,
    channel_map: dict[str, str],
    manual_options: dict[str, str],
    state: ThreadState,
    text: str,
) -> None:
    normalized_text = text.strip().lower()
    if state.pending_confirmation:
        if _is_affirmative(normalized_text):
            state.pending_confirmation = False
            if state.questions:
                store.save(state)
                client.chat_postMessage(
                    channel=state.source_channel_id,
                    thread_ts=state.thread_ts,
                    text=_format_state_questions(state),
                )
                return
            store.save(state)
            _route_to_destination(client, store, channel_map, state)
            return
        else:
            chosen_channel = manual_options.get(normalized_text)
            if not chosen_channel:
                client.chat_postMessage(
                    channel=state.source_channel_id,
                    thread_ts=state.thread_ts,
                    text=(
                        "Sem problema. Responda com uma opção para corrigir: "
                        f"{_format_manual_options(manual_options)}."
                    ),
                )
                return
            state.target_channel = chosen_channel
            state.pending_confirmation = False
            store.save(state)
            _route_to_destination(client, store, channel_map, state)
            return

    if not state.target_channel:
        chosen_channel = manual_options.get(normalized_text)
        if not chosen_channel:
            client.chat_postMessage(
                channel=state.source_channel_id,
                thread_ts=state.thread_ts,
                text=f"Opção inválida. Use: {_format_manual_options(manual_options)}.",
            )
            return
        state.target_channel = chosen_channel
    else:
        state.answers.append(text)

    store.save(state)
    _route_to_destination(client, store, channel_map, state)


def _route_to_destination(
    client,
    store: StateStore,
    channel_map: dict[str, str],
    state: ThreadState,
) -> None:
    if not state.target_channel:
        return
    destination_id = channel_map[state.target_channel]
    message = _format_destination_message(state)
    destination_response = client.chat_postMessage(channel=destination_id, text=message)
    destination_ts = destination_response.get("ts")
    destination_link = ""
    if destination_ts:
        permalink = client.chat_getPermalink(channel=destination_id, message_ts=destination_ts)
        destination_link = permalink.get("permalink", "")

    confirmation = f"Chamado roteado automaticamente para `#{state.target_channel}`."
    if destination_link:
        confirmation += f"\nMensagem no canal destino: {destination_link}"

    client.chat_postMessage(
        channel=state.source_channel_id,
        thread_ts=state.thread_ts,
        text=confirmation,
        unfurl_links=False,
        unfurl_media=False,
    )
    store.close(state.thread_ts)


def _format_questions(result: RouteResult) -> str:
    questions = "\n".join(f"{index}. {question}" for index, question in enumerate(result.questions, start=1))
    return (
        f"Identifiquei que este chamado deve ir para `#{result.target_channel}`"
        f" com palavra-chave `{result.keyword or 'não identificada'}`.\n"
        "Antes de enviar, responda nesta thread com as informações que souber:\n"
        f"{questions}"
    )


def _format_state_questions(state: ThreadState) -> str:
    questions = "\n".join(f"{index}. {question}" for index, question in enumerate(state.questions, start=1))
    return "Antes de enviar, responda nesta thread com as informações que souber:\n" + questions


def _format_confirmation_request(result: RouteResult, manual_options: dict[str, str]) -> str:
    return (
        f"Parece ser um chamado para `#{result.target_channel}` "
        f"(confiança {result.confidence:.0%}). Posso enviar para esse canal?\n"
        "Responda `sim` para enviar, ou informe uma opção para corrigir: "
        f"{_format_manual_options(manual_options)}."
    )


def _is_affirmative(text: str) -> bool:
    return text in {"s", "sim", "yes", "y", "pode", "pode sim", "ok", "confirmo", "correto"}


def _format_destination_message(state: ThreadState) -> str:
    parts = [
        f"Solicitante: <@{state.user_id}>",
        f"Prioridade sugerida: *{state.priority}*",
        f"Resumo: {state.summary or state.original_text}",
        f"Mensagem original:\n>{state.original_text}",
    ]
    if state.answers:
        parts.append("*Dados adicionais:*")
        parts.extend(
            f"- {question}: {answer}"
            for question, answer in zip(state.questions, state.answers, strict=False)
        )
    return "\n\n".join(parts)


if __name__ == "__main__":
    slack_app, app_token = build_app()
    SocketModeHandler(slack_app, app_token).start()
