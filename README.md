# Slack Ticket Router

Python Slack bot that centralizes ticket intake in one Slack channel, uses an LLM to classify the request, asks for missing information in the original thread when needed, and posts an operational ticket summary to the correct destination channel.

The default intake channel is `chamados-menu`. Destination channels are defined in `rules/channels.md`.

## Features

- Slack Socket Mode connection, so no public HTTP endpoint is required.
- Dynamic destination channels loaded from `rules/channels.md`.
- LLM provider abstraction:
  - Ollama/local models
  - OpenAI
  - Anthropic
  - Gemini
- Confidence-based routing:
  - low confidence: ask the user to choose a channel
  - medium confidence: ask for confirmation
  - high confidence: route automatically
- Automatic priority detection: `Alta`, `Média`, or `Baixa`.
- Operational summary generated for the destination channel.
- Original user message is included after the summary for auditability.
- Optional follow-up questions based on `rules/channels.md`.
- Thread-based interaction in the intake channel to avoid channel noise.
- SQLite-backed thread state, so open conversations survive bot restarts.
- Slack diagnostic command for token/channel membership checks.

## LLM Configuration

Default local setup:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3.6-64k:27b
OLLAMA_BASE_URL=http://localhost:11434
```

`qwen3.6-64k:27b` works well for Portuguese classification and has enough context for the rules file. A lighter local alternative is `gpt-oss-64k:20b`.

Cloud providers are also supported:

```env
LLM_PROVIDER=openai
LLM_MODEL=<openai-model>
OPENAI_API_KEY=...
```

```env
LLM_PROVIDER=anthropic
LLM_MODEL=<anthropic-model>
ANTHROPIC_API_KEY=...
```

```env
LLM_PROVIDER=gemini
LLM_MODEL=<gemini-model>
GEMINI_API_KEY=...
```

Install optional cloud SDKs with:

```bash
pip install -r requirements-cloud.txt
```

If you only use Ollama, `requirements.txt` is enough.

## Slack App Setup

Follow these steps to create and install the Slack bot.

### 1. Create The Slack App

1. Open <https://api.slack.com/apps>.
2. Click **Create New App**.
3. Choose **Blank app**.
4. Enter an app name, for example `Router Bot`.
5. Select your Slack workspace.
6. Click **Create App**.

### 2. Create The App-Level Token

This token is used by Socket Mode. It becomes `SLACK_APP_TOKEN`.

1. In the Slack app settings, go to **Basic Information**.
2. Scroll to **App-Level Tokens**.
3. Click **Generate Token and Scopes**.
4. Use a name such as `socket-mode`.
5. Add this scope:

```text
connections:write
```

6. Click **Generate**.
7. Copy the generated token into `.env`:

```env
SLACK_APP_TOKEN=replace-with-your-slack-app-token
```

The app-level Socket Mode token starts with `xapp-`.

### 3. Enable Socket Mode

1. Go to **Socket Mode**.
2. Turn **Enable Socket Mode** on.
3. Select the app-level token created in the previous step.
4. Save the change.

Socket Mode lets the bot run from your local machine without exposing a public HTTP endpoint.

### 4. Configure Bot OAuth Scopes

Go to **OAuth & Permissions** and add these **Bot Token Scopes**:

- `channels:history`
- `channels:read`
- `chat:write`
- `app_mentions:read`
- `users:read`

If the intake channel or any destination channel is private, also add:

- `groups:history`
- `groups:read`

### 5. Install The App To The Workspace

1. Still in **OAuth & Permissions**, click **Install to Workspace**.
2. Approve the installation.
3. Copy the **Bot User OAuth Token** into `.env`:

```env
SLACK_BOT_TOKEN=replace-with-your-slack-bot-token
```

The bot token starts with `xoxb-`.

If you add or change scopes later, click **Reinstall to Workspace** so the new permissions take effect.

### 6. Subscribe To Message Events

Go to **Event Subscriptions**.

1. Turn **Enable Events** on.
2. In **Subscribe to bot events**, add:

- `message.channels`

If the intake channel or destination channels are private, also add:

- `message.groups`

3. Save changes.
4. Reinstall the app if Slack asks for it.

### 7. Configure App Display

Optional but recommended:

1. Go to **Basic Information**.
2. Scroll to **Display Information**.
3. Set the app display name, for example `Router Bot`.
4. Upload an app icon.

Generated icon assets are available in this repository:

- `assets/router-bot-icon-512.png`
- `assets/router-bot-icon-original.png`

Use the 512x512 PNG for Slack.

### 8. Create Or Choose Slack Channels

Create or choose the intake channel and destination channels.

Default intake channel:

- `chamados-menu`

Default destination channels:

- `chamados-ti`
- `chamados-dados`
- `chamados-people`
- `chamados-plataforma`
- `chamados-seginfo`

### 9. Invite The Bot To Channels

Invite the bot to:

- the intake channel, for example `chamados-menu`
- every destination channel listed in `rules/channels.md`

Run this inside each channel:

```text
/invite @Router Bot
```

If the bot is not a member of a channel, it may not receive messages from that channel or may fail to post routed tickets.

### 10. Fill Slack Channel Env Vars

In `.env`, configure the intake channel:

```env
SLACK_CHANNEL_MENU=chamados-menu
```

Then configure every destination channel derived from `rules/channels.md`:

```env
SLACK_CHANNEL_TI=chamados-ti
SLACK_CHANNEL_DADOS=chamados-dados
SLACK_CHANNEL_PEOPLE=chamados-people
SLACK_CHANNEL_PLATAFORMA=chamados-plataforma
SLACK_CHANNEL_SEGINFO=chamados-seginfo
```

You may use Slack channel IDs instead of names:

```env
SLACK_CHANNEL_TI=C0123456789
```

### 11. Validate Slack Setup

After `.env` is filled and dependencies are installed, run:

```bash
python3 -m slackbot.diagnose
```

Expected output includes:

```text
bot_user_id: ...
team: ...
SLACK_CHANNEL_MENU -> C...
chamados-ti -> C... / is_member=True
```

If any destination channel shows `is_member=False`, invite the bot to that channel and run the diagnostic again.

### 12. Start The Bot

Run:

```bash
python3 -m slackbot.app
```

You should see:

```text
Bolt app is running!
```

Post a test message in the intake channel. The bot should reply in a thread and then route or ask follow-up questions depending on the classification result.

### Slack Troubleshooting

If the bot starts but does not react to messages:

- confirm **Socket Mode** is enabled
- confirm **Event Subscriptions** is enabled
- confirm `message.channels` is subscribed
- add `message.groups` if using private channels
- confirm the app was reinstalled after changing scopes or events
- confirm the bot was invited to the intake channel
- run `python3 -m slackbot.diagnose`
- check that `SLACK_CHANNEL_MENU` points to the correct channel

If the bot cannot post to a destination channel:

- invite the bot to that destination channel
- confirm the matching `SLACK_CHANNEL_*` env var exists
- confirm the destination section exists in `rules/channels.md`

## Environment

Create your `.env`:

```bash
cp .env.example .env
```

Fill in Slack tokens:

```env
SLACK_BOT_TOKEN=replace-with-your-slack-bot-token
SLACK_APP_TOKEN=replace-with-your-slack-app-token
```

The bot token starts with `xoxb-`; the app-level Socket Mode token starts with `xapp-`.

Set the intake channel:

```env
SLACK_CHANNEL_MENU=chamados-menu
```

Channel values can be Slack IDs such as `C...` or channel names such as `chamados-menu`.

## Dynamic Destination Channels

Destination channels are loaded from `rules/channels.md`. For every section named `## chamados-*`, the bot expects a matching env var.

Example rule section:

```md
## chamados-financeiro-contas
```

Required env var:

```env
SLACK_CHANNEL_FINANCEIRO_CONTAS=chamados-financeiro-contas
```

The env var name is derived by:

- removing the `chamados-` prefix
- converting to uppercase
- replacing `-` with `_`
- prefixing with `SLACK_CHANNEL_`

Examples:

```env
SLACK_CHANNEL_TI=chamados-ti
SLACK_CHANNEL_SEGINFO=chamados-seginfo
SLACK_CHANNEL_FINANCEIRO_CONTAS=chamados-financeiro-contas
```

## Routing Thresholds

The bot uses two confidence thresholds:

```env
CONFIDENCE_THRESHOLD=0.65
AUTO_ROUTE_CONFIDENCE_THRESHOLD=0.85
```

Behavior:

- below `CONFIDENCE_THRESHOLD`: ask the user to choose the destination channel
- between both thresholds: ask for confirmation before sending
- at or above `AUTO_ROUTE_CONFIDENCE_THRESHOLD`: route automatically

## Follow-Up Questions

This flag controls whether the LLM may create its own follow-up questions:

```env
ALLOW_LLM_GENERATED_QUESTIONS=false
```

With `false`, the bot only uses questions explicitly defined in `rules/channels.md`.

With `true`, the LLM may generate questions when no configured question is available for the detected keyword.

## Timezone

The bot uses this timezone for greetings such as `Bom dia`, `Boa tarde`, and `Boa noite`:

```env
BOT_TIMEZONE=America/Sao_Paulo
```

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 -m slackbot.app
```

For cloud providers:

```bash
pip install -r requirements-cloud.txt
```

## Test Classification Without Slack

With the configured LLM provider available:

```bash
python3 -m slackbot.cli "não consigo acessar a VPN"
```

The CLI prints the selected channel, keyword, confidence, confirmation requirement, priority, summary, reason, and any follow-up questions.

## Diagnose Slack

With `.env` filled:

```bash
python3 -m slackbot.diagnose
```

This validates the bot token, resolves configured channels, and shows whether the bot is a member of each destination channel.

## Ticket Flow

1. User posts a message in `chamados-menu`.
2. Bot replies in the original message thread with a greeting and analysis status.
3. LLM classifies the message into one destination channel.
4. LLM returns keyword, confidence, priority, operational summary, reason, and optional questions.
5. If confidence is low, the bot asks the user to choose the channel.
6. If confidence is medium, the bot asks for confirmation.
7. If follow-up questions are needed, the bot asks them in the same thread.
8. The bot posts the ticket to the destination channel.
9. The original thread receives a confirmation with a link to the destination message, without Slack link preview/unfurl.

## Destination Message Format

The destination channel receives a compact operational message:

```text
Solicitante: @user

Prioridade sugerida: Alta

Resumo: Notebook travando na inicialização com apresentação crítica amanhã de manhã.

Mensagem original:
>boa noite, estou com problema no meu notebook...

Dados adicionais:
- Qual o patrimônio, modelo ou identificação do equipamento?: CA1000
```

The original text is intentionally included because the summary is generated by an LLM.

## Rules File

Edit `rules/channels.md`.

Each destination channel must have a section:

```md
## chamados-ti

Descrição:
Demandas de suporte técnico corporativo, acesso de usuário, notebook, desktop, VPN...

Palavras-chave:
- vpn
  Perguntar:
  - Qual sistema ou recurso você está tentando acessar?
  - Qual erro aparece?
```

The bot uses:

- section name as the destination channel key
- description as classification context
- keywords to improve classification
- optional questions for missing information

## Add A Destination Channel

1. Create or choose the Slack channel.
2. Invite the bot:

```text
/invite @Router Bot
```

3. Add a section to `rules/channels.md`:

```md
## chamados-financeiro

Descrição:
Demandas financeiras, reembolsos, pagamentos, notas fiscais e fornecedores.

Palavras-chave:
- reembolso
  Perguntar:
  - Qual o valor e a data da despesa?
```

4. Add the matching env var:

```env
SLACK_CHANNEL_FINANCEIRO=chamados-financeiro
```

5. Restart the bot:

```bash
python3 -m slackbot.app
```

## App Icon

Generated icon assets are available in:

- `assets/router-bot-icon-512.png`
- `assets/router-bot-icon-original.png`

Use the 512x512 PNG in Slack under:

```text
Basic Information > Display Information > App icon & Preview
```
