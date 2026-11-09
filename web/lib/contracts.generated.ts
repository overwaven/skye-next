/* Generated from src/skye/web_contracts.py. Run npm run contracts; do not edit. */

export type Payments = "telegram_stars"
export type PrivateOnly = true
export type Resources = "account_wide"
export type Retention = "until_explicit_deletion"
export type Send = true
export type Uploads = true
export type Version = 1
export type Voice = true
export type SessionUri = string
export type Headers = string | null
export type Name = string
export type Url = string
export type Code =
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "busy"
  | "quota"
  | "unavailable"
  | "provider_error"
  | "interrupted"
  | "validation"
  | "cursor_expired"
export type Message = string
export type Recovery = string
export type RequestId = string
export type Retriable = boolean
export type Cursor = string
export type Data = RunEvent | ActivityEvent | MessageEvent | ResourceEvent
export type CostMilli = number | null
export type CostState = "pending" | "settled" | "unknown"
export type DeliveryState = "pending" | "complete" | "partial" | "failed"
export type Failure = ("quota" | "provider" | "moderation" | "context" | "interrupted" | "unknown") | null
export type Id = string
export type Label = string
export type State = "accepted" | "running" | "completed" | "failed" | "cancelling" | "cancelled" | "interrupted"
export type ThreadId = string
export type Type = "run.changed"
export type Category = "web" | "image" | "voice" | "code" | "memory" | "connector" | "automation" | "tool"
export type Label1 = string
export type Sequence = number
export type Status = "running" | "completed" | "failed"
export type ToolArgs = string
export type ToolId = string
export type ToolName = string
export type ToolOutput = string
export type RunId = string
export type Type1 = "run.activity"
export type Id1 = string
export type Origin = "telegram" | "web" | "automation"
export type Text = string
export type Type2 = "text"
export type Availability = "available" | "expired" | "unresolved"
export type FileId = string
export type MediaType = string
export type Name1 = string
export type Type3 = "file"
export type Parts = (TextPart | FilePart)[]
export type Role = "user" | "assistant"
export type RunId1 = string | null
export type Sequence1 = number
export type ThreadId1 = string
export type Type4 = "message.created"
export type Resource = "project" | "thread" | "memory" | "connector" | "skill" | "account"
export type ResourceId = string
export type Type5 = "resource.changed"
export type Version1 = 1
export type Availability1 = "available" | "expired"
export type CreatedAt = number
export type Id2 = string
export type IsImage = boolean
export type MediaType1 = string
export type Name2 = string
export type Size = number
export type Media = MediaRecord[]
export type Category1 = "personal" | "preference" | "instruction" | "project" | "other"
export type Content = string
export type Revision = number | null
export type LegacyHistory = "not_backfilled" | "partial" | "empty"
export type Messages = VisibleMessage[]
export type OlderThan = number | null
export type ImageModel = string
export type MemoryEnabled = boolean
export type Model = string
export type Reasoning = "none" | "low" | "medium" | "high" | "xhigh" | "max"
export type SparksDisplay = boolean
export type Emoji = string
export type Id3 = string
export type Instructions = string
export type Name3 = string
export type Revision1 = number
export type Emoji1 = string
export type Instructions1 = string
export type Name4 = string
export type Projects = ProjectRecord[]
export type AppConsentEnabled = boolean
export type AppsConfigured = boolean
export type CredentialNames = string[]
export type Id4 = string
export type Kind = "app" | "custom"
export type Name5 = string
export type Status1 = string
export type Url1 = string
export type Connectors = ConnectorRecord[]
export type CredentialsConfigured = boolean
export type Category2 = "personal" | "preference" | "instruction" | "project" | "other"
export type Content1 = string
export type Id5 = number
export type Revision2 = number
export type Memories = MemoryRecord[]
export type MemoryEnabled1 = boolean
export type ProviderVerified = boolean
export type Scope = "personal_account"
export type Description = string
export type Files = string[]
export type Id6 = string
export type Instructions2 = string
export type Name6 = string
export type Skills = SkillRecord[]
export type Activities = ActivityRecord[]
export type DeliveryState1 = "pending" | "complete" | "partial" | "failed"
/**
 * @maxItems 20
 */
export type FileIds = string[]
export type RequestId1 = string
export type Text1 = string
export type RequestId2 = string
export type RunId2 = string
export type ThreadId2 = string
export type CsrfToken = string
export type UserId = number
export type Base64 = string | null
export type Content2 = string | null
export type Filename = string
export type Activities1 = ActivityRecord[]
export type Cursor1 = string
export type Messages1 = VisibleMessage[]
export type OlderThan1 = number | null
export type Archived = boolean
export type Id7 = string
export type Pinned = boolean
export type Preview = string
export type ProjectId = string | null
export type Revision3 = number
export type Title = string
export type Stopped = boolean
export type ProjectId1 = string | null
export type Title1 = string
export type Threads = ThreadRecord[]
export type Archived1 = boolean | null
export type Pinned1 = boolean | null
export type ProjectId2 = string | null
export type Title2 = string | null
export type Text2 = string

/**
 * Schema-generation root, not an actual API response.
 */
export interface WebContract {
  capabilities: Capabilities
  connector_verification: ConnectorVerification
  connector_write: ConnectorWrite
  error: APIError
  event: EventEnvelope
  media: MediaRecord
  media_list: MediaList
  memory_write: MemoryWrite
  message: VisibleMessage
  message_page: MessagePage
  preferences: PreferencesRecord
  project: ProjectRecord
  project_create: ProjectCreate
  project_list: ProjectList
  resources: ResourceSnapshot
  run_details: RunDetails
  send: SendRequest
  send_receipt: SendReceipt
  session: SessionRecord
  skill_record: SkillRecord
  skill_upload: SkillUpload
  snapshot: Snapshot
  stop_receipt: StopReceipt
  thread: ThreadRecord
  thread_create: ThreadCreate
  thread_list: ThreadList
  thread_update: ThreadUpdate
  transcription: Transcription
}
export interface Capabilities {
  payments?: Payments
  private_only?: PrivateOnly
  resources?: Resources
  retention?: Retention
  send?: Send
  uploads?: Uploads
  version?: Version
  voice?: Voice
}
export interface ConnectorVerification {
  session_uri: SessionUri
}
export interface ConnectorWrite {
  headers?: Headers
  name: Name
  url: Url
}
export interface APIError {
  code: Code
  field_errors?: FieldErrors
  message: Message
  recovery: Recovery
  request_id: RequestId
  retriable?: Retriable
}
export interface FieldErrors {
  [k: string]: string
}
export interface EventEnvelope {
  cursor: Cursor
  data: Data
  version?: Version1
}
export interface RunEvent {
  run: RunStatus
  type?: Type
}
export interface RunStatus {
  cost_milli?: CostMilli
  cost_state?: CostState
  delivery_state?: DeliveryState
  failure?: Failure
  id: Id
  label: Label
  state: State
  thread_id: ThreadId
}
export interface ActivityEvent {
  activity: ActivityRecord
  run_id: RunId
  type?: Type1
}
export interface ActivityRecord {
  category: Category
  label?: Label1
  sequence: Sequence
  status: Status
  tool_args?: ToolArgs
  tool_id?: ToolId
  tool_name?: ToolName
  tool_output?: ToolOutput
}
export interface MessageEvent {
  message: VisibleMessage
  type?: Type4
}
export interface VisibleMessage {
  id: Id1
  origin: Origin
  parts: Parts
  role: Role
  run_id?: RunId1
  sequence: Sequence1
  thread_id: ThreadId1
}
export interface TextPart {
  text: Text
  type?: Type2
}
export interface FilePart {
  availability: Availability
  file_id: FileId
  media_type: MediaType
  name: Name1
  type?: Type3
}
export interface ResourceEvent {
  resource: Resource
  resource_id: ResourceId
  type?: Type5
}
export interface MediaRecord {
  availability?: Availability1
  created_at: CreatedAt
  id: Id2
  is_image?: IsImage
  media_type: MediaType1
  name: Name2
  size: Size
}
export interface MediaList {
  media: Media
}
export interface MemoryWrite {
  category?: Category1
  content: Content
  revision?: Revision
}
export interface MessagePage {
  legacy_history?: LegacyHistory
  messages: Messages
  older_than?: OlderThan
}
export interface PreferencesRecord {
  image_model: ImageModel
  memory_enabled: MemoryEnabled
  model: Model
  reasoning: Reasoning
  sparks_display: SparksDisplay
}
export interface ProjectRecord {
  emoji?: Emoji
  id: Id3
  instructions: Instructions
  name: Name3
  revision: Revision1
}
export interface ProjectCreate {
  emoji?: Emoji1
  instructions?: Instructions1
  name: Name4
}
export interface ProjectList {
  projects: Projects
}
export interface ResourceSnapshot {
  app_consent_enabled?: AppConsentEnabled
  apps_configured?: AppsConfigured
  connectors?: Connectors
  credentials_configured?: CredentialsConfigured
  memories?: Memories
  memory_enabled: MemoryEnabled1
  provider_verified?: ProviderVerified
  scope?: Scope
  skills?: Skills
}
export interface ConnectorRecord {
  credential_names?: CredentialNames
  id: Id4
  kind: Kind
  name: Name5
  status: Status1
  url?: Url1
}
export interface MemoryRecord {
  category?: Category2
  content: Content1
  id: Id5
  revision: Revision2
}
export interface SkillRecord {
  description: Description
  files?: Files
  id?: Id6
  instructions?: Instructions2
  name: Name6
}
export interface RunDetails {
  activities: Activities
  delivery_state: DeliveryState1
  run: RunStatus
}
export interface SendRequest {
  file_ids?: FileIds
  request_id: RequestId1
  text: Text1
  transcripts?: Transcripts
}
export interface Transcripts {
  [k: string]: string
}
export interface SendReceipt {
  request_id: RequestId2
  run_id: RunId2
  thread_id: ThreadId2
}
export interface SessionRecord {
  csrf_token: CsrfToken
  user_id: UserId
}
export interface SkillUpload {
  base64?: Base64
  content?: Content2
  filename: Filename
}
export interface Snapshot {
  activities?: Activities1
  cursor?: Cursor1
  messages: Messages1
  older_than?: OlderThan1
  run?: RunStatus | null
  thread: ThreadRecord
}
export interface ThreadRecord {
  archived?: Archived
  id: Id7
  pinned?: Pinned
  preview?: Preview
  project_id: ProjectId
  revision: Revision3
  title: Title
}
export interface StopReceipt {
  stopped: Stopped
}
export interface ThreadCreate {
  project_id?: ProjectId1
  title: Title1
}
export interface ThreadList {
  threads: Threads
}
export interface ThreadUpdate {
  archived?: Archived1
  pinned?: Pinned1
  project_id?: ProjectId2
  title?: Title2
}
export interface Transcription {
  media: MediaRecord
  text: Text2
}
