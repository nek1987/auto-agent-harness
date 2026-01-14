import { useState, useMemo } from 'react'
import { X, Loader2, ChevronRight, Check, Sparkles, ListTodo, AlertCircle } from 'lucide-react'
import { SkillCard, type SkillMatch } from './SkillCard'
import { TaskCard, type SubTask } from './TaskCard'
import { TaskEditorModal } from './TaskEditorModal'
import { useSkillsAnalysis } from '../hooks/useSkillsAnalysis'

interface SkillsAnalysisPanelProps {
  projectName: string
  feature: {
    name: string
    category: string
    description: string
    steps: string[]
  }
  onTasksConfirmed: (tasks: SubTask[]) => void
  onSkip: () => void
  onClose: () => void
}

type Step = 'analyzing' | 'selecting_skills' | 'decomposing' | 'reviewing_tasks'

export function SkillsAnalysisPanel({
  projectName,
  feature,
  onTasksConfirmed,
  onSkip,
  onClose,
}: SkillsAnalysisPanelProps) {
  const [currentStep, setCurrentStep] = useState<Step>('analyzing')
  const [selectedSkillIds, setSelectedSkillIds] = useState<Set<string>>(new Set())
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set())
  const [editingTask, setEditingTask] = useState<SubTask | null>(null)
  const [tasks, setTasks] = useState<SubTask[]>([])

  const analysis = useSkillsAnalysis(projectName)

  // Start analysis when component mounts
  useState(() => {
    analysis.analyze(feature)
  })

  // Update step based on analysis state
  useMemo(() => {
    if (analysis.skills.length > 0 && currentStep === 'analyzing') {
      setCurrentStep('selecting_skills')
      // Pre-select primary skills
      const primaryIds = new Set(
        analysis.skills
          .filter(s => s.relevanceScore >= 0.5)
          .slice(0, 5)
          .map(s => s.name)
      )
      setSelectedSkillIds(primaryIds)
    }

    if (analysis.tasks.length > 0 && currentStep === 'decomposing') {
      setCurrentStep('reviewing_tasks')
      setTasks(analysis.tasks)
      // Pre-select main tasks (not extensions)
      const mainIds = new Set(
        analysis.tasks.filter(t => !t.isExtension).map(t => t.id)
      )
      setSelectedTaskIds(mainIds)
    }
  }, [analysis.skills, analysis.tasks, currentStep])

  const toggleSkill = (skillId: string) => {
    const newSelected = new Set(selectedSkillIds)
    if (newSelected.has(skillId)) {
      newSelected.delete(skillId)
    } else {
      newSelected.add(skillId)
    }
    setSelectedSkillIds(newSelected)
  }

  const toggleTask = (taskId: string) => {
    const newSelected = new Set(selectedTaskIds)
    if (newSelected.has(taskId)) {
      newSelected.delete(taskId)
    } else {
      newSelected.add(taskId)
    }
    setSelectedTaskIds(newSelected)
  }

  const handleConfirmSkills = () => {
    if (selectedSkillIds.size === 0) return

    setCurrentStep('decomposing')
    analysis.decompose(Array.from(selectedSkillIds))
  }

  const handleConfirmTasks = () => {
    const selectedTasks = tasks.filter(t => selectedTaskIds.has(t.id))
    onTasksConfirmed(selectedTasks)
  }

  const handleUpdateTask = (updated: SubTask) => {
    setTasks(tasks.map(t => t.id === updated.id ? updated : t))
    setEditingTask(null)
  }

  const handleRemoveTask = (taskId: string) => {
    setTasks(tasks.filter(t => t.id !== taskId))
    selectedTaskIds.delete(taskId)
    setSelectedTaskIds(new Set(selectedTaskIds))
  }

  // Get all assigned skills for task editor
  const allAssignedSkills = useMemo(() => {
    const skills = new Set<string>()
    analysis.skills.forEach(s => skills.add(s.name))
    return Array.from(skills)
  }, [analysis.skills])

  // Separate tasks into main and extensions
  const mainTasks = tasks.filter(t => !t.isExtension)
  const extensionTasks = tasks.filter(t => t.isExtension)

  // Step indicator component
  const StepIndicator = () => (
    <div className="flex items-center gap-2 text-xs">
      <span className={`
        px-2 py-1 font-bold uppercase border-2
        ${currentStep === 'analyzing' || currentStep === 'selecting_skills'
          ? 'bg-[var(--color-neo-accent)] text-white border-[var(--color-neo-accent)]'
          : 'bg-[var(--color-neo-success)]/20 border-[var(--color-neo-success)]'
        }
      `}>
        1. Skills
      </span>
      <ChevronRight size={14} />
      <span className={`
        px-2 py-1 font-bold uppercase border-2
        ${currentStep === 'decomposing' || currentStep === 'reviewing_tasks'
          ? 'bg-[var(--color-neo-accent)] text-white border-[var(--color-neo-accent)]'
          : 'bg-[var(--color-neo-bg-alt)] border-[var(--color-neo-border)]'
        }
      `}>
        2. Tasks
      </span>
    </div>
  )

  return (
    <div className="border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)] shadow-neo">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
        <div className="flex items-center gap-3">
          <Sparkles size={20} className="text-[var(--color-neo-accent)]" />
          <h3 className="font-display font-bold text-lg">Skills Analysis</h3>
          <StepIndicator />
        </div>
        <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
          <X size={18} />
        </button>
      </div>

      {/* Error Message */}
      {analysis.error && (
        <div className="m-4 p-3 flex items-center gap-2 bg-[var(--color-neo-danger)]/10 border-3 border-[var(--color-neo-danger)]">
          <AlertCircle size={18} className="text-[var(--color-neo-danger)]" />
          <span className="text-sm">{analysis.error}</span>
        </div>
      )}

      {/* Content */}
      <div className="p-4 max-h-[60vh] overflow-auto">
        {/* Step 1: Analyzing */}
        {currentStep === 'analyzing' && (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 size={32} className="animate-spin text-[var(--color-neo-accent)]" />
            <p className="mt-4 font-display font-bold">Analyzing feature...</p>
            <p className="text-sm text-[var(--color-neo-muted)]">
              {analysis.status || 'Selecting relevant skills from catalog'}
            </p>
          </div>
        )}

        {/* Step 2: Selecting Skills */}
        {currentStep === 'selecting_skills' && (
          <div className="space-y-4">
            <div>
              <h4 className="font-display font-bold uppercase text-sm flex items-center gap-2">
                <Check size={16} className="text-[var(--color-neo-success)]" />
                Primary Skills ({analysis.skills.filter(s => s.relevanceScore >= 0.5).length})
              </h4>
              <p className="text-xs text-[var(--color-neo-muted)] mb-3">
                Highly relevant skills for this feature
              </p>
              <div className="grid gap-2">
                {analysis.skills
                  .filter(s => s.relevanceScore >= 0.5)
                  .slice(0, 5)
                  .map(skill => (
                    <SkillCard
                      key={skill.name}
                      skill={skill}
                      selected={selectedSkillIds.has(skill.name)}
                      onToggle={() => toggleSkill(skill.name)}
                    />
                  ))}
              </div>
            </div>

            {analysis.skills.filter(s => s.relevanceScore < 0.5).length > 0 && (
              <div>
                <h4 className="font-display font-bold uppercase text-sm">
                  Secondary Skills ({analysis.skills.filter(s => s.relevanceScore < 0.5).length})
                </h4>
                <p className="text-xs text-[var(--color-neo-muted)] mb-3">
                  Additional skills that may be useful
                </p>
                <div className="grid gap-2">
                  {analysis.skills
                    .filter(s => s.relevanceScore < 0.5)
                    .slice(0, 10)
                    .map(skill => (
                      <SkillCard
                        key={skill.name}
                        skill={skill}
                        selected={selectedSkillIds.has(skill.name)}
                        onToggle={() => toggleSkill(skill.name)}
                        compact
                      />
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Decomposing */}
        {currentStep === 'decomposing' && (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 size={32} className="animate-spin text-[var(--color-neo-accent)]" />
            <p className="mt-4 font-display font-bold">Decomposing feature...</p>
            <p className="text-sm text-[var(--color-neo-muted)]">
              {analysis.status || 'Generating tasks with selected skills'}
            </p>
          </div>
        )}

        {/* Step 4: Reviewing Tasks */}
        {currentStep === 'reviewing_tasks' && (
          <div className="space-y-4">
            {mainTasks.length > 0 && (
              <div>
                <h4 className="font-display font-bold uppercase text-sm flex items-center gap-2">
                  <ListTodo size={16} className="text-[var(--color-neo-accent)]" />
                  Main Tasks ({mainTasks.length})
                </h4>
                <p className="text-xs text-[var(--color-neo-muted)] mb-3">
                  Core implementation tasks for this feature
                </p>
                <div className="grid gap-2">
                  {mainTasks.map(task => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      selected={selectedTaskIds.has(task.id)}
                      onToggle={() => toggleTask(task.id)}
                      onEdit={() => setEditingTask(task)}
                      onRemove={() => handleRemoveTask(task.id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {extensionTasks.length > 0 && (
              <div>
                <h4 className="font-display font-bold uppercase text-sm">
                  Extension Tasks ({extensionTasks.length})
                </h4>
                <p className="text-xs text-[var(--color-neo-muted)] mb-3">
                  Optional enhancements and improvements
                </p>
                <div className="grid gap-2">
                  {extensionTasks.map(task => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      selected={selectedTaskIds.has(task.id)}
                      onToggle={() => toggleTask(task.id)}
                      onEdit={() => setEditingTask(task)}
                      onRemove={() => handleRemoveTask(task.id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="p-3 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
              <p className="text-sm">
                <span className="font-bold">Selected:</span>{' '}
                {selectedTaskIds.size} of {tasks.length} tasks
              </p>
              {analysis.decompositionResult && (
                <p className="text-xs text-[var(--color-neo-muted)] mt-1">
                  Total complexity: {analysis.decompositionResult.totalComplexity} |{' '}
                  Est. time: {analysis.decompositionResult.estimatedTime}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3 p-4 border-t-3 border-[var(--color-neo-border)]">
        {currentStep === 'selecting_skills' && (
          <>
            <button
              type="button"
              onClick={handleConfirmSkills}
              disabled={selectedSkillIds.size === 0 || analysis.isLoading}
              className="neo-btn neo-btn-primary flex-1"
            >
              {analysis.isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <>
                  Confirm Selection ({selectedSkillIds.size})
                  <ChevronRight size={16} />
                </>
              )}
            </button>
            <button type="button" onClick={onSkip} className="neo-btn neo-btn-ghost">
              Skip
            </button>
          </>
        )}

        {currentStep === 'reviewing_tasks' && (
          <>
            <button
              type="button"
              onClick={handleConfirmTasks}
              disabled={selectedTaskIds.size === 0}
              className="neo-btn neo-btn-success flex-1"
            >
              Add Selected ({selectedTaskIds.size})
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedTaskIds(new Set(tasks.map(t => t.id)))
              }}
              className="neo-btn neo-btn-primary"
            >
              Select All ({tasks.length})
            </button>
            <button type="button" onClick={onSkip} className="neo-btn neo-btn-ghost">
              Skip
            </button>
          </>
        )}

        {(currentStep === 'analyzing' || currentStep === 'decomposing') && (
          <button type="button" onClick={onSkip} className="neo-btn neo-btn-ghost flex-1">
            Cancel
          </button>
        )}
      </div>

      {/* Task Editor Modal */}
      {editingTask && (
        <TaskEditorModal
          task={editingTask}
          availableSkills={allAssignedSkills}
          onSave={handleUpdateTask}
          onCancel={() => setEditingTask(null)}
        />
      )}
    </div>
  )
}
