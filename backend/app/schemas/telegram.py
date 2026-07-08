from typing import Literal

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    date: int
    chat: TelegramChat
    from_: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramWebhookUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None


class TelegramWebhookAccepted(BaseModel):
    status: Literal["accepted"] = "accepted"
    source: Literal["telegram"] = "telegram"
    update_id: int
    message_id: int | None = None
    chat_id: int | None = None
    has_text: bool = False
