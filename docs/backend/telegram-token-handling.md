# Telegram Token Handling

Telegram bot tokens must never be committed to the repository.

## Current backend scope

The current backend receives Telegram webhooks and extracts incident details from incoming text. It does not send Telegram replies yet, so the bot token is not required for the current webhook-to-extraction integration.

## Future send-message scope

When the backend starts sending replies or follow-up questions to Telegram users, add the token through a secret-backed environment variable such as:

```text
TELEGRAM_BOT_TOKEN
```

The token should be configured in deployment secrets, not in source code, docs, tests, Docker Compose defaults, or pull request bodies.

## Rotation rule

If a token is pasted into chat, logs, GitHub, or any other shared place, rotate it in BotFather before using the bot in production.
