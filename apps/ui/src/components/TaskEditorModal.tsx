import { X, Plus, Trash2 } from 'lucide-react'
import { useState, useId } from 'react'
import type { SubTask } from './TaskCard'

interface TaskEditorModalProps {
  task: SubTask
  availableSkills: string[]
  onSave: (updated: SubTask) => void
  onCancel: () => void
}

export function TaskEditorModal({
  task,
  availableSkills,
  onSave,
  onCancel,
}: TaskEditorModalProps) {
  const formId = useId()

  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [type, setType] = useState(task.type)
  const [complexity, setComplexity] = useState(task.estimatedComplexity)
  const [assignedSkills, setAssignedSkills] = useState<string[]>(task.assignedSkills)
  const [steps, setSteps] = useState<{ id: string; value: string }[]>(
    task.steps.map((s, i) => ({ id: `${formId}-step-${i}`, value: s }))
  )
  const [stepCounter, setStepCounter] = useState(task.steps.length)

  const handleAddStep = () => {
    setSteps([...steps, { id: `${formId}-step-${stepCounter}`, value: '' }])
    setStepCounter(stepCounter + 1)
  }

  const handleRemoveStep = (id: string) => {
    setSteps(steps.filter(s => s.id !== id))
  }

  const handleStepChange = (id: string, value: string) => {
    setSteps(steps.map(s => s.id === id ? { ...s, value } : s))
  }

  const toggleSkill = (skill: string) => {
    if (assignedSkills.includes(skill)) {
      setAssignedSkills(assignedSkills.filter(s => s !== skill))
    } else {
      setAssignedSkills([...assignedSkills, skill])
    }
  }

  const handleSave = () => {
    const updatedTask: SubTask = {
      ...task,
      title: title.trim(),
      description: description.trim(),
      type,
      estimatedComplexity: complexity,
      assignedSkills,
      steps: steps.map(s => s.value.trim()).filter(s => s.length > 0),
    }
    onSave(updatedTask)
  }

  const isValid = title.trim().length > 0

  return (
    <div className="neo-modal-backdrop" onClick={onCancel}>
      <div
        className="neo-modal w-full max-w-2xl max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)] sticky top-0 bg-[var(--color-neo-bg)]">
          <h2 className="font-display text-xl font-bold">Edit Task</h2>
          <button
            onClick={onCancel}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="neo-input"
              placeholder="Task title..."
            />
          </div>

          {/* Description */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="neo-input min-h-[80px] resize-y"
              placeholder="What this task accomplishes..."
            />
          </div>

          {/* Type & Complexity Row */}
          <div className="flex gap-4">
            {/* Type */}
            <div className="flex-1">
              <label className="block font-display font-bold mb-2 uppercase text-xs">
                Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as SubTask['type'])}
                className="neo-input"
              >
                <option value="implementation">Implementation</option>
                <option value="testing">Testing</option>
                <option value="documentation">Documentation</option>
              </select>
            </div>

            {/* Complexity */}
            <div className="flex-1">
              <label className="block font-display font-bold mb-2 uppercase text-xs">
                Complexity (1-10)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={complexity}
                  onChange={(e) => setComplexity(parseInt(e.target.value))}
                  className="flex-1"
                />
                <span className="w-8 text-center font-bold">{complexity}</span>
              </div>
            </div>
          </div>

          {/* Assigned Skills */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs">
              Assigned Skills
            </label>
            <div className="flex flex-wrap gap-2 p-3 border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)] max-h-32 overflow-auto">
              {availableSkills.map((skill) => (
                <button
                  key={skill}
                  type="button"
                  onClick={() => toggleSkill(skill)}
                  className={`
                    px-2 py-1 text-xs font-bold border-2 transition-all
                    ${assignedSkills.includes(skill)
                      ? 'bg-[var(--color-neo-accent)] text-white border-[var(--color-neo-accent)]'
                      : 'bg-white border-[var(--color-neo-border)] hover:border-[var(--color-neo-accent)]'
                    }
                  `}
                >
                  {skill}
                </button>
              ))}
            </div>
            {assignedSkills.length > 0 && (
              <p className="text-xs text-[var(--color-neo-muted)] mt-1">
                Selected: {assignedSkills.join(', ')}
              </p>
            )}
          </div>

          {/* Steps */}
          <div>
            <label className="block font-display font-bold mb-2 uppercase text-xs">
              Implementation Steps
            </label>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={step.id} className="flex gap-2">
                  <span className="neo-input w-10 text-center flex-shrink-0 flex items-center justify-center">
                    {index + 1}
                  </span>
                  <input
                    type="text"
                    value={step.value}
                    onChange={(e) => handleStepChange(step.id, e.target.value)}
                    className="neo-input flex-1"
                    placeholder="Describe this step..."
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveStep(step.id)}
                    className="neo-btn neo-btn-ghost p-2"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={handleAddStep}
              className="neo-btn neo-btn-ghost mt-2 text-sm"
            >
              <Plus size={16} />
              Add Step
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 p-4 border-t-3 border-[var(--color-neo-border)] sticky bottom-0 bg-[var(--color-neo-bg)]">
          <button
            type="button"
            onClick={handleSave}
            disabled={!isValid}
            className="neo-btn neo-btn-success flex-1"
          >
            Save Changes
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="neo-btn neo-btn-ghost"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
