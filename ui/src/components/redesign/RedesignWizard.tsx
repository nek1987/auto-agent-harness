import { useState, useEffect } from 'react'
import {
  X,
  Upload,
  Palette,
  FileCode,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ChevronRight,
  ChevronLeft,
  Play,
} from 'lucide-react'
import { ReferenceUploader } from './ReferenceUploader'
import { DesignTokenPreview } from './DesignTokenPreview'
import { ChangePlanViewer } from './ChangePlanViewer'
import type { RedesignSession } from '../../lib/types'

interface RedesignWizardProps {
  projectName: string
  onClose: () => void
}

type WizardStep = 'references' | 'tokens' | 'plan' | 'implementing'

const STEPS: { key: WizardStep; label: string; icon: React.ElementType }[] = [
  { key: 'references', label: 'References', icon: Upload },
  { key: 'tokens', label: 'Design Tokens', icon: Palette },
  { key: 'plan', label: 'Change Plan', icon: FileCode },
  { key: 'implementing', label: 'Implementation', icon: Play },
]

export function RedesignWizard({ projectName, onClose }: RedesignWizardProps) {
  const [currentStep, setCurrentStep] = useState<WizardStep>('references')
  const [session, setSession] = useState<RedesignSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Load existing session on mount
  useEffect(() => {
    loadSession()
  }, [projectName])

  const loadSession = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/redesign/status`)
      if (response.ok) {
        const data = await response.json()
        setSession(data)
        // Set step based on session status
        if (data.status === 'collecting') setCurrentStep('references')
        else if (data.status === 'extracting' || data.status === 'planning') setCurrentStep('tokens')
        else if (data.status === 'approving') setCurrentStep('plan')
        else if (data.status === 'implementing' || data.status === 'verifying') setCurrentStep('implementing')
      } else if (response.status === 404) {
        // No active session, start fresh
        setSession(null)
      }
    } catch (err) {
      console.error('Failed to load session:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const startSession = async () => {
    setIsProcessing(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/redesign/start`, {
        method: 'POST',
      })
      if (response.ok) {
        const data = await response.json()
        setSession(data)
      } else {
        const err = await response.json()
        setError(err.detail || 'Failed to start session')
      }
    } catch (err) {
      setError('Failed to start session')
    } finally {
      setIsProcessing(false)
    }
  }

  const extractTokens = async () => {
    if (!session) return
    setIsProcessing(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/redesign/extract-tokens`, {
        method: 'POST',
      })
      if (response.ok) {
        const data = await response.json()
        setSession(prev => prev ? { ...prev, extracted_tokens: data.tokens, status: 'planning' } : null)
        setCurrentStep('tokens')
      } else {
        const err = await response.json()
        setError(err.detail || 'Failed to extract tokens')
      }
    } catch (err) {
      setError('Failed to extract tokens')
    } finally {
      setIsProcessing(false)
    }
  }

  const generatePlan = async () => {
    if (!session) return
    setIsProcessing(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/redesign/generate-plan`, {
        method: 'POST',
      })
      if (response.ok) {
        const data = await response.json()
        setSession(prev => prev ? {
          ...prev,
          change_plan: data.plan,
          framework_detected: data.framework,
          status: 'approving'
        } : null)
        setCurrentStep('plan')
      } else {
        const err = await response.json()
        setError(err.detail || 'Failed to generate plan')
      }
    } catch (err) {
      setError('Failed to generate plan')
    } finally {
      setIsProcessing(false)
    }
  }

  const approvePhase = async (phase: string) => {
    setIsProcessing(true)
    setError(null)
    try {
      const response = await fetch(`/api/projects/${projectName}/redesign/approve-phase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phase }),
      })
      if (response.ok) {
        await loadSession()
      } else {
        const err = await response.json()
        setError(err.detail || 'Failed to approve phase')
      }
    } catch (err) {
      setError('Failed to approve phase')
    } finally {
      setIsProcessing(false)
    }
  }

  const cancelSession = async () => {
    if (!confirm('Are you sure you want to cancel this redesign session?')) return
    setIsProcessing(true)
    try {
      await fetch(`/api/projects/${projectName}/redesign/cancel`, {
        method: 'DELETE',
      })
      onClose()
    } catch (err) {
      setError('Failed to cancel session')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReferenceAdded = () => {
    loadSession()
  }

  const getStepIndex = (step: WizardStep) => STEPS.findIndex(s => s.key === step)

  const canProceed = () => {
    if (currentStep === 'references') {
      return session?.references && session.references.length > 0
    }
    if (currentStep === 'tokens') {
      return session?.extracted_tokens !== null
    }
    if (currentStep === 'plan') {
      return session?.change_plan !== null
    }
    return false
  }

  const handleNext = async () => {
    if (currentStep === 'references' && canProceed()) {
      await extractTokens()
    } else if (currentStep === 'tokens' && session?.extracted_tokens) {
      await generatePlan()
    } else if (currentStep === 'plan') {
      setCurrentStep('implementing')
    }
  }

  const handleBack = () => {
    const idx = getStepIndex(currentStep)
    if (idx > 0) {
      setCurrentStep(STEPS[idx - 1].key)
    }
  }

  if (isLoading) {
    return (
      <div className="neo-modal-backdrop" onClick={onClose}>
        <div className="neo-modal w-full max-w-4xl" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-center p-12">
            <Loader2 className="animate-spin" size={32} />
            <span className="ml-3 font-display">Loading...</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-4xl max-h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <Palette className="text-[var(--color-neo-accent)]" size={24} />
            <h2 className="font-display text-xl sm:text-2xl font-bold">
              Design System Redesign
            </h2>
          </div>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
            <X size={20} />
          </button>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center justify-between px-6 py-4 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)]">
          {STEPS.map((step, idx) => {
            const isActive = step.key === currentStep
            const isPast = getStepIndex(currentStep) > idx
            const Icon = step.icon

            return (
              <div key={step.key} className="flex items-center">
                <div className={`
                  flex items-center gap-2 px-3 py-2 rounded-none border-3
                  ${isActive
                    ? 'bg-[var(--color-neo-accent)] text-white border-[var(--color-neo-border)]'
                    : isPast
                      ? 'bg-[var(--color-neo-success)] text-white border-[var(--color-neo-border)]'
                      : 'bg-white text-[var(--color-neo-muted)] border-[var(--color-neo-border)]'
                  }
                `}>
                  {isPast ? <CheckCircle2 size={16} /> : <Icon size={16} />}
                  <span className="font-display text-xs uppercase hidden sm:inline">
                    {step.label}
                  </span>
                </div>
                {idx < STEPS.length - 1 && (
                  <ChevronRight
                    className={`mx-2 ${isPast ? 'text-[var(--color-neo-success)]' : 'text-[var(--color-neo-muted)]'}`}
                    size={16}
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 p-3 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
            <AlertCircle size={18} />
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto">
              <X size={16} />
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* No Session - Start Button */}
          {!session && (
            <div className="text-center py-12">
              <Palette className="mx-auto mb-4 text-[var(--color-neo-muted)]" size={48} />
              <h3 className="font-display text-lg font-bold mb-2">
                Start a New Redesign Session
              </h3>
              <p className="text-[var(--color-neo-muted)] mb-6 max-w-md mx-auto">
                Upload reference images or URLs, and let AI extract design tokens
                to transform your project's design system.
              </p>
              <button
                onClick={startSession}
                disabled={isProcessing}
                className="neo-btn neo-btn-primary"
              >
                {isProcessing ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : (
                  <Play size={18} />
                )}
                Start Redesign Session
              </button>
            </div>
          )}

          {/* Step 1: References */}
          {session && currentStep === 'references' && (
            <ReferenceUploader
              projectName={projectName}
              references={session.references || []}
              onReferenceAdded={handleReferenceAdded}
            />
          )}

          {/* Step 2: Design Tokens */}
          {session && currentStep === 'tokens' && (
            <DesignTokenPreview
              tokens={session.extracted_tokens}
              isExtracting={session.status === 'extracting'}
            />
          )}

          {/* Step 3: Change Plan */}
          {session && currentStep === 'plan' && (
            <ChangePlanViewer
              plan={session.change_plan}
              framework={session.framework_detected}
              onApprovePhase={approvePhase}
            />
          )}

          {/* Step 4: Implementation */}
          {session && currentStep === 'implementing' && (
            <div className="text-center py-12">
              <CheckCircle2 className="mx-auto mb-4 text-[var(--color-neo-success)]" size={48} />
              <h3 className="font-display text-lg font-bold mb-2">
                Ready for Implementation
              </h3>
              <p className="text-[var(--color-neo-muted)] mb-6 max-w-md mx-auto">
                The agent will now apply the design tokens to your project.
                Start the agent to begin implementation.
              </p>
              <div className="flex items-center justify-center gap-4">
                <button
                  onClick={onClose}
                  className="neo-btn neo-btn-success"
                >
                  <Play size={18} />
                  Start Agent
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-t-3 border-[var(--color-neo-border)]">
          <div className="flex gap-2">
            {session && (
              <button
                onClick={cancelSession}
                disabled={isProcessing}
                className="neo-btn neo-btn-danger"
              >
                Cancel Session
              </button>
            )}
          </div>

          <div className="flex gap-2">
            {getStepIndex(currentStep) > 0 && (
              <button
                onClick={handleBack}
                disabled={isProcessing}
                className="neo-btn neo-btn-ghost"
              >
                <ChevronLeft size={18} />
                Back
              </button>
            )}

            {session && currentStep !== 'implementing' && (
              <button
                onClick={handleNext}
                disabled={!canProceed() || isProcessing}
                className="neo-btn neo-btn-primary"
              >
                {isProcessing ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : currentStep === 'references' ? (
                  <>
                    Extract Tokens
                    <ChevronRight size={18} />
                  </>
                ) : currentStep === 'tokens' ? (
                  <>
                    Generate Plan
                    <ChevronRight size={18} />
                  </>
                ) : (
                  <>
                    Continue
                    <ChevronRight size={18} />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
