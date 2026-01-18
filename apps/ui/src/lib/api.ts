/**
 * API Client for the Autonomous Coding UI
 */

import type {
  ProjectSummary,
  ProjectDetail,
  ProjectPrompts,
  FeatureListResponse,
  Feature,
  FeatureCreate,
  AgentStatusResponse,
  AgentActionResponse,
  SetupStatus,
  DirectoryListResponse,
  PathValidationResponse,
  AssistantConversation,
  AssistantConversationDetail,
  ImportFeaturesRequest,
  ImportFeaturesResponse,
  SpecUpdateAnalyzeResponse,
  SpecUpdateApplyResponse,
} from './types'

const API_BASE = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// ============================================================================
// Projects API
// ============================================================================

export async function listProjects(): Promise<ProjectSummary[]> {
  return fetchJSON('/projects')
}

export async function createProject(
  name: string,
  path: string,
  specMethod: 'claude' | 'manual' = 'manual'
): Promise<ProjectSummary> {
  return fetchJSON('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, path, spec_method: specMethod }),
  })
}

export async function getProject(name: string): Promise<ProjectDetail> {
  return fetchJSON(`/projects/${encodeURIComponent(name)}`)
}

export async function deleteProject(name: string, deleteFiles: boolean = false): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(name)}?delete_files=${deleteFiles}`, {
    method: 'DELETE',
  })
}

export async function importFeatures(
  name: string,
  data: ImportFeaturesRequest
): Promise<ImportFeaturesResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(name)}/import`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getProjectPrompts(name: string): Promise<ProjectPrompts> {
  return fetchJSON(`/projects/${encodeURIComponent(name)}/prompts`)
}

export async function updateProjectPrompts(
  name: string,
  prompts: Partial<ProjectPrompts>
): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(name)}/prompts`, {
    method: 'PUT',
    body: JSON.stringify(prompts),
  })
}

// ============================================================================
// Features API
// ============================================================================

export async function listFeatures(projectName: string): Promise<FeatureListResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features`)
}

export async function createFeature(projectName: string, feature: FeatureCreate): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features`, {
    method: 'POST',
    body: JSON.stringify(feature),
  })
}

export async function getFeature(projectName: string, featureId: number): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}`)
}

export async function deleteFeature(projectName: string, featureId: number): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}`, {
    method: 'DELETE',
  })
}

export async function skipFeature(projectName: string, featureId: number): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}/skip`, {
    method: 'PATCH',
  })
}

// ============================================================================
// Agent API
// ============================================================================

export async function getAgentStatus(projectName: string): Promise<AgentStatusResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/status`)
}

export interface StartAgentOptions {
  yoloMode?: boolean
  mode?: string | null
  model?: string | null
}

export async function startAgent(
  projectName: string,
  options: StartAgentOptions = {}
): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/start`, {
    method: 'POST',
    body: JSON.stringify({
      yolo_mode: options.yoloMode ?? false,
      mode: options.mode ?? null,
      model: options.model ?? null,
    }),
  })
}

export async function stopAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/stop`, {
    method: 'POST',
  })
}

export async function pauseAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/pause`, {
    method: 'POST',
  })
}

export async function resumeAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/resume`, {
    method: 'POST',
  })
}

// ============================================================================
// Spec Creation API
// ============================================================================

export interface SpecFileStatus {
  exists: boolean
  status: 'complete' | 'in_progress' | 'not_started' | 'error' | 'unknown'
  feature_count: number | null
  timestamp: string | null
  files_written: string[]
}

export async function getSpecStatus(projectName: string): Promise<SpecFileStatus> {
  return fetchJSON(`/spec/status/${encodeURIComponent(projectName)}`)
}

// ============================================================================
// Spec Update API
// ============================================================================

export async function analyzeSpecUpdate(
  projectName: string,
  inputText: string,
  mode: 'merge' | 'rebuild' = 'merge',
  analysisModel?: string | null
): Promise<SpecUpdateAnalyzeResponse> {
  return fetchJSON('/spec/update/analyze', {
    method: 'POST',
    body: JSON.stringify({
      project_name: projectName,
      input_text: inputText,
      mode,
      analysis_model: analysisModel ?? null,
    }),
  })
}

export async function applySpecUpdate(
  projectName: string,
  analysisId: string,
  mapping: {
    feature_key: string
    action: 'update' | 'create' | 'skip'
    existing_feature_id?: number | null
    change_type?: 'cosmetic' | 'logic'
  }[],
  notes?: string
): Promise<SpecUpdateApplyResponse> {
  return fetchJSON('/spec/update/apply', {
    method: 'POST',
    body: JSON.stringify({
      project_name: projectName,
      analysis_id: analysisId,
      mapping,
      notes: notes ?? null,
    }),
  })
}

// ============================================================================
// Setup API
// ============================================================================

export async function getSetupStatus(): Promise<SetupStatus> {
  return fetchJSON('/setup/status')
}

export async function healthCheck(): Promise<{ status: string }> {
  return fetchJSON('/health')
}

// ============================================================================
// Filesystem API
// ============================================================================

export async function listDirectory(path?: string): Promise<DirectoryListResponse> {
  const params = path ? `?path=${encodeURIComponent(path)}` : ''
  return fetchJSON(`/filesystem/list${params}`)
}

export async function createDirectory(fullPath: string): Promise<{ success: boolean; path: string }> {
  // Backend expects { parent_path, name }, not { path }
  // Split the full path into parent directory and folder name

  // Remove trailing slash if present
  const normalizedPath = fullPath.endsWith('/') ? fullPath.slice(0, -1) : fullPath

  // Find the last path separator
  const lastSlash = normalizedPath.lastIndexOf('/')

  let parentPath: string
  let name: string

  // Handle Windows drive root (e.g., "C:/newfolder")
  if (lastSlash === 2 && /^[A-Za-z]:/.test(normalizedPath)) {
    // Path like "C:/newfolder" - parent is "C:/"
    parentPath = normalizedPath.substring(0, 3) // "C:/"
    name = normalizedPath.substring(3)
  } else if (lastSlash > 0) {
    parentPath = normalizedPath.substring(0, lastSlash)
    name = normalizedPath.substring(lastSlash + 1)
  } else if (lastSlash === 0) {
    // Unix root path like "/newfolder"
    parentPath = '/'
    name = normalizedPath.substring(1)
  } else {
    // No slash - invalid path
    throw new Error('Invalid path: must be an absolute path')
  }

  if (!name) {
    throw new Error('Invalid path: directory name is empty')
  }

  return fetchJSON('/filesystem/create-directory', {
    method: 'POST',
    body: JSON.stringify({ parent_path: parentPath, name }),
  })
}

export async function validatePath(path: string): Promise<PathValidationResponse> {
  return fetchJSON('/filesystem/validate', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}

// ============================================================================
// Assistant Chat API
// ============================================================================

export async function listAssistantConversations(
  projectName: string
): Promise<AssistantConversation[]> {
  return fetchJSON(`/assistant/conversations/${encodeURIComponent(projectName)}`)
}

export async function getAssistantConversation(
  projectName: string,
  conversationId: number
): Promise<AssistantConversationDetail> {
  return fetchJSON(
    `/assistant/conversations/${encodeURIComponent(projectName)}/${conversationId}`
  )
}

export async function createAssistantConversation(
  projectName: string
): Promise<AssistantConversation> {
  return fetchJSON(`/assistant/conversations/${encodeURIComponent(projectName)}`, {
    method: 'POST',
  })
}

export async function deleteAssistantConversation(
  projectName: string,
  conversationId: number
): Promise<void> {
  await fetchJSON(
    `/assistant/conversations/${encodeURIComponent(projectName)}/${conversationId}`,
    { method: 'DELETE' }
  )
}

// ============================================================================
// Spec Import API
// ============================================================================

export interface SpecValidationResponse {
  is_valid: boolean
  score: number
  has_project_name: boolean
  has_overview: boolean
  has_tech_stack: boolean
  has_feature_count: boolean
  has_core_features: boolean
  has_database_schema: boolean
  has_api_endpoints: boolean
  has_implementation_steps: boolean
  has_success_criteria: boolean
  project_name: string | null
  feature_count: number | null
  tech_stack: Record<string, string> | null
  missing_sections: string[]
  warnings: string[]
  errors: string[]
}

export interface SpecAnalysisResponse {
  validation: SpecValidationResponse
  strengths: string[]
  improvements: string[]
  critical_issues: string[]
  suggested_changes: Record<string, unknown> | null
  analysis_model: string
  analysis_timestamp: string
}

export interface SpecImportResponse {
  success: boolean
  path: string
  validation: SpecValidationResponse | null
  message: string
}

export interface SpecRefineResponse {
  success: boolean
  refined_spec: string
  message: string
}

export async function validateSpec(specContent: string): Promise<SpecValidationResponse> {
  return fetchJSON('/spec/validate', {
    method: 'POST',
    body: JSON.stringify({ spec_content: specContent }),
  })
}

export async function analyzeSpec(
  specContent: string,
  analysisModel?: string | null
): Promise<SpecAnalysisResponse> {
  return fetchJSON('/spec/analyze', {
    method: 'POST',
    body: JSON.stringify({
      spec_content: specContent,
      analysis_model: analysisModel ?? null,
    }),
  })
}

export async function importSpecToProject(
  projectName: string,
  specContent: string,
  specName: string = 'main',
  validate: boolean = true
): Promise<SpecImportResponse> {
  return fetchJSON(`/spec/import/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    body: JSON.stringify({
      spec_content: specContent,
      spec_name: specName,
      validate,
    }),
  })
}

export async function uploadSpecFile(
  projectName: string,
  file: File,
  validate: boolean = true,
  specName: string = 'main'
): Promise<SpecImportResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const params = new URLSearchParams()
  params.set('validate', String(validate))
  params.set('spec_name', specName)

  const response = await fetch(
    `${API_BASE}/spec/upload/${encodeURIComponent(projectName)}?${params}`,
    {
      method: 'POST',
      body: formData,
    }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function refineSpec(
  specContent: string,
  feedback: string,
  analysisModel?: string | null
): Promise<SpecRefineResponse> {
  return fetchJSON('/spec/refine', {
    method: 'POST',
    body: JSON.stringify({
      spec_content: specContent,
      feedback,
      analysis_model: analysisModel ?? null,
    }),
  })
}

export interface EnhanceSpecResponse {
  enhanced_spec: string
  changes_made: string[]
  message: string
}

export async function enhanceSpec(
  specContent: string,
  analysisModel?: string | null
): Promise<EnhanceSpecResponse> {
  return fetchJSON('/spec/enhance', {
    method: 'POST',
    body: JSON.stringify({
      spec_content: specContent,
      analysis_model: analysisModel ?? null,
    }),
  })
}
