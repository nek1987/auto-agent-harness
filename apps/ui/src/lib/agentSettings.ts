const MODEL_STORAGE_PREFIX = 'agent-model'

export const DEFAULT_AGENT_MODEL = 'claude-opus-4-5-20251101'

export const AGENT_MODEL_OPTIONS = [
  'claude-opus-4-5-20251101',
  'claude-sonnet-4-20250514',
]

function buildStorageKey(projectName: string, mode?: string | null): string {
  const normalizedMode = mode && mode.trim() ? mode.trim() : 'default'
  return `${MODEL_STORAGE_PREFIX}:${projectName}:${normalizedMode}`
}

export function getAgentModel(projectName: string, mode?: string | null): string {
  try {
    const modeKey = buildStorageKey(projectName, mode)
    const stored = localStorage.getItem(modeKey)
    if (stored && stored.trim().length > 0) {
      return stored
    }
    const fallback = localStorage.getItem(buildStorageKey(projectName, 'default'))
    return fallback && fallback.trim().length > 0 ? fallback : DEFAULT_AGENT_MODEL
  } catch {
    return DEFAULT_AGENT_MODEL
  }
}

export function setAgentModel(projectName: string, model: string, mode?: string | null): void {
  const value = model.trim()
  if (!value) return
  try {
    localStorage.setItem(buildStorageKey(projectName, mode), value)
  } catch {
    // Ignore storage errors (private mode, disabled storage)
  }
}
