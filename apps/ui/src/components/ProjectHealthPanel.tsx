import { useEffect, useState, useCallback } from 'react'
import { AlertTriangle, CheckCircle2, RefreshCw, Layers, Palette } from 'lucide-react'
import { getProjectPrompts } from '../lib/api'
import type { ProjectPrompts } from '../lib/types'

interface ProjectHealthPanelProps {
  projectName: string
}

interface ReferenceSummary {
  total: number
  activeSessionId: number | null
  activeStatus: string | null
}

interface RedesignSummary {
  status: string | null
  sessionId: number | null
}

export function ProjectHealthPanel({ projectName }: ProjectHealthPanelProps) {
  const [prompts, setPrompts] = useState<ProjectPrompts | null>(null)
  const [referenceSummary, setReferenceSummary] = useState<ReferenceSummary | null>(null)
  const [redesignSummary, setRedesignSummary] = useState<RedesignSummary | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchHealth = useCallback(async () => {
    setIsLoading(true)
    try {
      const promptsData = await getProjectPrompts(projectName)
      setPrompts(promptsData)

      const [refsResponse, statusResponse, redesignResponse] = await Promise.all([
        fetch(`/api/projects/${projectName}/component-reference/references`),
        fetch(`/api/projects/${projectName}/component-reference/status`),
        fetch(`/api/projects/${projectName}/redesign/status`),
      ])

      if (refsResponse.ok) {
        const refsData = await refsResponse.json()
        setReferenceSummary(prev => ({
          total: refsData.total ?? 0,
          activeSessionId: prev?.activeSessionId ?? null,
          activeStatus: prev?.activeStatus ?? null,
        }))
      }

      if (statusResponse.ok) {
        const statusData = await statusResponse.json()
        setReferenceSummary(prev => ({
          total: prev?.total ?? 0,
          activeSessionId: statusData.id ?? null,
          activeStatus: statusData.status ?? null,
        }))
      } else if (statusResponse.status === 404) {
        setReferenceSummary(prev => ({
          total: prev?.total ?? 0,
          activeSessionId: null,
          activeStatus: null,
        }))
      }

      if (redesignResponse.ok) {
        const redesignData = await redesignResponse.json()
        setRedesignSummary({
          status: redesignData.status ?? null,
          sessionId: redesignData.id ?? null,
        })
      } else if (redesignResponse.status === 404) {
        setRedesignSummary({ status: null, sessionId: null })
      }
    } catch {
      // Ignore errors, panel is informational
    } finally {
      setIsLoading(false)
    }
  }, [projectName])

  useEffect(() => {
    fetchHealth()
  }, [fetchHealth])

  const appSpec = prompts?.app_spec ?? ''
  const initializerPrompt = prompts?.initializer_prompt ?? ''
  const hasSpecRoot = /<project_specification>/i.test(appSpec)
  const featureCountMatch = appSpec.match(/<feature_count>(\d+)<\/feature_count>/i)
  const featureCount = featureCountMatch ? parseInt(featureCountMatch[1], 10) : null
  const hasFeatureCount = Boolean(featureCountMatch)
  const hasFeaturePlaceholder = initializerPrompt.includes('[FEATURE_COUNT]')

  const warnings: string[] = []
  if (!hasSpecRoot) warnings.push('Spec is missing <project_specification> root tag')
  if (!hasFeatureCount) warnings.push('Spec is missing <feature_count> (feature planning may be shallow)')
  if (hasFeaturePlaceholder) warnings.push('Initializer prompt still has [FEATURE_COUNT] placeholder')

  return (
    <div className="neo-card p-4 sm:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-lg font-bold uppercase">
            Project Health
          </h3>
          <p className="text-xs text-[var(--color-neo-text-secondary)]">
            Spec quality, references, and redesign status
          </p>
        </div>
        <button
          onClick={fetchHealth}
          disabled={isLoading}
          className="neo-btn neo-btn-ghost text-xs"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {warnings.length > 0 ? (
        <div className="p-3 border-3 border-[var(--color-neo-danger)] bg-[var(--color-neo-danger)]/10 text-sm space-y-1">
          <div className="flex items-center gap-2 font-bold text-[var(--color-neo-danger)]">
            <AlertTriangle size={16} />
            Spec Warnings
          </div>
          {warnings.map((warning, idx) => (
            <div key={idx} className="text-[var(--color-neo-danger)]">
              {warning}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-sm text-[var(--color-neo-done)]">
          <CheckCircle2 size={16} />
          Spec structure looks good
          {featureCount ? ` • Feature count: ${featureCount}` : ''}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-3 border-3 border-[var(--color-neo-border)] bg-white space-y-1">
          <div className="flex items-center gap-2 text-sm font-bold uppercase">
            <Layers size={16} />
            Component References
          </div>
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            {referenceSummary ? (
              <>
                {referenceSummary.total} page reference{referenceSummary.total === 1 ? '' : 's'}
                {referenceSummary.activeSessionId ? (
                  <span className="block text-xs text-[var(--color-neo-muted)]">
                    Active session #{referenceSummary.activeSessionId} ({referenceSummary.activeStatus})
                  </span>
                ) : (
                  <span className="block text-xs text-[var(--color-neo-muted)]">
                    No active session
                  </span>
                )}
              </>
            ) : (
              'Loading reference status...'
            )}
          </div>
        </div>

        <div className="p-3 border-3 border-[var(--color-neo-border)] bg-white space-y-1">
          <div className="flex items-center gap-2 text-sm font-bold uppercase">
            <Palette size={16} />
            Redesign Session
          </div>
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            {redesignSummary ? (
              redesignSummary.sessionId ? (
                <>
                  Active session #{redesignSummary.sessionId}
                  <span className="block text-xs text-[var(--color-neo-muted)]">
                    Status: {redesignSummary.status}
                  </span>
                </>
              ) : (
                'No active redesign'
              )
            ) : (
              'Loading redesign status...'
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
