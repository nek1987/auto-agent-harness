/**
 * Import Project Modal Component
 *
 * Multi-step modal for importing existing projects:
 * 1. Enter project name
 * 2. Select existing project folder
 * 3. Choose import mode:
 *    - Quick Import (mark all features as passing)
 *    - Run Analysis (analyze codebase first)
 *    - Start Fresh (no existing features)
 */

import { useState } from 'react'
import {
  X,
  ArrowRight,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  Folder,
  Zap,
  Search,
  FileEdit,
  Download,
} from 'lucide-react'
import { useCreateProject } from '../hooks/useProjects'
import { FolderBrowser } from './FolderBrowser'
import { importFeatures, startAgent } from '../lib/api'
import { getAgentModel } from '../lib/agentSettings'

type Step = 'name' | 'folder' | 'mode' | 'importing' | 'complete'
type ImportMode = 'quick' | 'analysis' | 'fresh'

interface ImportProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated: (projectName: string) => void
}

export function ImportProjectModal({
  isOpen,
  onClose,
  onProjectCreated,
}: ImportProjectModalProps) {
  const [step, setStep] = useState<Step>('name')
  const [projectName, setProjectName] = useState('')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [importStatus, setImportStatus] = useState<string>('')
  const [importResult, setImportResult] = useState<{ passing: number; pending: number } | null>(null)

  const createProject = useCreateProject()

  if (!isOpen) return null

  const handleNameSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = projectName.trim()

    if (!trimmed) {
      setError('Please enter a project name')
      return
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      setError('Project name can only contain letters, numbers, hyphens, and underscores')
      return
    }

    setError(null)
    setStep('folder')
  }

  const handleFolderSelect = (path: string) => {
    // Use the selected path directly (existing project)
    setProjectPath(path)
    setStep('mode')
  }

  const handleFolderCancel = () => {
    setStep('name')
  }

  const handleModeSelect = async (mode: ImportMode) => {
    if (!projectPath) {
      setError('Please select a project folder first')
      setStep('folder')
      return
    }

    setStep('importing')
    setImportStatus('Registering project...')

    try {
      // Create/register the project
      await createProject.mutateAsync({
        name: projectName.trim(),
        path: projectPath,
        specMethod: 'manual',
      })

      if (mode === 'quick') {
        // Quick import: create placeholder features as passing
        setImportStatus('Importing features as implemented...')
        const result = await importFeatures(projectName.trim(), {
          features: createPlaceholderFeatures(),
          clear_existing: true,
        })
        setImportResult({ passing: result.passing, pending: result.pending })
        setStep('complete')
      } else if (mode === 'analysis') {
        // Analysis mode: start agent with analysis mode
        setImportStatus('Starting analysis agent...')
        await startAgent(projectName.trim(), { yoloMode: false, model: getAgentModel(projectName.trim(), 'coding') })
        setStep('complete')
        setTimeout(() => {
          onProjectCreated(projectName.trim())
          handleClose()
        }, 1500)
      } else {
        // Fresh start: just create project, no features
        setStep('complete')
        setTimeout(() => {
          onProjectCreated(projectName.trim())
          handleClose()
        }, 1500)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to import project')
      setStep('mode')
    }
  }

  const handleClose = () => {
    setStep('name')
    setProjectName('')
    setProjectPath(null)
    setError(null)
    setImportStatus('')
    setImportResult(null)
    onClose()
  }

  const handleBack = () => {
    if (step === 'mode') {
      setStep('folder')
    } else if (step === 'folder') {
      setStep('name')
      setProjectPath(null)
    }
  }

  const handleComplete = () => {
    onProjectCreated(projectName.trim())
    handleClose()
  }

  // Folder step uses larger modal
  if (step === 'folder') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-3xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <Folder size={24} className="text-[var(--color-neo-progress)]" />
              <div>
                <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
                  Select Project Location
                </h2>
                <p className="text-sm text-[#4a4a4a]">
                  Select the existing project directory to import
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="neo-btn neo-btn-ghost p-2"
            >
              <X size={20} />
            </button>
          </div>

          {/* Folder Browser */}
          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleFolderCancel}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="neo-modal-backdrop" onClick={handleClose}>
      <div
        className="neo-modal w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-2">
            <Download size={20} className="text-[var(--color-neo-progress)]" />
            <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
              {step === 'name' && 'Import Existing Project'}
              {step === 'mode' && 'Choose Import Mode'}
              {step === 'importing' && 'Importing...'}
              {step === 'complete' && 'Import Complete!'}
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Step 1: Project Name */}
          {step === 'name' && (
            <form onSubmit={handleNameSubmit}>
              <div className="mb-6">
                <label className="block font-bold mb-2 text-[#1a1a1a]">
                  Project Name
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="existing-app"
                  className="neo-input"
                  pattern="^[a-zA-Z0-9_-]+$"
                  autoFocus
                />
                <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                  Name to register this project under in the harness.
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  className="neo-btn neo-btn-primary"
                  disabled={!projectName.trim()}
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </form>
          )}

          {/* Step 2: Import Mode */}
          {step === 'mode' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-2">
                Project: <span className="font-mono font-bold">{projectPath}</span>
              </p>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                How would you like to import this project?
              </p>

              <div className="space-y-4">
                {/* Quick Import option */}
                <button
                  onClick={() => handleModeSelect('quick')}
                  disabled={createProject.isPending}
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-done)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <Zap size={24} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg text-[#1a1a1a]">Quick Import</span>
                        <span className="neo-badge bg-[var(--color-neo-done)] text-xs">
                          Recommended
                        </span>
                      </div>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Mark all existing features as implemented. Best when you know the project is complete.
                      </p>
                    </div>
                  </div>
                </button>

                {/* Analysis option */}
                <button
                  onClick={() => handleModeSelect('analysis')}
                  disabled={createProject.isPending}
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <Search size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[#1a1a1a]">Run Analysis First</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Let the agent analyze the codebase and identify features. Best for discovering improvements.
                      </p>
                    </div>
                  </div>
                </button>

                {/* Fresh Start option */}
                <button
                  onClick={() => handleModeSelect('fresh')}
                  disabled={createProject.isPending}
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-pending)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <FileEdit size={24} />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[#1a1a1a]">Start Fresh</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Register the project without importing features. Define features manually later.
                      </p>
                    </div>
                  </div>
                </button>
              </div>

              {error && (
                <div className="mt-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}

              <div className="flex justify-start mt-6">
                <button
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                  disabled={createProject.isPending}
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Importing */}
          {step === 'importing' && (
            <div className="text-center py-8">
              <Loader2 size={48} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
              <p className="text-[var(--color-neo-text-secondary)]">
                {importStatus}
              </p>
            </div>
          )}

          {/* Step 4: Complete */}
          {step === 'complete' && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)] shadow-[4px_4px_0px_rgba(0,0,0,1)] mb-4">
                <CheckCircle2 size={32} />
              </div>
              <h3 className="font-display font-bold text-xl mb-2">
                {projectName}
              </h3>
              <p className="text-[var(--color-neo-text-secondary)]">
                Project imported successfully!
              </p>
              {importResult && (
                <div className="mt-4 p-3 bg-[var(--color-neo-bg-secondary)] border-2 border-[var(--color-neo-border)]">
                  <p className="text-sm">
                    <span className="font-bold text-[var(--color-neo-done)]">{importResult.passing}</span> features passing
                    {importResult.pending > 0 && (
                      <>, <span className="font-bold text-[var(--color-neo-pending)]">{importResult.pending}</span> pending</>
                    )}
                  </p>
                </div>
              )}
              <button
                onClick={handleComplete}
                className="neo-btn neo-btn-primary mt-6"
              >
                Go to Project
                <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Create placeholder features for quick import.
 * These represent a typical completed project structure.
 */
function createPlaceholderFeatures() {
  return [
    {
      category: 'Core',
      name: 'Project Structure',
      description: 'Basic project structure and configuration',
      steps: ['Project initialized', 'Dependencies configured', 'Build system working'],
      passes: true,
      source_spec: 'imported',
    },
    {
      category: 'Core',
      name: 'Main Application',
      description: 'Main application entry point and routing',
      steps: ['Entry point created', 'Routing configured', 'Base layout implemented'],
      passes: true,
      source_spec: 'imported',
    },
    {
      category: 'UI',
      name: 'User Interface',
      description: 'Core UI components and styling',
      steps: ['Components created', 'Styling applied', 'Responsive design implemented'],
      passes: true,
      source_spec: 'imported',
    },
    {
      category: 'Data',
      name: 'Data Management',
      description: 'Data fetching and state management',
      steps: ['API integration', 'State management', 'Data persistence'],
      passes: true,
      source_spec: 'imported',
    },
  ]
}
