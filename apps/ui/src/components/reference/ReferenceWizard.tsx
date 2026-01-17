import { useEffect, useState, useCallback } from 'react'
import { Loader2, PackageOpen, Wand2, CheckCircle2 } from 'lucide-react'
import { ReferenceUploader } from '../redesign/ReferenceUploader'
import type { ComponentReferenceSession } from '../../lib/types'

interface ReferenceWizardProps {
  projectName: string
  onClose: () => void
}

interface GenerateFeaturesResponse {
  generated: number
  existing?: number
  feature_count?: number | null
  target_range?: {
    min: number
    max: number
    original_count: number
  }
  analysis_summary?: string
  message?: string
}

export function ReferenceWizard({ projectName, onClose }: ReferenceWizardProps) {
  const [session, setSession] = useState<ComponentReferenceSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [analysisSummary, setAnalysisSummary] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setIsLoading(true)
    setStatusMessage(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/component-reference/status`)
      if (response.ok) {
        const data = await response.json()
        setSession(data)
      } else {
        setSession(null)
      }
    } catch {
      setSession(null)
    } finally {
      setIsLoading(false)
    }
  }, [projectName])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const startSession = async () => {
    setIsStarting(true)
    setStatusMessage(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/component-reference/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_type: 'custom' }),
      })
      if (!response.ok) {
        throw new Error('Failed to start reference session')
      }
      const data = await response.json()
      setSession(data)
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Failed to start session')
    } finally {
      setIsStarting(false)
    }
  }

  const handleGenerateFeatures = async () => {
    if (!session) return

    setIsGenerating(true)
    setStatusMessage(null)
    setAnalysisSummary(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/component-reference/generate-features`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to generate features')
      }
      const data: GenerateFeaturesResponse = await response.json()
      if (data.message) {
        setStatusMessage(data.message)
      } else {
        setStatusMessage(`Generated ${data.generated} features from references`)
      }
      if (data.analysis_summary) {
        setAnalysisSummary(data.analysis_summary)
      }
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Failed to generate features')
    } finally {
      setIsGenerating(false)
    }
  }

  const componentsCount = session?.components?.length ?? 0
  const hasComponents = componentsCount > 0

  return (
    <div className="neo-card max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)]">
        <div>
          <h3 className="font-display text-lg sm:text-xl font-bold">
            Component Reference Session
          </h3>
          <p className="text-xs sm:text-sm text-[var(--color-neo-text-secondary)]">
            Upload UI components to guide future feature implementation without triggering a redesign.
          </p>
        </div>
        <button
          onClick={onClose}
          className="neo-btn neo-btn-ghost text-sm"
        >
          Close
        </button>
      </div>

      <div className="p-4 sm:p-6 space-y-6">
        {/* Session Status */}
        <div className="flex flex-wrap items-center gap-3">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-[var(--color-neo-muted)]">
              <Loader2 size={16} className="animate-spin" />
              Loading session...
            </div>
          ) : session ? (
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={16} className="text-[var(--color-neo-done)]" />
              Active session #{session.id} • {componentsCount} components
            </div>
          ) : (
            <div className="text-sm text-[var(--color-neo-muted)]">
              No active reference session yet.
            </div>
          )}
          {!session && (
            <button
              onClick={startSession}
              disabled={isStarting}
              className="neo-btn neo-btn-secondary text-sm"
            >
              {isStarting ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <PackageOpen size={16} />
              )}
              Start Session
            </button>
          )}
        </div>

        {/* Reference Uploader */}
        <ReferenceUploader
          projectName={projectName}
          references={[]}
          onReferenceAdded={fetchStatus}
          allowDesignReferences={false}
        />

        {/* Generate Features */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)]">
          <div>
            <h4 className="font-display font-bold text-sm uppercase">
              Generate Features From References
            </h4>
            <p className="text-xs text-[var(--color-neo-text-secondary)]">
              Creates implementation tasks based on uploaded components.
            </p>
          </div>
          <button
            onClick={handleGenerateFeatures}
            disabled={!hasComponents || isGenerating}
            className="neo-btn neo-btn-primary text-sm"
          >
            {isGenerating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Wand2 size={16} />
            )}
            Generate Features
          </button>
        </div>

        {statusMessage && (
          <div className="p-3 bg-[var(--color-neo-progress)]/10 border-3 border-[var(--color-neo-border)] text-sm">
            {statusMessage}
          </div>
        )}

        {analysisSummary && (
          <div className="p-3 bg-white border-3 border-[var(--color-neo-border)] text-sm text-[var(--color-neo-text-secondary)]">
            {analysisSummary}
          </div>
        )}
      </div>
    </div>
  )
}
