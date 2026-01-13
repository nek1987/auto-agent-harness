/**
 * Import Spec Modal Component
 *
 * Multi-step modal for importing an existing app_spec.txt file:
 * 1. Upload - Drag and drop or select file
 * 2. Validate - Show validation results
 * 3. Analyze (optional) - Deep analysis with Claude
 * 4. Review & Refine - Accept/reject suggestions
 * 5. Import - Import to project and start agent
 */

import { useState, useCallback } from 'react'
import {
  X,
  Upload,
  FileText,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Search,
  CheckCircle2,
  Zap,
  Play,
} from 'lucide-react'
import {
  validateSpec,
  analyzeSpec,
  refineSpec,
  importSpecToProject,
  type SpecValidationResponse,
  type SpecAnalysisResponse,
} from '../lib/api'
import { SpecAnalysisReport, type SuggestionDecisions } from './SpecAnalysisReport'

type Step = 'upload' | 'validating' | 'review' | 'analyzing' | 'refining' | 'importing' | 'complete'

interface ImportSpecModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onImportComplete: () => void
}

export function ImportSpecModal({
  isOpen,
  projectName,
  onClose,
  onImportComplete,
}: ImportSpecModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [specContent, setSpecContent] = useState<string>('')
  const [validation, setValidation] = useState<SpecValidationResponse | null>(null)
  const [analysis, setAnalysis] = useState<SpecAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [importPath, setImportPath] = useState<string>('')

  const handleClose = useCallback(() => {
    setStep('upload')
    setFile(null)
    setSpecContent('')
    setValidation(null)
    setAnalysis(null)
    setError(null)
    setIsDragging(false)
    setImportPath('')
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
    setFile(selectedFile)
    setError(null)

    // Read file content
    try {
      const content = await selectedFile.text()
      setSpecContent(content)
      setStep('validating')

      // Validate
      const result = await validateSpec(content)
      setValidation(result)
      setStep('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to read file')
      setStep('upload')
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleAnalyze = async () => {
    if (!specContent) return

    setStep('analyzing')
    setError(null)

    try {
      const result = await analyzeSpec(specContent)
      setAnalysis(result)
      setValidation(result.validation)
      setStep('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
      setStep('review')
    }
  }

  const handleRefine = async (decisions: SuggestionDecisions) => {
    if (!specContent || !analysis) return

    setStep('refining')
    setError(null)

    // Build feedback string from decisions
    const feedbackParts: string[] = []

    if (decisions.accepted.length > 0) {
      const acceptedImprovements = decisions.accepted.map(i => analysis.improvements[i]).filter(Boolean)
      if (acceptedImprovements.length > 0) {
        feedbackParts.push(`Apply these improvements: ${acceptedImprovements.join('; ')}`)
      }
    }

    if (decisions.rejected.length > 0) {
      const rejectedImprovements = decisions.rejected.map(i => analysis.improvements[i]).filter(Boolean)
      if (rejectedImprovements.length > 0) {
        feedbackParts.push(`Do NOT apply these suggestions: ${rejectedImprovements.join('; ')}`)
      }
    }

    if (decisions.customFeedback.trim()) {
      feedbackParts.push(`Additional requirements: ${decisions.customFeedback.trim()}`)
    }

    const feedback = feedbackParts.join('\n\n')

    try {
      const result = await refineSpec(specContent, feedback)
      if (result.success && result.refined_spec) {
        // Update spec content with refined version
        setSpecContent(result.refined_spec)
        // Re-validate the refined spec
        const validationResult = await validateSpec(result.refined_spec)
        setValidation(validationResult)
        // Clear analysis to allow re-analysis
        setAnalysis(null)
        setStep('review')
      } else {
        setError(result.message || 'Refinement failed')
        setStep('review')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Refinement failed')
      setStep('review')
    }
  }

  const handleImport = async () => {
    if (!specContent || !validation?.is_valid) return

    setStep('importing')
    setError(null)

    try {
      const result = await importSpecToProject(projectName, specContent)
      setImportPath(result.path)
      setStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setStep('review')
    }
  }

  const handleComplete = () => {
    onImportComplete()
    handleClose()
  }

  const handleBack = () => {
    if (step === 'review') {
      setStep('upload')
      setFile(null)
      setSpecContent('')
      setValidation(null)
      setAnalysis(null)
    }
  }

  if (!isOpen) return null

  return (
    <div className="neo-modal-backdrop" onClick={handleClose}>
      <div
        className="neo-modal w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-2">
            <FileText size={20} className="text-[var(--color-neo-progress)]" />
            <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
              {step === 'upload' && 'Import Spec File'}
              {step === 'validating' && 'Validating...'}
              {step === 'review' && 'Review Spec'}
              {step === 'analyzing' && 'Analyzing with Claude...'}
              {step === 'refining' && 'Refining Spec...'}
              {step === 'importing' && 'Importing...'}
              {step === 'complete' && 'Ready to Start!'}
            </h2>
          </div>
          <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Upload Step */}
          {step === 'upload' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-4">
                Import an existing <code className="font-mono bg-gray-100 px-1">app_spec.txt</code> file
                to project <span className="font-bold">{projectName}</span>.
              </p>

              {/* Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                  relative flex flex-col items-center justify-center
                  min-h-[200px] p-8
                  border-3 border-dashed
                  ${isDragging
                    ? 'border-[var(--color-neo-progress)] bg-blue-50'
                    : 'border-[var(--color-neo-border)] bg-[var(--color-neo-bg-secondary)]'
                  }
                  transition-colors duration-150
                `}
              >
                <Upload
                  size={48}
                  className={`
                    mb-4
                    ${isDragging ? 'text-[var(--color-neo-progress)]' : 'text-[var(--color-neo-text-secondary)]'}
                  `}
                />
                <p className="font-bold text-lg text-center mb-2">
                  Drop your app_spec.txt here
                </p>
                <p className="text-[var(--color-neo-text-secondary)] text-sm text-center mb-4">
                  or click to browse
                </p>
                <input
                  type="file"
                  accept=".txt,.xml"
                  onChange={handleInputChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <button className="neo-btn neo-btn-secondary pointer-events-none">
                  Choose File
                </button>
              </div>

              {error && (
                <div className="mt-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Validating Step */}
          {step === 'validating' && (
            <div className="text-center py-12">
              <Loader2 size={48} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                Validating spec structure...
              </p>
              {file && (
                <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2 font-mono">
                  {file.name}
                </p>
              )}
            </div>
          )}

          {/* Review Step */}
          {step === 'review' && validation && (
            <div>
              {file && (
                <div className="flex items-center gap-2 mb-4 p-3 bg-[var(--color-neo-bg-secondary)] border-2 border-[var(--color-neo-border)]">
                  <FileText size={16} />
                  <span className="font-mono text-sm">{file.name}</span>
                  <span className="text-[var(--color-neo-text-secondary)] text-sm ml-auto">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              )}

              <SpecAnalysisReport
                validation={validation}
                analysis={analysis}
                showActions={false}
                interactive={!!analysis}
                onRefine={handleRefine}
              />

              {error && (
                <div className="mt-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 mt-6 pt-4 border-t-3 border-[var(--color-neo-border)]">
                <button onClick={handleBack} className="neo-btn neo-btn-ghost">
                  <ArrowLeft size={16} />
                  Back
                </button>
                <div className="flex-1" />
                {!analysis && (
                  <button
                    onClick={handleAnalyze}
                    className="neo-btn neo-btn-secondary"
                    disabled={!validation.is_valid}
                  >
                    <Search size={16} />
                    Analyze with Claude
                  </button>
                )}
                <button
                  onClick={handleImport}
                  className="neo-btn neo-btn-primary"
                  disabled={!validation.is_valid}
                >
                  <Play size={16} />
                  Import & Start Agent
                </button>
              </div>
            </div>
          )}

          {/* Refining Step */}
          {step === 'refining' && (
            <div className="text-center py-12">
              <Loader2 size={48} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                Applying your changes...
              </p>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                Claude is refining the spec based on your feedback
              </p>
            </div>
          )}

          {/* Analyzing Step */}
          {step === 'analyzing' && (
            <div className="text-center py-12">
              <Loader2 size={48} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                Analyzing spec with Claude...
              </p>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                This may take a few seconds
              </p>
            </div>
          )}

          {/* Importing Step */}
          {step === 'importing' && (
            <div className="text-center py-12">
              <Loader2 size={48} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                Importing spec to project...
              </p>
            </div>
          )}

          {/* Complete Step */}
          {step === 'complete' && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)] shadow-[4px_4px_0px_rgba(0,0,0,1)] mb-4">
                <CheckCircle2 size={32} />
              </div>
              <h3 className="font-display font-bold text-xl mb-2">
                Spec Imported Successfully!
              </h3>
              <p className="text-[var(--color-neo-text-secondary)] mb-4">
                The spec has been imported to project <span className="font-bold">{projectName}</span>
              </p>
              {importPath && (
                <p className="text-sm font-mono text-[var(--color-neo-text-secondary)] mb-4">
                  {importPath}
                </p>
              )}
              <div className="flex items-center justify-center gap-2 p-3 bg-[var(--color-neo-progress)] bg-opacity-20 border-2 border-[var(--color-neo-progress)] rounded mb-4">
                <Zap size={18} className="text-[var(--color-neo-progress)]" />
                <span className="text-sm font-bold">
                  The initializer agent will start automatically
                </span>
              </div>
              <div className="flex justify-center gap-3 mt-6">
                <button onClick={handleClose} className="neo-btn neo-btn-ghost">
                  Close
                </button>
                <button onClick={handleComplete} className="neo-btn neo-btn-primary">
                  <Play size={16} />
                  Start Agent
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
