from __future__ import annotations

from slack_bolt import App

from slackbot.app import _resolve_channel_id
from slackbot.config import destination_channel_refs, load_settings, validate_settings
from slackbot.rules import load_rules


def main() -> None:
    settings = load_settings()
    validate_settings(settings)
    app = App(token=settings.slack_bot_token)

    auth = app.client.auth_test()
    print(f"bot_user_id: {auth.get('user_id')}")
    print(f"team: {auth.get('team')}")

    menu_id = _resolve_channel_id(app.client, settings.channel_menu)
    print(f"SLACK_CHANNEL_MENU -> {menu_id}")

    rules = load_rules(settings.rules_path)
    channel_refs = destination_channel_refs([rule.name for rule in rules])
    for name, channel_ref in channel_refs.items():
        channel_id = _resolve_channel_id(app.client, channel_ref)
        info = app.client.conversations_info(channel=channel_id)
        channel = info.get("channel", {})
        print(f"{name} -> {channel_id} / is_member={channel.get('is_member')}")

    print("diagnóstico concluído")


if __name__ == "__main__":
    main()
