from slackbot.app import _first_name, _format_destination_message, _format_manual_options, _manual_options
from slackbot.state import ThreadState


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def users_info(self, user):
        if self.error:
            raise self.error
        return self.response


def test_first_name_uses_profile_first_name():
    client = FakeClient({"user": {"profile": {"first_name": "Leonardo"}}})

    assert _first_name(client, "U123") == "Leonardo"


def test_first_name_falls_back_to_first_word_of_real_name():
    client = FakeClient({"user": {"profile": {"real_name": "Maria Silva"}}})

    assert _first_name(client, "U123") == "Maria"


def test_first_name_falls_back_to_mention_on_error():
    client = FakeClient(error=RuntimeError("boom"))

    assert _first_name(client, "U123") == "<@U123>"


def test_format_destination_message_is_minimal():
    state = ThreadState(
        thread_ts="123.456",
        source_channel_id="C123",
        user_id="U123",
        original_text="Meu notebook não inicializa.",
        target_channel="chamados-ti",
        keyword="notebook",
        priority="Alta",
        summary="Notebook não inicializa.",
        questions=["Qual o patrimônio, modelo ou identificação do equipamento?"],
        answers=["Patrimônio ca1000."],
    )

    message = _format_destination_message(state)

    assert message == (
        "Solicitante: <@U123>\n\n"
        "Prioridade sugerida: *Alta*\n\n"
        "Resumo: Notebook não inicializa.\n\n"
        "Mensagem original:\n"
        ">Meu notebook não inicializa.\n\n"
        "*Dados adicionais:*\n\n"
        "- Qual o patrimônio, modelo ou identificação do equipamento?: Patrimônio ca1000."
    )
    assert "Novo chamado roteado automaticamente" not in message
    assert "Canal classificado" not in message
    assert "Palavra-chave" not in message
    assert "Thread original" not in message


def test_manual_options_are_derived_from_channel_names():
    options = _manual_options(
        {
            "chamados-ti": "C1",
            "chamados-financeiro-contas": "C2",
        }
    )

    assert options == {
        "ti": "chamados-ti",
        "financeiro-contas": "chamados-financeiro-contas",
    }
    assert _format_manual_options(options) == "`financeiro-contas`, `ti`"
