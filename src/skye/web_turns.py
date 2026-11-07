"""Web adapter over the same TurnService, runtime and MediaLibrary as Telegram."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import structlog
from agents.items import TResponseInputItem

from .attachments import (
    audio_model_parts,
    document_model_parts,
    image_input_part,
    is_audio_upload,
)
from .db import Database
from .models import ChatSettings, RequestContext, Scope
from .runtime import (
    AgentRuntime,
    RunEvent,
    RunOutput,
    leftover_reply,
    safe_tool_label,
)
from .telegram_receipts import activity_category
from .threads import MediaReceipt, ThreadStore
from .turns import Admission, BusyTurn, DuplicateRun, TurnService
from .web_contracts import (
    MediaRecord,
    SendReceipt,
    SendRequest,
    StopReceipt,
    Transcription,
)
from .web_media import MediaRef, WebMediaStore

log = structlog.get_logger()


class WebTurnRunner:
    def __init__(
        self,
        database: Database,
        runtime: AgentRuntime,
        threads: ThreadStore,
        turns: TurnService,
        media: WebMediaStore,
        *,
        max_attachment_bytes: int,
        native_media: bool = False,
        max_audio_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.database = database
        self.runtime = runtime
        self.threads = threads
        self.turns = turns
        self.media = media
        self.max_attachment_bytes = max_attachment_bytes
        self.max_audio_bytes = max_audio_bytes
        self.native_media = native_media
        self._tasks: set[asyncio.Task[object]] = set()

    async def send(self, user_id: int, thread_id: str, request: SendRequest) -> SendReceipt:
        scope = Scope("user", user_id)
        thread = await self.threads.require(scope, thread_id)
        if thread.record.archived:
            raise ValueError("Unarchive this thread before sending")
        if len(request.transcripts) > len(request.file_ids):
            raise ValueError("Transcripts must belong to attached audio")
        if any(len(value) > 32_000 for value in request.transcripts.values()):
            raise ValueError("A transcript is too long")
        if any(key not in request.file_ids for key in request.transcripts):
            raise ValueError("A transcript belongs to a missing attachment")
        refs: list[MediaRef] = []
        for media_id in request.file_ids:
            refs.append(await self.media.resolve(user_id, media_id))
        if sum(item.record.size for item in refs) > self.max_attachment_bytes * 2:
            raise ValueError("The attachments for one message are too large")
        settings = await self.database.get_settings(scope)
        name_row = await self.database.fetch_one(
            "SELECT display_name FROM known_users WHERE user_id=?", (user_id,)
        )
        context = RequestContext(
            chat_id=user_id,
            chat_type="private",
            user_id=user_id,
            display_name=(str(name_row[0]) if name_row and name_row[0] else "You"),
            conversation_thread_id=thread.record.id,
        )
        loop = asyncio.get_running_loop()
        admitted: asyncio.Future[str] = loop.create_future()

        async def operation(admission: Admission, run_id: str) -> RunOutput:
            return await self._run_web_turn(
                user_id, thread, context, settings, request, refs, admission, run_id
            )

        def on_admitted(run_id: str) -> None:
            if not admitted.done():
                admitted.set_result(run_id)

        task = asyncio.create_task(
            self.turns.execute(
                thread,
                context,
                f"web:{user_id}:{request.request_id}",
                operation,
                settings=settings,
                on_admitted=on_admitted,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        try:
            admitted_task = asyncio.ensure_future(admitted)
            done, _ = await asyncio.wait(
                {
                    cast(asyncio.Task[object], task),
                    cast(asyncio.Task[object], admitted_task),
                },
                timeout=30,
                return_when=asyncio.FIRST_COMPLETED,
            )
        except asyncio.CancelledError:
            task.cancel()
            raise
        if admitted.done():
            return SendReceipt(
                thread_id=thread.record.id,
                run_id=admitted.result(),
                request_id=request.request_id,
            )
        if task in done:
            error = task.exception()
            if isinstance(error, DuplicateRun):
                row = await self.database.fetch_one(
                    "SELECT id FROM canonical_runs WHERE requester_id=? AND request_key=?",
                    (user_id, _request_hash(f"web:{user_id}:{request.request_id}")),
                )
                if row is not None:
                    return SendReceipt(
                        thread_id=thread.record.id,
                        run_id=str(row[0]),
                        request_id=request.request_id,
                    )
            if error is not None:
                raise error
        task.cancel()
        raise BusyTurn("Skye is still starting the previous request. Try again.")

    async def _run_web_turn(
        self,
        user_id: int,
        thread: Any,
        context: RequestContext,
        settings: ChatSettings,
        request: SendRequest,
        refs: list[MediaRef],
        admission: Admission,
        run_id: str,
    ) -> RunOutput:
        sent = 0
        media_parts: list[MediaReceipt] = []
        for ref in refs:
            media_parts.append(
                MediaReceipt(
                    ref.record.name,
                    ref.record.media_type,
                    ref.record.id,
                    ref.record.size,
                    "available" if ref.record.availability == "available" else "expired",
                )
            )
        await self.threads.append(
            context.scope,
            thread.record.id,
            role="user",
            origin="web",
            text=request.text,
            receipt=f"web:user:{user_id}:{request.request_id}",
            run_id=run_id,
            media=media_parts,
        )
        content = await self._content(user_id, request, refs)

        async def on_reply(text: str, reply_to: int | None = None) -> None:
            nonlocal sent
            sent += 1
            await self.threads.append(
                context.scope,
                thread.record.id,
                role="assistant",
                origin="web",
                text=text,
                receipt=f"web:{run_id}:{sent}",
                run_id=run_id,
            )

        async def on_event(event: RunEvent) -> None:
            if event.kind == "provider_receipt":
                await self.turns.record_provider_receipt(
                    run_id, event.provider_response_id, event.usage_snapshot
                )
                return
            if event.kind not in {"tool", "activity"}:
                return
            if event.kind == "activity" and event.tool_name == "send_voice":
                label = (
                    "Recorded a voice reply"
                    if event.tool_status == "done"
                    else "Recording a voice reply"
                )
                category = "voice"
            else:
                label = safe_tool_label(event.tool_name)
                category = activity_category(event.tool_name)
            status = {"done": "completed", "error": "failed"}.get(
                event.tool_status, event.tool_status
            )
            if status not in {"running", "completed", "failed"}:
                status = "completed"
            await self.threads.record_activity(
                context.scope,
                run_id,
                category,
                status,
                label=label,
                tool_id=event.tool_id or event.tool_name,
            )
            if event.tool_name in {"remember", "forget"} and status == "completed":
                await self.threads.publish_resource(context.scope, "memory", thread.record.id)

        try:
            output = await self.runtime.run(
                context,
                settings,
                content,
                _noop,
                run_key=f"thread:{thread.record.id}",
                conversation_id=thread.session_ref,
                extra_instructions=thread.instructions,
                on_event=on_event,
                on_reply=on_reply,
                awaiting_reply=True,
                transport="web",
                canonical_run_id=run_id,
            )
            leftover = leftover_reply(output, awaiting_reply=True)
            if leftover:
                await self.threads.append(
                    context.scope,
                    thread.record.id,
                    role="assistant",
                    origin="web",
                    text=leftover,
                    receipt=f"web:{run_id}:fallback",
                    run_id=run_id,
                )
            delivered_media = await self._deliver_media(user_id, thread.record.id, run_id, output)
            await self.turns.finish_delivery(run_id, complete=True)
            await self.turns.settle_delivered(run_id, admission, output)
            if delivered_media:
                log.info("web_media_delivered", run_id=run_id, count=delivered_media)
            return output
        except BaseException:
            await self.turns.finish_delivery(run_id, complete=False)
            raise

    async def _content(
        self, user_id: int, request: SendRequest, refs: list[MediaRef]
    ) -> list[TResponseInputItem]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": request.text}]
        for ref in refs:
            _, data = await self.media.read(user_id, ref.record.id)
            name, mime = ref.record.name, ref.record.media_type
            if mime in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                content.extend(
                    [
                        {"type": "input_text", "text": f"Attached image ({name}):"},
                        image_input_part(mime, data),
                    ]
                )
            elif is_audio_upload(name, mime):
                transcript = request.transcripts.get(ref.record.id, "").strip()
                if not transcript:
                    transcript = await self.runtime.audio.transcribe(name, data, mime)  # type: ignore[union-attr]
                content.extend(
                    audio_model_parts(
                        "Attached",
                        "audio",
                        name,
                        mime,
                        data,
                        transcript,
                        native_media=self.native_media,
                    )
                )
            else:
                content.extend(
                    document_model_parts(
                        "Attached", name, mime, data, native_media=self.native_media
                    )
                )
        return cast(list[TResponseInputItem], [{"role": "user", "content": content}])

    async def _deliver_media(
        self, user_id: int, thread_id: str, run_id: str, output: RunOutput
    ) -> int:
        receipts: list[MediaReceipt] = []
        images = list(output.images)
        files = list(output.files)
        for index, data in enumerate(images, start=1):
            ref = await self.media.save_generated(
                user_id, f"image-{index}.png", data, "image/png"
            )
            receipts.append(
                MediaReceipt(
                    ref.record.name,
                    ref.record.media_type,
                    ref.record.id,
                    ref.record.size,
                    "available",
                )
            )
        for item in files:
            ref = await self.media.save_generated(user_id, item.filename, item.data)
            receipts.append(
                MediaReceipt(
                    ref.record.name,
                    ref.record.media_type,
                    ref.record.id,
                    ref.record.size,
                    "available",
                )
            )
        if not receipts:
            return 0
        await self.threads.append(
            Scope("user", user_id),
            thread_id,
            role="assistant",
            origin="web",
            text="",
            receipt=f"web:{run_id}:media",
            run_id=run_id,
            media=receipts,
        )
        return len(receipts)

    async def stop(self, user_id: int, thread_id: str) -> StopReceipt:
        stopped = await self.turns.cancel_thread(Scope("user", user_id), thread_id)
        return StopReceipt(stopped=stopped)

    async def transcribe(
        self, user_id: int, filename: str, mime: str, data: bytes
    ) -> Transcription:
        if not data:
            raise ValueError("The recording is empty.")
        if len(data) > self.max_audio_bytes:
            raise ValueError("The recording is too long.")
        if not is_audio_upload(filename, mime):
            raise ValueError("Unsupported recording format.")
        ref = await self.media.save(user_id, filename, mime, data)
        try:
            text = await self.runtime.audio.transcribe(filename, data, mime)  # type: ignore[union-attr]
        except Exception:
            await self.media.delete(user_id, ref.record.id)
            raise
        return Transcription(text=text[:32_000], media=ref.record)

    async def list_media(self, user_id: int) -> list[MediaRecord]:
        return [item.record for item in await self.media.list(user_id)]


async def _noop(_text: str) -> None:
    return


def _request_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()
