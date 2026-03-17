from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- vk_updates queue (poller → game) ---


class VkMessageNew(BaseModel):
    type: Literal["message_new"]
    chat_id: int
    user_id: int
    text: str
    ts: int


class VkMessageEvent(BaseModel):
    type: Literal["message_event"]
    chat_id: int
    user_id: int
    event_id: str
    payload: dict
    ts: int


VkUpdate = Annotated[VkMessageNew | VkMessageEvent, Field(discriminator="type")]


# --- vk_outgoing queue (game → mailbox) ---


class EventAnswer(BaseModel):
    event_id: str
    user_id: int
    text: str


class OutgoingMessage(BaseModel):
    peer_id: int  # 2_000_000_000 + chat_id for group chats
    text: str
    keyboard: dict | None = None
    event_answer: EventAnswer | None = None
    # When set, mailbox echoes the sent message_id back via vk_sent_callbacks
    correlation_id: str | None = None
    # When set, mailbox deletes this cmid (conversation message id) instead of sending
    delete_cmid: int | None = None


# --- vk_sent_callbacks queue (mailbox → game) ---


class VkSentCallback(BaseModel):
    correlation_id: str
    peer_id: int
    message_id: int
