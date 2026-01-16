import { useState, useEffect, useId, useCallback } from 'react'
import { X, Plus, Trash2, Loader2, AlertCircle, Bug, Sparkles, Brain, Zap, AlertTriangle, Palette, PackageOpen } from 'lucide-react'
import { useCreateFeature } from '../hooks/useProjects'
import { useFeatureAnalysis } from '../hooks/useFeatureAnalysis'
import { FeatureSuggestionsPanel, type Suggestion } from './FeatureSuggestionsPanel'
import { SkillsAnalysisPanel } from './SkillsAnalysisPanel'
import { RedesignWizard } from './redesign'
import { ReferenceWizard } from './reference/ReferenceWizard'
import type { AgentStatus } from '../lib/types'
import type { SubTask } from './TaskCard'

interface ComplexityAnalysis {
  score: number
  level: 'simple' | 'medium' | 'complex'
  shouldDecompose: boolean
  reasons: string[]
  suggestedApproach: 'direct' | 'recommend_decompose' | 'require_decompose'
}

interface Step {
  id: string
  value: string
}

interface AddFeatureFormProps {
  projectName: string
  onClose: () => void
  logs: Array<{ line: string; timestamp: string }>
  agentStatus: AgentStatus
  agentMode?: string | null
}

export function AddFeatureForm({
  projectName,
  onClose,
  logs,
  agentStatus,
  agentMode,
}: AddFeatureFormProps) {
  const formId = useId()
  const [itemType, setItemType] = useState<'feature' | 'bug' | 'reference' | 'redesign'>('feature')
  const [category, setCategory] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('')
  const [steps, setSteps] = useState<Step[]>([{ id: `${formId}-step-0`, value: '' }])
  const [error, setError] = useState<string | null>(null)
  const [stepCounter, setStepCounter] = useState(1)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [useSkillsAnalysis, setUseSkillsAnalysis] = useState(false)
  const [showSkillsPanel, setShowSkillsPanel] = useState(false)
  const [isCreatingTasks, setIsCreatingTasks] = useState(false)

  // Complexity analysis state
  const [complexityAnalysis, setComplexityAnalysis] = useState<ComplexityAnalysis | null>(null)
  const [showComplexityWarning, setShowComplexityWarning] = useState(false)
  const [isAnalyzingComplexity, setIsAnalyzingComplexity] = useState(false)

  const createFeature = useCreateFeature(projectName)
  const analysis = useFeatureAnalysis(projectName)
  const isBug = itemType === 'bug'
  const isReference = itemType === 'reference'
  const isRedesign = itemType === 'redesign'

  // Auto-analyze complexity when description or steps change significantly
  const analyzeComplexity = useCallback(async () => {
    if (isBug || !name.trim() || !description.trim()) {
      setComplexityAnalysis(null)
      setShowComplexityWarning(false)
      return
    }

    const filteredSteps = steps.map(s => s.value.trim()).filter(s => s.length > 0)

    setIsAnalyzingComplexity(true)
    try {
      const response = await fetch(
        `/api/projects/${projectName}/features/analyze-complexity`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            category: category.trim() || 'uncategorized',
            name: name.trim(),
            description: description.trim(),
            steps: filteredSteps,
            item_type: 'feature',
          }),
        }
      )

      if (response.ok) {
        const result: ComplexityAnalysis = await response.json()
        setComplexityAnalysis(result)

        // Auto-enable skills analysis for complex features
        if (result.suggestedApproach === 'require_decompose') {
          setUseSkillsAnalysis(true)
          setShowComplexityWarning(true)
        } else if (result.suggestedApproach === 'recommend_decompose' && !useSkillsAnalysis) {
          setShowComplexityWarning(true)
        } else {
          setShowComplexityWarning(false)
        }
      }
    } catch (e) {
      console.error('Complexity analysis failed:', e)
    } finally {
      setIsAnalyzingComplexity(false)
    }
  }, [projectName, name, description, category, steps, isBug, useSkillsAnalysis])

  // Debounced complexity analysis
  useEffect(() => {
    const timer = setTimeout(() => {
      analyzeComplexity()
    }, 1000) // 1 second debounce

    return () => clearTimeout(timer)
  }, [name, description, category, steps, isBug])

  const handleAddStep = () => {
    setSteps([...steps, { id: `${formId}-step-${stepCounter}`, value: '' }])
    setStepCounter(stepCounter + 1)
  }

  const handleRemoveStep = (id: string) => {
    setSteps(steps.filter(step => step.id !== id))
  }

  const handleStepChange = (id: string, value: string) => {
    setSteps(steps.map(step =>
      step.id === id ? { ...step, value } : step
    ))
  }

  // Filter and get current steps
  const getFilteredSteps = () => {
    return steps
      .map(s => s.value.trim())
      .filter(s => s.length > 0)
  }

  const handleAnalyze = () => {
    setError(null)
    setShowAnalysis(true)

    const filteredSteps = getFilteredSteps()

    analysis.analyze({
      name: name.trim(),
      category: isBug ? 'bug' : category.trim(),
      description: description.trim(),
      steps: filteredSteps,
    })
  }

  const handleApplySuggestions = async (selectedSuggestions: Suggestion[]) => {
    setError(null)

    // Enhance description with selected suggestions
    let enhancedDescription = description.trim()
    const additionalSteps: string[] = []

    for (const suggestion of selectedSuggestions) {
      // Add suggestion info to description
      enhancedDescription += `\n\n[${suggestion.type.toUpperCase()}] ${suggestion.title}: ${suggestion.description}`

      // Add implementation steps
      additionalSteps.push(...suggestion.implementationSteps)
    }

    // Combine existing steps with suggestion steps
    const filteredSteps = getFilteredSteps()
    const allSteps = [
      ...filteredSteps,
      ...additionalSteps.filter(step => !filteredSteps.includes(step)),
    ]

    try {
      await createFeature.mutateAsync({
        category: isBug ? 'bug' : category.trim(),
        name: name.trim(),
        description: enhancedDescription,
        steps: allSteps.length > 0 ? allSteps : (isBug ? ['Reproduce the bug'] : []),
        priority: isBug ? 0 : (priority ? parseInt(priority, 10) : undefined),
        item_type: isBug ? 'bug' : 'feature',
      })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ' + (isBug ? 'bug' : 'feature'))
    }
  }

  const handleSkipAnalysis = () => {
    analysis.clearAnalysis()
    setShowAnalysis(false)
  }

  const handleCloseAnalysis = () => {
    analysis.clearAnalysis()
    setShowAnalysis(false)
  }

  const handleSkillsAnalyze = () => {
    setError(null)
    setShowSkillsPanel(true)
  }

  const handleSkillsTasksConfirmed = async (tasks: SubTask[]) => {
    setIsCreatingTasks(true)
    setError(null)

    try {
      // Create each task as a separate feature
      for (const task of tasks) {
        await createFeature.mutateAsync({
          category: category.trim() || 'uncategorized',
          name: task.title,
          description: task.description,
          steps: task.steps.length > 0 ? task.steps : [],
          priority: priority ? parseInt(priority, 10) : undefined,
          item_type: 'feature',
          assigned_skills: task.assignedSkills.length > 0 ? task.assignedSkills : undefined,
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create features from tasks')
    } finally {
      setIsCreatingTasks(false)
    }
  }

  const handleSkillsSkip = () => {
    setShowSkillsPanel(false)
  }

  const handleSkillsClose = () => {
    setShowSkillsPanel(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Check if complexity requires decomposition
    if (complexityAnalysis?.suggestedApproach === 'require_decompose' && !useSkillsAnalysis) {
      setError('This feature is too complex. Please enable Skills Analysis to decompose it into smaller tasks.')
      setShowComplexityWarning(true)
      return
    }

    // Filter out empty steps
    const filteredSteps = getFilteredSteps()

    try {
      await createFeature.mutateAsync({
        category: isBug ? 'bug' : category.trim(),
        name: name.trim(),
        description: description.trim(),
        steps: filteredSteps.length > 0 ? filteredSteps : (isBug ? ['Reproduce the bug'] : []),
        priority: isBug ? 0 : (priority ? parseInt(priority, 10) : undefined),
        item_type: isBug ? 'bug' : 'feature',
      })
      onClose()
    } catch (err) {
      // Handle complexity error from backend
      const errorMessage = err instanceof Error ? err.message : String(err)
      if (errorMessage.includes('complexity_requires_decomposition')) {
        setShowComplexityWarning(true)
        setUseSkillsAnalysis(true)
        setError('Feature complexity requires decomposition. Skills Analysis has been enabled.')
        return
      }
      setError(err instanceof Error ? err.message : 'Failed to create ' + (isBug ? 'bug' : 'feature'))
    }
  }

  const isValid = (isBug || category.trim()) && name.trim() && description.trim()
  const canAnalyze = !isBug && name.trim() && description.trim()

  // For reference mode, render the wizard inside the modal
  if (isReference) {
    return (
      <div className="neo-modal-backdrop" onClick={onClose}>
        <div
          className="neo-modal w-full max-w-5xl max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <ReferenceWizard projectName={projectName} onClose={onClose} />
        </div>
      </div>
    )
  }

  // For redesign mode, render the wizard inside the modal
  if (isRedesign) {
    return (
      <div className="neo-modal-backdrop" onClick={onClose}>
        <div
          className="neo-modal w-full max-w-4xl max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <RedesignWizard
            projectName={projectName}
            onClose={onClose}
            logs={logs}
            agentStatus={agentStatus}
            agentMode={agentMode}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b-3 border-[var(--color-neo-border)]">
          <h2 className="font-display text-xl sm:text-2xl font-bold">
            {isBug ? 'Report Bug' : 'Add Feature'}
          </h2>
          <button
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2 min-h-[44px] min-w-[44px]"
          >
            <X size={20} className="sm:w-6 sm:h-6" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          {/* Error Message */}
          {(error || analysis.error) && (
            <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span className="text-sm sm:text-base">{error || analysis.error}</span>
              <button
                type="button"
                onClick={() => {
                  setError(null)
                  if (analysis.error) {
                    analysis.clearAnalysis()
                  }
                }}
                className="ml-auto min-w-[32px] min-h-[32px] flex items-center justify-center"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Type Toggle: Feature / Bug / Reference / Redesign */}
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setItemType('feature')}
              className={`neo-btn flex-1 flex items-center justify-center gap-2 min-h-[48px] ${
                itemType === 'feature' ? 'neo-btn-primary' : 'neo-btn-ghost'
              }`}
            >
              <Sparkles size={18} />
              <span className="text-sm sm:text-base">Feature</span>
            </button>
            <button
              type="button"
              onClick={() => setItemType('bug')}
              className={`neo-btn flex-1 flex items-center justify-center gap-2 min-h-[48px] ${
                isBug ? 'neo-btn-danger' : 'neo-btn-ghost'
              }`}
            >
              <Bug size={18} />
              <span className="text-sm sm:text-base">Bug</span>
            </button>
            <button
              type="button"
              onClick={() => setItemType('reference')}
              className={`neo-btn flex-1 flex items-center justify-center gap-2 min-h-[48px] ${
                isReference ? 'neo-btn-secondary' : 'neo-btn-ghost'
              }`}
            >
              <PackageOpen size={18} />
              <span className="text-sm sm:text-base">Reference</span>
            </button>
            <button
              type="button"
              onClick={() => setItemType('redesign')}
              className={`neo-btn flex-1 flex items-center justify-center gap-2 min-h-[48px] ${
                isRedesign ? 'neo-btn-accent' : 'neo-btn-ghost'
              }`}
            >
              <Palette size={18} />
              <span className="text-sm sm:text-base">Redesign</span>
            </button>
          </div>

          {isBug && (
            <div className="p-3 bg-[var(--color-neo-danger)]/10 border-3 border-[var(--color-neo-danger)] text-xs sm:text-sm">
              <strong>Bug Mode:</strong> AI agent will analyze this bug and automatically create fix features.
            </div>
          )}

          {/* Category & Priority Row - hidden for bugs */}
          {!isBug && (
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              <div className="flex-1">
                <label className="block font-display font-bold mb-2 uppercase text-xs sm:text-sm">
                  Category
                </label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g., Authentication, UI, API"
                  className="neo-input min-h-[48px]"
                  required={!isBug}
                />
              </div>
              <div className="w-full sm:w-32">
                <label className="block font-display font-bold mb-2 uppercase text-xs sm:text-sm">
                  Priority
                </label>
                <input
                  type="number"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  placeholder="Auto"
                  min="1"
                  className="neo-input min-h-[48px]"
                />
              </div>
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs sm:text-sm">
              {isBug ? 'Bug Title' : 'Feature Name'}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={isBug ? "e.g., Login button not responding" : "e.g., User login form"}
              className="neo-input min-h-[48px]"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs sm:text-sm">
              {isBug ? 'Bug Description' : 'Description'}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={isBug ? "Describe what's broken and expected behavior..." : "Describe what this feature should do..."}
              className="neo-input min-h-[100px] resize-y"
              required
            />
          </div>

          {/* Steps */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs sm:text-sm">
              {isBug ? 'Steps to Reproduce (Optional)' : 'Test Steps (Optional)'}
            </label>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={step.id} className="flex gap-2">
                  <span className="neo-input w-10 sm:w-12 text-center flex-shrink-0 flex items-center justify-center min-h-[48px]">
                    {index + 1}
                  </span>
                  <input
                    type="text"
                    value={step.value}
                    onChange={(e) => handleStepChange(step.id, e.target.value)}
                    placeholder="Describe this step..."
                    className="neo-input flex-1 min-h-[48px]"
                  />
                  {steps.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveStep(step.id)}
                      className="neo-btn neo-btn-ghost p-2 min-h-[48px] min-w-[48px]"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={handleAddStep}
              className="neo-btn neo-btn-ghost mt-2 text-sm min-h-[44px]"
            >
              <Plus size={16} />
              Add Step
            </button>
          </div>

          {/* Complexity Warning */}
          {showComplexityWarning && complexityAnalysis && !isBug && (
            <div className={`p-3 border-3 ${
              complexityAnalysis.suggestedApproach === 'require_decompose'
                ? 'bg-[var(--color-neo-danger)]/10 border-[var(--color-neo-danger)]'
                : 'bg-amber-100 border-amber-500'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={18} className={
                  complexityAnalysis.suggestedApproach === 'require_decompose'
                    ? 'text-[var(--color-neo-danger)]'
                    : 'text-amber-600'
                } />
                <span className="font-display font-bold text-sm uppercase">
                  {complexityAnalysis.suggestedApproach === 'require_decompose'
                    ? 'Complex Feature - Decomposition Required'
                    : 'Medium Complexity - Decomposition Recommended'
                  }
                </span>
                {isAnalyzingComplexity && (
                  <Loader2 size={14} className="animate-spin ml-auto" />
                )}
              </div>
              <p className="text-sm font-medium mb-1">
                Complexity Score: {complexityAnalysis.score}/10
              </p>
              <ul className="text-xs space-y-0.5 text-[var(--color-neo-muted)]">
                {complexityAnalysis.reasons.slice(0, 3).map((reason, i) => (
                  <li key={i}>• {reason}</li>
                ))}
              </ul>
              {complexityAnalysis.suggestedApproach !== 'require_decompose' && (
                <button
                  type="button"
                  onClick={() => setShowComplexityWarning(false)}
                  className="text-xs underline mt-2 text-[var(--color-neo-muted)] hover:text-[var(--color-neo-text)]"
                >
                  Dismiss warning
                </button>
              )}
            </div>
          )}

          {/* Complexity indicator (small, non-intrusive) */}
          {complexityAnalysis && !showComplexityWarning && !isBug && (
            <div className="flex items-center gap-2 text-xs text-[var(--color-neo-muted)]">
              {isAnalyzingComplexity ? (
                <>
                  <Loader2 size={12} className="animate-spin" />
                  <span>Analyzing complexity...</span>
                </>
              ) : (
                <>
                  <span className={`w-2 h-2 rounded-full ${
                    complexityAnalysis.level === 'simple' ? 'bg-green-500' :
                    complexityAnalysis.level === 'medium' ? 'bg-amber-500' :
                    'bg-red-500'
                  }`} />
                  <span>
                    Complexity: {complexityAnalysis.level} ({complexityAnalysis.score}/10)
                  </span>
                  {complexityAnalysis.shouldDecompose && (
                    <button
                      type="button"
                      onClick={() => setShowComplexityWarning(true)}
                      className="underline hover:no-underline"
                    >
                      View details
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {/* Skills Analysis Toggle - only for features */}
          {!isBug && (
            <div className="p-3 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  className={`
                    w-6 h-6 border-3 border-[var(--color-neo-border)] flex items-center justify-center
                    ${useSkillsAnalysis ? 'bg-[var(--color-neo-accent)]' : 'bg-white'}
                  `}
                  onClick={() => setUseSkillsAnalysis(!useSkillsAnalysis)}
                >
                  {useSkillsAnalysis && <Zap size={14} className="text-white" strokeWidth={3} />}
                </div>
                <div className="flex-1">
                  <span className="font-display font-bold text-sm uppercase">
                    Skills Analysis
                  </span>
                  <p className="text-xs text-[var(--color-neo-muted)] mt-0.5">
                    AI подберет skills из каталога и декомпозирует задачу
                  </p>
                </div>
              </label>
            </div>
          )}

          {/* Skills Analysis Panel */}
          {showSkillsPanel && (
            <SkillsAnalysisPanel
              projectName={projectName}
              feature={{
                name: name.trim(),
                category: category.trim() || 'uncategorized',
                description: description.trim(),
                steps: getFilteredSteps(),
              }}
              onTasksConfirmed={handleSkillsTasksConfirmed}
              onSkip={handleSkillsSkip}
              onClose={handleSkillsClose}
            />
          )}

          {/* AI Analysis Panel */}
          {showAnalysis && (
            <FeatureSuggestionsPanel
              suggestions={analysis.suggestions}
              complexity={analysis.complexity}
              isAnalyzing={analysis.isAnalyzing}
              onToggleSuggestion={analysis.toggleSuggestion}
              onRemoveSuggestion={analysis.removeSuggestion}
              onEditSuggestion={analysis.editSuggestion}
              onApply={handleApplySuggestions}
              onSkip={handleSkipAnalysis}
              onClose={handleCloseAnalysis}
            />
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-4 border-t-3 border-[var(--color-neo-border)]">
            {/* AI Analyze Button - only for features */}
            {!isBug && !showAnalysis && !showSkillsPanel && (
              <button
                type="button"
                onClick={useSkillsAnalysis ? handleSkillsAnalyze : handleAnalyze}
                disabled={!canAnalyze || createFeature.isPending || isCreatingTasks}
                className={`neo-btn flex-1 min-h-[48px] justify-center ${
                  useSkillsAnalysis ? 'neo-btn-primary' : 'neo-btn-accent'
                }`}
                title={useSkillsAnalysis
                  ? "Analyze feature with skills and decompose into tasks"
                  : "Analyze feature with AI and get improvement suggestions"
                }
              >
                {useSkillsAnalysis ? <Zap size={18} /> : <Brain size={18} />}
                {useSkillsAnalysis ? 'Skills Analysis' : 'Analyze with AI'}
              </button>
            )}

            <button
              type="submit"
              disabled={!isValid || createFeature.isPending || analysis.isAnalyzing || isCreatingTasks || showSkillsPanel}
              className={`neo-btn flex-1 min-h-[48px] justify-center ${isBug ? 'neo-btn-danger' : 'neo-btn-success'}`}
            >
              {(createFeature.isPending || isCreatingTasks) ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  {isBug ? <Bug size={18} /> : <Plus size={18} />}
                  {isBug ? 'Report Bug' : 'Create Feature'}
                </>
              )}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="neo-btn neo-btn-ghost min-h-[48px] justify-center"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
