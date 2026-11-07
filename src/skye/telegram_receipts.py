"""Translate confirmed Telegram objects to minimal, transport-neutral transcript parts."""

from aiogram.types import Message

from .models import MediaGroupItem
from .threads import MediaReceipt


def message_media(message: Message) -> tuple[MediaReceipt, ...]:
    if message.photo:
        photo = message.photo[-1]
        return (MediaReceipt("Image", "image/jpeg", photo.file_id, photo.file_size),)
    for kind, default_name, default_mime in (
        (message.voice, "Voice message.ogg", "audio/ogg"),
        (message.audio, "Audio", "audio/mpeg"),
        (message.video, "Video.mp4", "video/mp4"),
        (message.video_note, "Video message.mp4", "video/mp4"),
        (message.animation, "Animation", "video/mp4"),
        (message.document, "Document", "application/octet-stream"),
    ):
        if kind is not None:
            return (
                MediaReceipt(
                    getattr(kind, "file_name", None) or default_name,
                    getattr(kind, "mime_type", None) or default_mime,
                    kind.file_id,
                    kind.file_size,
                ),
            )
    return ()


def album_media(item: MediaGroupItem) -> MediaReceipt:
    return MediaReceipt(
        item.file_name or {"photo": "Image", "video": "Video"}.get(item.media_kind, "Document"),
        item.mime_type
        or {"photo": "image/jpeg", "video": "video/mp4"}.get(
            item.media_kind, "application/octet-stream"
        ),
        item.file_id,
        item.file_size,
    )


def activity_category(tool_name: str) -> str:
    # Raw names from third-party tools may contain sensitive text. Unknown tools
    # collapse to a generic category; no args/output/labels are ever persisted.
    return {
        "web_search": "web",
        "web_search_call": "web",
        "generate_image": "image",
        "edit_image": "image",
        "image_generation": "image",
        "image_generation_call": "image",
        "send_voice": "voice",
        "shell": "code",
        "shell_exec": "code",
        "shell_call": "code",
        "local_shell_call": "code",
        "remember": "memory",
        "recall": "memory",
        "forget": "memory",
        "mcp_call": "connector",
        "list_automations": "automation",
        "create_scheduled_automation": "automation",
        "create_webhook_automation": "automation",
        "update_automation": "automation",
        "delete_automation": "automation",
    }.get(tool_name, "tool")
