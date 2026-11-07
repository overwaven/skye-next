"""Version-one web contracts. No HTTP listener or production migration is enabled here."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import Reasoning


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TextPart(Contract):
    type: Literal["text"] = "text"
    text: str


class FilePart(Contract):
    type: Literal["file"] = "file"
    file_id: str
    name: str
    media_type: str
    availability: Literal["available", "expired", "unresolved"]


MessagePart = Annotated[TextPart | FilePart, Field(discriminator="type")]


class VisibleMessage(Contract):
    id: str
    thread_id: str
    sequence: int = Field(ge=1)
    role: Literal["user", "assistant"]
    origin: Literal["telegram", "web", "automation"]
    parts: list[MessagePart]
    run_id: str | None = None


class ProjectRecord(Contract):
    id: str
    name: str = Field(min_length=1, max_length=64)
    instructions: str = Field(max_length=12_000)
    revision: int = Field(ge=1)


class ThreadRecord(Contract):
    id: str
    project_id: str | None
    title: str
    archived: bool = False
    revision: int = Field(ge=1)


class SessionRecord(Contract):
    user_id: int = Field(gt=0)
    csrf_token: str = Field(min_length=32)


class Capabilities(Contract):
    version: Literal[1] = 1
    private_only: Literal[True] = True
    send: Literal[False] = False
    uploads: Literal[False] = False
    payments: Literal["telegram_stars"] = "telegram_stars"
    retention: Literal["until_explicit_deletion"] = "until_explicit_deletion"
    resources: Literal["account_wide"] = "account_wide"


class PreferencesRecord(Contract):
    model: str
    image_model: str
    reasoning: Reasoning
    memory_enabled: bool
    sparks_display: bool


class ProjectList(Contract):
    projects: list[ProjectRecord]


class ThreadList(Contract):
    threads: list[ThreadRecord]


class MessagePage(Contract):
    messages: list[VisibleMessage]
    older_than: int | None = Field(default=None, ge=1)
    legacy_history: Literal["not_backfilled"] = "not_backfilled"


class SendRequest(Contract):
    request_id: str = Field(min_length=16, max_length=128)
    text: str = Field(min_length=1, max_length=32_000)
    file_ids: list[str] = Field(default_factory=list, max_length=20)


class APIError(Contract):
    code: Literal[
        "unauthenticated",
        "forbidden",
        "not_found",
        "conflict",
        "busy",
        "quota",
        "unavailable",
        "provider_error",
        "interrupted",
        "validation",
        "cursor_expired",
    ]
    message: str
    recovery: str
    request_id: str
    retriable: bool = False
    field_errors: dict[str, str] = Field(default_factory=dict)


class RunStatus(Contract):
    id: str
    thread_id: str
    state: Literal[
        "accepted", "running", "completed", "failed", "cancelling", "cancelled", "interrupted"
    ]
    label: str
    cost_milli: int | None = Field(default=None, ge=0)
    cost_state: Literal["pending", "settled", "unknown"] = "pending"


class RunEvent(Contract):
    type: Literal["run.changed"] = "run.changed"
    run: RunStatus


class MessageEvent(Contract):
    type: Literal["message.created"] = "message.created"
    message: VisibleMessage


class ResourceEvent(Contract):
    type: Literal["resource.changed"] = "resource.changed"
    resource: Literal["project", "thread", "memory", "connector", "skill", "account"]
    resource_id: str


class EventEnvelope(Contract):
    version: Literal[1] = 1
    cursor: str
    data: Annotated[RunEvent | MessageEvent | ResourceEvent, Field(discriminator="type")]


class WebContract(Contract):
    """Schema-generation root, not an actual API response."""

    project: ProjectRecord
    thread: ThreadRecord
    message: VisibleMessage
    send: SendRequest
    error: APIError
    event: EventEnvelope
    session: SessionRecord
    project_list: ProjectList
    thread_list: ThreadList
    message_page: MessagePage
    capabilities: Capabilities
    preferences: PreferencesRecord
