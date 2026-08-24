from slackbot.config import channel_env_name


def test_channel_env_name_uses_channel_suffix():
    assert channel_env_name("chamados-ti") == "SLACK_CHANNEL_TI"
    assert channel_env_name("chamados-seginfo") == "SLACK_CHANNEL_SEGINFO"
    assert channel_env_name("chamados-financeiro-contas") == "SLACK_CHANNEL_FINANCEIRO_CONTAS"
