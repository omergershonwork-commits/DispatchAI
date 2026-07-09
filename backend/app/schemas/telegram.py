from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.incident import IncidentExtractionResult


class TelegramUser(BaseModel):
    """Telegram user metadata included on inbound webhook messages."""

    id: int = Field(description="Telegram user identifier.")
    is_bot: bool | None = Field(default=None, description="Whether the sender is a Telegram bot.")
    first_name: str | None = Field(default=None, description="Sender first name, when Telegram includes it.")
    last_name: str | None = Field(default=None, description="Sender last name, when Telegram includes it.")
    username: str | None = Field(default=None, description="Sender Telegram username, when available.")


class TelegramChat(BaseModel):
    """Telegram chat metadata for the conversation that produced the update."""

    id: int = Field(description="Telegram chat identifier.")
    type: str = Field(description="Telegram chat type, such as private, group, supergroup, or channel.")
    title: str | None = Field(default=None, description="Group, supergroup, or channel title, when available.")
    username: str | None = Field(default=None, description="Chat username, when available.")
    first_name: str | None = Field(default=None, description="Private chat first name, when available.")
    last_name: str | None = Field(default=None, description="Private chat last name, when available.")


class TelegramMessage(BaseModel):
    """Telegram message subset required by the backend ingestion skeleton."""

    message_id: int = Field(description="Telegram message identifier inside the chat.")
    date: int = Field(description="Telegram message Unix timestamp in seconds.")
    chat: TelegramChat = Field(description="Chat that received or produced the message.")
    from_: TelegramUser | None = Field(
        default=None,
        alias="from",
        description="Telegram sender metadata. Uses alias because 'from' is reserved in Python.",
    )
    text: str | None = Field(default=None, description="Plain text message content, when the update contains text.")


class TelegramWebhookUpdate(BaseModel):
    """Top-level Telegram webhook update accepted by the ingestion endpoint."""

    update_id: int = Field(description="Unique Telegram update identifier.")
    message: TelegramMessage | None = Field(default=None, description="Telegram message payload, when the update contains a message.")


class TelegramWebhookAccepted(BaseModel):
    """Stable response returned after the backend accepts a Telegram webhook update."""

    status: Literal["accepted"] = Field(default="accepted", description="Webhook acceptance status.")
    source: Literal["telegram"] = Field(default="telegram", description="Webhook source platform.")
    update_id: int = Field(description="Telegram update identifier that was accepted.")
    message_id: int | None = Field(default=None, description="Telegram message identifier, when the update contains a message.")
    chat_id: int | None = Field(default=None, description="Telegram chat identifier, when the update contains a message.")
    has_text: bool = Field(default=False, description="Whether the accepted update contains text content.")
    extraction: IncidentExtractionResult | None = Field(default=None, description="Incident extraction result for text messages, when extraction succeeds.")
    extraction_error: str | None = Field(default=None, description="Safe extraction error code when extraction fails after webhook acceptance.")
    telegram_reply_sent: bool = Field(default=False, description="Whether a Telegram reply was sent for this webhook.")
    telegram_reply_error: str | None = Field(default=None, description="Safe Telegram reply error code when replying fails after webhook acceptance.")
