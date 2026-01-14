/**
 * TypeScript types for the Autonomous Coding UI
 */

// Project types
export interface ProjectStats {
  passing: number
  in_progress: number
  total: number
  percentage: number
}

export interface ProjectSummary {
  name: string
  path: string
  has_spec: boolean
  stats: ProjectStats
}

export interface ProjectDetail extends ProjectSummary {
  prompts_dir: string
}

// Filesystem types
export interface DriveInfo {
  letter: string
  label: string
  available?: boolean
}

export interface DirectoryEntry {
  name: string
  path: string
  is_directory: boolean
  has_children: boolean
}

export interface DirectoryListResponse {
  current_path: string
  parent_path: string | null
  entries: DirectoryEntry[]
  drives: DriveInfo[] | null
}

export interface PathValidationResponse {
  valid: boolean
  exists: boolean
  is_directory: boolean
  can_write: boolean
  message: string
}

export interface ProjectPrompts {
  app_spec: string
  initializer_prompt: string
  coding_prompt: string
}

// Feature types
export type ItemType = 'feature' | 'bug'
export type BugStatus = 'open' | 'analyzing' | 'fixing' | 'resolved'

export interface Feature {
  id: number
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
  item_type: ItemType
  parent_bug_id: number | null
  bug_status: BugStatus | null
  assigned_skills: string[] | null
}

export interface FeatureListResponse {
  pending: Feature[]
  in_progress: Feature[]
  done: Feature[]
}

export interface FeatureCreate {
  category: string
  name: string
  description: string
  steps: string[]
  priority?: number
  item_type?: ItemType
  assigned_skills?: string[]
}

// Agent types
export type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed'

export interface AgentStatusResponse {
  status: AgentStatus
  pid: number | null
  started_at: string | null
  yolo_mode: boolean
}

export interface AgentActionResponse {
  success: boolean
  status: AgentStatus
  message: string
}

// Setup types
export interface SetupStatus {
  claude_cli: boolean
  credentials: boolean
  node: boolean
  npm: boolean
}

// WebSocket message types
export type WSMessageType = 'progress' | 'feature_update' | 'log' | 'agent_status' | 'pong' | 'activity'

export interface WSProgressMessage {
  type: 'progress'
  passing: number
  in_progress: number
  total: number
  percentage: number
}

export interface WSFeatureUpdateMessage {
  type: 'feature_update'
  feature_id: number
  passes: boolean
}

export interface WSLogMessage {
  type: 'log'
  line: string
  timestamp: string
}

export interface WSAgentStatusMessage {
  type: 'agent_status'
  status: AgentStatus
}

export interface WSPongMessage {
  type: 'pong'
}

// Activity tracking for current tool/feature execution
export type ActivityEvent = 'tool_start' | 'tool_end' | 'feature_start'

export interface WSActivityMessage {
  type: 'activity'
  event: ActivityEvent
  tool?: string           // Tool name when event is tool_start/tool_end
  feature_id?: number     // Feature ID when event is feature_start
  feature_name?: string   // Feature name when event is feature_start
  timestamp: string
}

export type WSMessage =
  | WSProgressMessage
  | WSFeatureUpdateMessage
  | WSLogMessage
  | WSAgentStatusMessage
  | WSPongMessage
  | WSActivityMessage

// ============================================================================
// Spec Chat Types
// ============================================================================

export interface SpecQuestionOption {
  label: string
  description: string
}

export interface SpecQuestion {
  question: string
  header: string
  options: SpecQuestionOption[]
  multiSelect: boolean
}

export interface SpecChatTextMessage {
  type: 'text'
  content: string
}

export interface SpecChatQuestionMessage {
  type: 'question'
  questions: SpecQuestion[]
  tool_id?: string
}

export interface SpecChatCompleteMessage {
  type: 'spec_complete'
  path: string
}

export interface SpecChatFileWrittenMessage {
  type: 'file_written'
  path: string
}

export interface SpecChatSessionCompleteMessage {
  type: 'complete'
}

export interface SpecChatErrorMessage {
  type: 'error'
  content: string
}

export interface SpecChatPongMessage {
  type: 'pong'
}

export interface SpecChatResponseDoneMessage {
  type: 'response_done'
}

export type SpecChatServerMessage =
  | SpecChatTextMessage
  | SpecChatQuestionMessage
  | SpecChatCompleteMessage
  | SpecChatFileWrittenMessage
  | SpecChatSessionCompleteMessage
  | SpecChatErrorMessage
  | SpecChatPongMessage
  | SpecChatResponseDoneMessage

// Image attachment for chat messages
export interface ImageAttachment {
  id: string
  filename: string
  mimeType: 'image/jpeg' | 'image/png'
  base64Data: string    // Raw base64 (without data: prefix)
  previewUrl: string    // data: URL for display
  size: number          // File size in bytes
}

// Text file attachment for spec analysis
export interface TextAttachment {
  id: string
  filename: string
  mimeType: 'text/plain' | 'text/markdown'
  content: string       // Raw text content (not base64)
  size: number          // File size in bytes
}

// Union type for all attachments
export type Attachment = ImageAttachment | TextAttachment

// Type guards for attachments
export function isImageAttachment(att: Attachment): att is ImageAttachment {
  return att.mimeType === 'image/jpeg' || att.mimeType === 'image/png'
}

export function isTextAttachment(att: Attachment): att is TextAttachment {
  return att.mimeType === 'text/plain' || att.mimeType === 'text/markdown'
}

// UI chat message for display
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  attachments?: ImageAttachment[]
  textAttachments?: TextAttachment[]
  timestamp: Date
  questions?: SpecQuestion[]
  isStreaming?: boolean
}

// ============================================================================
// Assistant Chat Types
// ============================================================================

export interface AssistantConversation {
  id: number
  project_name: string
  title: string | null
  created_at: string | null
  updated_at: string | null
  message_count: number
}

export interface AssistantMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string | null
}

export interface AssistantConversationDetail {
  id: number
  project_name: string
  title: string | null
  created_at: string | null
  updated_at: string | null
  messages: AssistantMessage[]
}

export interface AssistantChatTextMessage {
  type: 'text'
  content: string
}

export interface AssistantChatToolCallMessage {
  type: 'tool_call'
  tool: string
  input: Record<string, unknown>
}

export interface AssistantChatResponseDoneMessage {
  type: 'response_done'
}

export interface AssistantChatErrorMessage {
  type: 'error'
  content: string
}

export interface AssistantChatConversationCreatedMessage {
  type: 'conversation_created'
  conversation_id: number
}

export interface AssistantChatPongMessage {
  type: 'pong'
}

export type AssistantChatServerMessage =
  | AssistantChatTextMessage
  | AssistantChatToolCallMessage
  | AssistantChatResponseDoneMessage
  | AssistantChatErrorMessage
  | AssistantChatConversationCreatedMessage
  | AssistantChatPongMessage

// ============================================================================
// Import Feature Types
// ============================================================================

export interface ImportFeatureItem {
  category: string
  name: string
  description: string
  steps?: string[]
  passes?: boolean // default true for existing features
  source_spec?: string
  dependencies?: number[]
}

export interface ImportFeaturesRequest {
  features: ImportFeatureItem[]
  clear_existing?: boolean
}

export interface ImportFeaturesResponse {
  success: boolean
  imported: number
  passing: number
  pending: number
  message: string
}

// ============================================================================
// Redesign Types
// ============================================================================

export type RedesignStatus =
  | 'collecting'
  | 'extracting'
  | 'planning'
  | 'approving'
  | 'implementing'
  | 'verifying'
  | 'complete'
  | 'failed'

export type RedesignPhase =
  | 'references'
  | 'tokens'
  | 'plan'
  | 'globals'
  | 'config'
  | 'components'
  | 'pages'
  | 'verification'

export interface RedesignReference {
  type: 'image' | 'url' | 'figma'
  data: string  // base64 for image, URL string otherwise
  metadata?: {
    filename?: string
    original_url?: string
    width?: number
    height?: number
    added_at?: string
  }
}

export interface ColorScale {
  [shade: string]: string
}

export interface ColorTokens {
  primary?: ColorScale
  secondary?: ColorScale
  neutral?: ColorScale
  semantic?: {
    success?: { DEFAULT: string }
    error?: { DEFAULT: string }
    warning?: { DEFAULT: string }
    info?: { DEFAULT: string }
  }
}

export interface TypographyTokens {
  fontFamily?: {
    sans?: string[]
    serif?: string[]
    mono?: string[]
  }
  fontSize?: {
    [size: string]: { value: string }
  }
  fontWeight?: {
    [weight: string]: number
  }
}

export interface SpacingTokens {
  [key: string]: string
}

export interface BorderTokens {
  radius?: {
    [size: string]: string
  }
  width?: {
    [size: string]: string
  }
}

export interface ShadowTokens {
  [size: string]: string
}

export interface DesignTokens {
  $schema?: string
  colors?: ColorTokens
  typography?: TypographyTokens
  spacing?: SpacingTokens
  borders?: BorderTokens
  shadows?: ShadowTokens
}

export interface FileChange {
  type: string
  name?: string
  oldValue?: string
  newValue: string | object
  section?: string
}

export interface PlanFile {
  path: string
  action: 'create' | 'modify' | 'delete'
  changes: FileChange[]
}

export interface PlanPhase {
  name: string
  description: string
  files: PlanFile[]
}

export interface ChangePlan {
  output_format: string
  framework: string
  phases: PlanPhase[]
}

export interface RedesignSession {
  id: number
  project_name: string
  status: RedesignStatus
  current_phase: RedesignPhase | null
  references: RedesignReference[] | null
  extracted_tokens: DesignTokens | null
  change_plan: ChangePlan | null
  framework_detected: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export interface RedesignApproval {
  phase: string
  approved: boolean
  modifications: object | null
  comment: string | null
  approved_at: string | null
}
