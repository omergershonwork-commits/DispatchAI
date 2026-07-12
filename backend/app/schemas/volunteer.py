from typing import Literal

from pydantic import BaseModel, Field


class VolunteerWebhookAccepted(BaseModel):
    """Stable response returned after accepting a volunteer bot webhook update."""

    status: Literal["accepted"] = Field(default="accepted", description="Webhook acceptance status.")
    source: Literal["telegram_volunteer"] = Field(
        default="telegram_volunteer",
        description="Webhook source adapter.",
    )
    update_id: int = Field(description="Telegram update identifier that was accepted.")
    message_id: int | None = Field(
        default=None,
        description="Telegram message identifier, when the update contains a message.",
    )
    chat_id: int | None = Field(
        default=None,
        description="Telegram chat identifier, when the update contains a message.",
    )
    has_text: bool = Field(default=False, description="Whether the accepted update contains text content.")
    volunteer_id: int | None = Field(default=None, description="Registered volunteer identifier, when available.")
    volunteer_status: str | None = Field(default=None, description="Volunteer status after webhook processing.")
    dispatch_id: int | None = Field(default=None, description="Dispatch identifier affected by the command.")
    command_error: str | None = Field(default=None, description="Safe volunteer command processing error code.")
    telegram_reply_sent: bool = Field(default=False, description="Whether a Telegram reply was sent.")
    telegram_reply_error: str | None = Field(default=None, description="Safe Telegram reply error code.")
