import { useState, useEffect, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useProjects, useFeatures, useAgentStatus } from './hooks/useProjects'
import { useProjectWebSocket } from './hooks/useWebSocket'
import { useFeatureSound } from './hooks/useFeatureSound'
import { useCelebration } from './hooks/useCelebration'
import { useAuthStore, setupTokenRefresh } from './lib/auth'
import { startAgent } from './lib/api'
import { getAgentModel } from './lib/agentSettings'
import { LoginForm } from './components/LoginForm'

const STORAGE_KEY = 'auto-agent-harness-selected-project'
import { ProjectSelector } from './components/ProjectSelector'
import { KanbanBoard } from './components/KanbanBoard'
import { AgentControl } from './components/AgentControl'
import { ProgressDashboard } from './components/ProgressDashboard'
import { ProjectHealthPanel } from './components/ProjectHealthPanel'
import { AgentSettingsPanel } from './components/AgentSettingsPanel'
import { SetupWizard } from './components/SetupWizard'
import { AddFeatureForm } from './components/AddFeatureForm'
import { FeatureModal } from './components/FeatureModal'
import { DebugLogViewer } from './components/DebugLogViewer'
import { AgentThought } from './components/AgentThought'
import { ActivityPanel } from './components/ActivityPanel'
import { AssistantFAB } from './components/AssistantFAB'
import { AssistantPanel } from './components/AssistantPanel'
import { ImportSpecModal } from './components/ImportSpecModal'
import { SpecCreationChat } from './components/SpecCreationChat'
import { Plus, Loader2, LogOut, FileQuestion, Upload, Bot } from 'lucide-react'
import type { Feature } from './lib/types'

function App() {
  // Authentication state
  const { isAuthenticated, user, logout, checkAuth } = useAuthStore()
  const [authChecked, setAuthChecked] = useState(false)
  const queryClient = useQueryClient()

  // Initialize selected project from localStorage
  const [selectedProject, setSelectedProject] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })
  const [showAddFeature, setShowAddFeature] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [setupComplete, setSetupComplete] = useState(true) // Start optimistic
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288) // Default height
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [showImportSpecModal, setShowImportSpecModal] = useState(false)
  const [showSpecChat, setShowSpecChat] = useState(false)

  // Check authentication on mount
  useEffect(() => {
    const check = async () => {
      await checkAuth()
      setAuthChecked(true)
    }
    check()

    // Setup automatic token refresh
    const cleanup = setupTokenRefresh()
    return cleanup
  }, [checkAuth])

  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: features } = useFeatures(selectedProject)
  const { data: agentStatusData } = useAgentStatus(selectedProject)
  const wsState = useProjectWebSocket(selectedProject)

  // Play sounds when features move between columns
  useFeatureSound(features)

  // Celebrate when all features are complete
  useCelebration(features, selectedProject)

  // Persist selected project to localStorage
  const handleSelectProject = useCallback((project: string | null) => {
    setSelectedProject(project)
    try {
      if (project) {
        localStorage.setItem(STORAGE_KEY, project)
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // localStorage not available
    }
  }, [])

  // Handle project deletion - refresh project list
  const handleProjectDeleted = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['projects'] })
  }, [queryClient])

  // Handle spec import completion
  const handleSpecImportComplete = useCallback(async () => {
    setShowImportSpecModal(false)
    // Refresh projects to update has_spec status
    await queryClient.invalidateQueries({ queryKey: ['projects'] })
    // Auto-start the initializer agent
    if (selectedProject) {
      try {
        await startAgent(selectedProject, { yoloMode: false, model: getAgentModel(selectedProject, 'coding') })
      } catch (err) {
        console.error('Failed to start agent after spec import:', err)
      }
    }
  }, [queryClient, selectedProject])

  // Handle spec creation completion via Claude chat
  const handleSpecComplete = useCallback(async (_specPath: string, yoloMode: boolean = false) => {
    setShowSpecChat(false)
    // Refresh projects to update has_spec status
    await queryClient.invalidateQueries({ queryKey: ['projects'] })
    // Auto-start the initializer agent
    if (selectedProject) {
      try {
        await startAgent(selectedProject, { yoloMode, model: getAgentModel(selectedProject, 'coding') })
      } catch (err) {
        console.error('Failed to start agent after spec creation:', err)
      }
    }
  }, [queryClient, selectedProject])

  // Validate stored project exists (clear if project was deleted)
  useEffect(() => {
    if (selectedProject && projects && !projects.some(p => p.name === selectedProject)) {
      handleSelectProject(null)
    }
  }, [selectedProject, projects, handleSelectProject])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      // D : Toggle debug window
      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault()
        setDebugOpen(prev => !prev)
      }

      // N : Add new feature (when project selected)
      if ((e.key === 'n' || e.key === 'N') && selectedProject) {
        e.preventDefault()
        setShowAddFeature(true)
      }

      // A : Toggle assistant panel (when project selected)
      if ((e.key === 'a' || e.key === 'A') && selectedProject) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
      }

      // Escape : Close modals
      if (e.key === 'Escape') {
        if (showSpecChat) {
          setShowSpecChat(false)
        } else if (showImportSpecModal) {
          setShowImportSpecModal(false)
        } else if (assistantOpen) {
          setAssistantOpen(false)
        } else if (showAddFeature) {
          setShowAddFeature(false)
        } else if (selectedFeature) {
          setSelectedFeature(null)
        } else if (debugOpen) {
          setDebugOpen(false)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedProject, showAddFeature, selectedFeature, debugOpen, assistantOpen, showSpecChat, showImportSpecModal])

  // Combine WebSocket progress with feature data
  const progress = wsState.progress.total > 0 ? wsState.progress : {
    passing: features?.done.length ?? 0,
    total: (features?.pending.length ?? 0) + (features?.in_progress.length ?? 0) + (features?.done.length ?? 0),
    percentage: 0,
  }

  if (progress.total > 0 && progress.percentage === 0) {
    progress.percentage = Math.round((progress.passing / progress.total) * 100 * 10) / 10
  }

  // Show loading spinner while checking auth
  if (!authChecked) {
    return (
      <div className="min-h-screen bg-[var(--color-neo-bg)] flex items-center justify-center">
        <Loader2 size={48} className="animate-spin text-[var(--color-neo-progress)]" />
      </div>
    )
  }

  // Show login form if not authenticated
  if (!isAuthenticated) {
    return <LoginForm />
  }

  if (!setupComplete) {
    return <SetupWizard onComplete={() => setSetupComplete(true)} />
  }

  return (
    <div className="min-h-screen bg-[var(--color-neo-bg)]">
      {/* Header */}
      <header className="bg-[var(--color-neo-text)] text-white border-b-4 border-[var(--color-neo-border)]">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            {/* Logo and Title */}
            <div className="flex items-center justify-between sm:justify-start gap-2 sm:gap-4">
              <h1 className="font-display text-lg sm:text-2xl font-bold tracking-tight uppercase">
                Auto Agent Harness
              </h1>
              {user && (
                <span className="text-xs sm:text-sm text-white/70">
                  {user.username}
                </span>
              )}
            </div>

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-2 sm:gap-4">
              <ProjectSelector
                projects={projects ?? []}
                selectedProject={selectedProject}
                onSelectProject={handleSelectProject}
                onProjectDeleted={handleProjectDeleted}
                isLoading={projectsLoading}
              />

              {selectedProject && (
                <>
                  <button
                    onClick={() => setShowAddFeature(true)}
                    className="neo-btn neo-btn-primary text-xs sm:text-sm min-h-[44px]"
                    title="Press N"
                  >
                    <Plus size={18} />
                    <span className="hidden sm:inline">Add Feature</span>
                    <span className="sm:hidden">Add</span>
                    <kbd className="hidden sm:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
                      N
                    </kbd>
                  </button>

                  <AgentControl
                    projectName={selectedProject}
                    status={wsState.agentStatus}
                    yoloMode={agentStatusData?.yolo_mode ?? false}
                    mode={agentStatusData?.mode ?? null}
                    lastLogTimestamp={wsState.logs.length > 0 ? wsState.logs[wsState.logs.length - 1].timestamp : null}
                  />
                </>
              )}

              {/* Logout Button */}
              <button
                onClick={logout}
                className="neo-btn text-sm bg-white/10 hover:bg-white/20 text-white border-white/30 min-h-[44px] min-w-[44px]"
                title="Logout"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main
        className="max-w-7xl mx-auto px-4 py-8"
        style={{ paddingBottom: debugOpen ? debugPanelHeight + 32 : undefined }}
      >
        {!selectedProject ? (
          <div className="neo-empty-state mt-12">
            <h2 className="font-display text-2xl font-bold mb-2">
              Welcome to Auto Agent Harness
            </h2>
            <p className="text-[var(--color-neo-text-secondary)] mb-4">
              Select a project from the dropdown above or create a new one to get started.
            </p>
          </div>
        ) : (() => {
          // Find the selected project data
          const selectedProjectData = projects?.find(p => p.name === selectedProject)
          const hasNoSpec = selectedProjectData && selectedProjectData.has_spec === false

          // Show NoSpecState if project has no spec
          if (hasNoSpec) {
            return (
              <div className="neo-card p-12 text-center max-w-2xl mx-auto mt-12">
                <FileQuestion size={64} className="mx-auto mb-6 text-[var(--color-neo-text-secondary)]" />
                <h2 className="font-display text-2xl font-bold mb-3">
                  No Specification Found
                </h2>
                <p className="text-[var(--color-neo-text-secondary)] mb-8">
                  To start working on this project, you need an app specification.
                  You can import an existing spec file or create one interactively with Claude.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <button
                    onClick={() => setShowImportSpecModal(true)}
                    className="neo-btn neo-btn-secondary"
                  >
                    <Upload size={18} />
                    Import Spec File
                  </button>
                  <button
                    onClick={() => setShowSpecChat(true)}
                    className="neo-btn neo-btn-primary"
                  >
                    <Bot size={18} />
                    Create with Claude
                  </button>
                </div>
              </div>
            )
          }

          return (
            <div className="space-y-8">
              {/* Progress Dashboard */}
              <ProgressDashboard
                passing={progress.passing}
                total={progress.total}
                percentage={progress.percentage}
                isConnected={wsState.isConnected}
              />

              <ProjectHealthPanel projectName={selectedProject} />

              <AgentSettingsPanel projectName={selectedProject} />

              {/* Agent Thought - shows latest agent narrative */}
              <AgentThought
                logs={wsState.logs}
                agentStatus={wsState.agentStatus}
              />

              {/* Activity Panel - shows current tool and feature */}
              <ActivityPanel
                logs={wsState.logs}
                agentStatus={wsState.agentStatus}
              />

              {/* Initializing Features State - show when agent is running but no features yet */}
              {features &&
               features.pending.length === 0 &&
               features.in_progress.length === 0 &&
               features.done.length === 0 &&
               wsState.agentStatus === 'running' && (
                <div className="neo-card p-8 text-center">
                  <Loader2 size={32} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
                  <h3 className="font-display font-bold text-xl mb-2">
                    Initializing Features...
                  </h3>
                  <p className="text-[var(--color-neo-text-secondary)]">
                    The agent is reading your spec and creating features. This may take a moment.
                  </p>
                </div>
              )}

              {/* Kanban Board */}
              <KanbanBoard
                features={features}
                onFeatureClick={setSelectedFeature}
              />
            </div>
          )
        })()}
      </main>

      {/* Add Feature Modal */}
      {showAddFeature && selectedProject && (
        <AddFeatureForm
          projectName={selectedProject}
          onClose={() => setShowAddFeature(false)}
          logs={wsState.logs}
          agentStatus={wsState.agentStatus}
          agentMode={agentStatusData?.mode ?? null}
        />
      )}

      {/* Feature Detail Modal */}
      {selectedFeature && selectedProject && (
        <FeatureModal
          feature={selectedFeature}
          projectName={selectedProject}
          onClose={() => setSelectedFeature(null)}
        />
      )}

      {/* Debug Log Viewer - fixed to bottom */}
      {selectedProject && (
        <DebugLogViewer
          logs={wsState.logs}
          isOpen={debugOpen}
          onToggle={() => setDebugOpen(!debugOpen)}
          onClear={wsState.clearLogs}
          onHeightChange={setDebugPanelHeight}
        />
      )}

      {/* Assistant FAB and Panel */}
      {selectedProject && (
        <>
          <AssistantFAB
            onClick={() => setAssistantOpen(!assistantOpen)}
            isOpen={assistantOpen}
          />
          <AssistantPanel
            projectName={selectedProject}
            isOpen={assistantOpen}
            onClose={() => setAssistantOpen(false)}
          />
        </>
      )}

      {/* Import Spec Modal */}
      {showImportSpecModal && selectedProject && (
        <ImportSpecModal
          isOpen={showImportSpecModal}
          projectName={selectedProject}
          onClose={() => setShowImportSpecModal(false)}
          onImportComplete={handleSpecImportComplete}
        />
      )}

      {/* Spec Creation Chat (full-screen) */}
      {showSpecChat && selectedProject && (
        <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
          <SpecCreationChat
            projectName={selectedProject}
            onComplete={handleSpecComplete}
            onCancel={() => setShowSpecChat(false)}
            onExitToProject={() => setShowSpecChat(false)}
          />
        </div>
      )}
    </div>
  )
}

export default App
