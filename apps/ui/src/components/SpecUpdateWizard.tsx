/**
 * Spec Update Wizard
 *
 * Multi-step flow to analyze a large requirements document and merge it
 * into the current app_spec with feature mapping.
 */

import { useCallback, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Loader2,
  RefreshCcw,
  Upload,
  X,
} from 'lucide-react'
import {
  analyzeSpecUpdate,
  applySpecUpdate,
  listFeatures,
} from '../lib/api'
import type {
  Feature,
  SpecUpdateAnalyzeResponse,
  SpecUpdateMatchCandidate,
} from '../lib/types'
import { getAgentModel } from '../lib/agentSettings'

interface SpecUpdateWizardProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onApplied: () => void
}

type Step = 'input' | 'analyzing' | 'review' | 'mapping' | 'applying' | 'complete'

type MappingDecision = {
  feature_key: string
  action: 'update' | 'create' | 'skip'
  existing_feature_id?: number | null
  change_type: 'cosmetic' | 'logic'
}

export function SpecUpdateWizard({
  isOpen,
  projectName,
  onClose,
  onApplied,
}: SpecUpdateWizardProps) {
  const [step, setStep] = useState<Step>('input')
  const [inputText, setInputText] = useState('')
  const [fileName, setFileName] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<SpecUpdateAnalyzeResponse | null>(null)
  const [analysisId, setAnalysisId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [mapping, setMapping] = useState<Record<string, MappingDecision>>({})
  const [existingFeatures, setExistingFeatures] = useState<Feature[]>([])
  const analysisModel = getAgentModel(projectName, 'spec_analysis')

  const handleClose = useCallback(() => {
    setStep('input')
    setInputText('')
    setFileName(null)
    setAnalysis(null)
    setAnalysisId(null)
    setError(null)
    setIsDragging(false)
    setMapping({})
    setExistingFeatures([])
    onClose()
  }, [onClose])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }, [])

  const handleFileSelect = async (selectedFile: File) => {
    setError(null)
    try {
      const content = await selectedFile.text()
      setInputText(content)
      setFileName(selectedFile.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to read file')
    }
  }

  const handleAnalyze = async () => {
    if (!inputText.trim()) {
      setError('Provide a requirements document or paste text.')
      return
    }

    setStep('analyzing')
    setError(null)

    try {
      const result = await analyzeSpecUpdate(projectName, inputText, 'merge', analysisModel)
      setAnalysis(result)
      setAnalysisId(result.analysis_id)
      setStep('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
      setStep('input')
    }
  }

  const handlePrepareMapping = async () => {
    if (!analysis) return
    setError(null)
    setStep('mapping')

    try {
      const features = await listFeatures(projectName)
      const all = [...features.pending, ...features.in_progress, ...features.done]
      setExistingFeatures(all)
      setMapping(buildInitialMapping(analysis, all))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load features')
    }
  }

  const handleApply = async () => {
    if (!analysisId || !analysis) return
    setStep('applying')
    setError(null)

    try {
      const payload = Object.values(mapping)
      await applySpecUpdate(projectName, analysisId, payload)
      setStep('complete')
      onApplied()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply update')
      setStep('mapping')
    }
  }

  const updateDecision = (featureKey: string, updates: Partial<MappingDecision>) => {
    setMapping(prev => {
      const current = prev[featureKey]
      if (!current) return prev
      return { ...prev, [featureKey]: { ...current, ...updates } }
    })
  }

  const summary = useMemo(() => {
    const decisions = Object.values(mapping)
    const created = decisions.filter(d => d.action === 'create').length
    const updated = decisions.filter(d => d.action === 'update').length
    const skipped = decisions.filter(d => d.action === 'skip').length
    const needsReview = decisions.filter(d => d.change_type === 'logic' && d.action !== 'skip').length
    return { created, updated, skipped, needsReview }
  }, [mapping])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="neo-card max-w-4xl w-full max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-neo-border)]">
          <h2 className="font-display font-bold text-xl">Update Spec</h2>
          <button onClick={handleClose} className="neo-btn neo-btn-secondary">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {step === 'input' && (
            <>
              <div className="space-y-2">
                <p className="text-[var(--color-neo-text-secondary)]">
                  Upload a markdown/text requirements document or paste the full text. The analysis will
                  extract requirements and generate a merged app_spec.
                </p>
              </div>

              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                  isDragging ? 'border-[var(--color-neo-accent)] bg-[var(--color-neo-bg-alt)]' : 'border-[var(--color-neo-border)]'
                }`}
              >
                <Upload size={32} className="mx-auto mb-3 text-[var(--color-neo-text-secondary)]" />
                <p className="text-sm text-[var(--color-neo-text-secondary)]">
                  Drop a .md or .txt file here, or choose a file.
                </p>
                <label className="neo-btn neo-btn-secondary mt-4 inline-flex items-center gap-2 cursor-pointer">
                  <FileText size={16} />
                  Select file
                  <input
                    type="file"
                    accept=".md,.txt"
                    className="hidden"
                    onChange={(e) => e.target.files && handleFileSelect(e.target.files[0])}
                  />
                </label>
                {fileName && (
                  <div className="mt-3 text-sm text-[var(--color-neo-text-secondary)]">
                    Loaded: <span className="font-mono">{fileName}</span>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-semibold mb-2">Paste requirements text</label>
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  className="neo-input w-full h-40 font-mono text-xs"
                  placeholder="Paste your full requirements document here..."
                />
              </div>

              {error && (
                <div className="neo-card bg-red-50 text-red-700 p-3">
                  {error}
                </div>
              )}
            </>
          )}

          {step === 'analyzing' && (
            <div className="text-center py-12">
              <Loader2 size={32} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                Analyzing requirements and generating merged spec...
              </p>
            </div>
          )}

          {step === 'review' && analysis && (
            <div className="space-y-6">
              <div className="neo-card bg-[var(--color-neo-bg-alt)] p-4">
                <h3 className="font-display font-bold mb-2">Coverage</h3>
                <div className="grid sm:grid-cols-2 gap-3 text-sm">
                  {analysis.coverage.map(item => (
                    <div key={item.section} className="flex items-center justify-between">
                      <span className="truncate">{item.section}</span>
                      <span className="font-mono text-[var(--color-neo-text-secondary)]">
                        {item.requirements} req / {item.chunks} chunk
                      </span>
                    </div>
                  ))}
                </div>
                {!analysis.coverage_complete && (
                  <div className="mt-3 text-sm text-[var(--color-neo-warning)]">
                    Coverage incomplete. Review the document or refine before applying.
                  </div>
                )}
              </div>

              <div className="neo-card bg-[var(--color-neo-bg-alt)] p-4">
                <h3 className="font-display font-bold mb-2">Diff Summary</h3>
                {analysis.diff.change_count === 0 ? (
                  <p className="text-sm text-[var(--color-neo-text-secondary)]">No changes detected.</p>
                ) : (
                  <ul className="text-sm space-y-1">
                    {analysis.diff.changes.map((change, idx) => (
                      <li key={`${change.section}-${idx}`} className="flex items-center gap-2">
                        <span className="font-mono">{change.section}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          change.change_type === 'logic' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {change.change_type}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <label className="block text-sm font-semibold mb-2">Proposed app_spec</label>
                <textarea
                  value={analysis.proposed_spec}
                  readOnly
                  className="neo-input w-full h-48 font-mono text-xs"
                />
              </div>

              {error && (
                <div className="neo-card bg-red-50 text-red-700 p-3">
                  {error}
                </div>
              )}
            </div>
          )}

          {step === 'mapping' && analysis && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="font-display font-bold">Feature Mapping</h3>
                <div className="text-sm text-[var(--color-neo-text-secondary)]">
                  {summary.updated} update / {summary.created} create / {summary.skipped} skip
                </div>
              </div>

              <div className="space-y-4">
                {analysis.feature_candidates.map(candidate => {
                  const decision = mapping[candidate.feature_key]
                  const options = existingFeatures
                  return (
                    <div key={candidate.feature_key} className="neo-card p-4 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-semibold">{candidate.name}</div>
                          <div className="text-sm text-[var(--color-neo-text-secondary)]">
                            {candidate.description}
                          </div>
                        </div>
                        <span className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                          {candidate.category}
                        </span>
                      </div>

                      <div className="grid sm:grid-cols-3 gap-3 text-sm">
                        <label className="flex flex-col gap-1">
                          <span className="text-[var(--color-neo-text-secondary)]">Action</span>
                          <select
                            className="neo-input"
                            value={decision?.action ?? 'create'}
                            onChange={(e) => updateDecision(candidate.feature_key, { action: e.target.value as MappingDecision['action'] })}
                          >
                            <option value="update">Update existing</option>
                            <option value="create">Create new</option>
                            <option value="skip">Skip</option>
                          </select>
                        </label>

                        <label className="flex flex-col gap-1">
                          <span className="text-[var(--color-neo-text-secondary)]">Existing feature</span>
                          <select
                            className="neo-input"
                            value={decision?.existing_feature_id ?? ''}
                            onChange={(e) => updateDecision(candidate.feature_key, { existing_feature_id: Number(e.target.value) })}
                            disabled={decision?.action !== 'update'}
                          >
                            <option value="">Select feature</option>
                            {options.map(feature => (
                              <option key={feature.id} value={feature.id}>
                                #{feature.id} {feature.name}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="flex flex-col gap-1">
                          <span className="text-[var(--color-neo-text-secondary)]">Change type</span>
                          <select
                            className="neo-input"
                            value={decision?.change_type ?? 'logic'}
                            onChange={(e) => updateDecision(candidate.feature_key, { change_type: e.target.value as MappingDecision['change_type'] })}
                            disabled={decision?.action === 'skip'}
                          >
                            <option value="cosmetic">Cosmetic</option>
                            <option value="logic">Logic</option>
                          </select>
                        </label>
                      </div>

                      {decision?.change_type === 'logic' && decision?.action !== 'skip' && (
                        <div className="text-xs text-[var(--color-neo-warning)] flex items-center gap-2">
                          <AlertTriangle size={14} /> Will be marked as needs review
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {error && (
                <div className="neo-card bg-red-50 text-red-700 p-3">
                  {error}
                </div>
              )}
            </div>
          )}

          {step === 'applying' && (
            <div className="text-center py-12">
              <Loader2 size={32} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">Applying spec update...</p>
            </div>
          )}

          {step === 'complete' && (
            <div className="text-center py-12">
              <CheckCircle2 size={32} className="mx-auto mb-4 text-[var(--color-neo-done)]" />
              <p className="font-display font-bold text-lg">Spec update applied</p>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                The app_spec and feature list have been updated.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between p-4 border-t border-[var(--color-neo-border)]">
          <div className="flex items-center gap-2 text-sm text-[var(--color-neo-text-secondary)]">
            {step === 'review' && !analysis?.coverage_complete && (
              <>
                <AlertTriangle size={16} className="text-[var(--color-neo-warning)]" />
                Coverage incomplete
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {step === 'review' && (
              <button className="neo-btn neo-btn-secondary" onClick={() => setStep('input')}>
                <ArrowLeft size={16} />
                Back
              </button>
            )}
            {step === 'mapping' && (
              <button className="neo-btn neo-btn-secondary" onClick={() => setStep('review')}>
                <ArrowLeft size={16} />
                Back
              </button>
            )}
            {step === 'input' && (
              <button className="neo-btn neo-btn-primary" onClick={handleAnalyze}>
                <RefreshCcw size={16} />
                Analyze
              </button>
            )}
            {step === 'review' && (
              <button
                className="neo-btn neo-btn-primary"
                onClick={handlePrepareMapping}
                disabled={!analysis?.coverage_complete}
              >
                Next: Mapping
              </button>
            )}
            {step === 'mapping' && (
              <button className="neo-btn neo-btn-primary" onClick={handleApply}>
                Apply Update
              </button>
            )}
            {(step === 'complete' || step === 'input') && (
              <button className="neo-btn neo-btn-secondary" onClick={handleClose}>
                Close
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function buildInitialMapping(
  analysis: SpecUpdateAnalyzeResponse,
  existingFeatures: Feature[]
): Record<string, MappingDecision> {
  const decisions: Record<string, MappingDecision> = {}

  const candidatesByKey = new Map<string, SpecUpdateMatchCandidate>()
  analysis.match_candidates.forEach(group => {
    if (group.candidates.length > 0) {
      candidatesByKey.set(group.feature_key, group.candidates[0])
    }
  })

  analysis.feature_candidates.forEach(candidate => {
    const match = candidatesByKey.get(candidate.feature_key)
    if (match) {
      decisions[candidate.feature_key] = {
        feature_key: candidate.feature_key,
        action: 'update',
        existing_feature_id: match.feature_id,
        change_type: match.change_type,
      }
    } else {
      decisions[candidate.feature_key] = {
        feature_key: candidate.feature_key,
        action: 'create',
        change_type: 'logic',
      }
    }
  })

  if (existingFeatures.length === 0) {
    return decisions
  }

  return decisions
}
