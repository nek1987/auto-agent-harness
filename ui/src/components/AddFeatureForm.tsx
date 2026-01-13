import { useState, useId } from 'react'
import { X, Plus, Trash2, Loader2, AlertCircle, Bug, Sparkles } from 'lucide-react'
import { useCreateFeature } from '../hooks/useProjects'

interface Step {
  id: string
  value: string
}

interface AddFeatureFormProps {
  projectName: string
  onClose: () => void
}

export function AddFeatureForm({ projectName, onClose }: AddFeatureFormProps) {
  const formId = useId()
  const [itemType, setItemType] = useState<'feature' | 'bug'>('feature')
  const [category, setCategory] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('')
  const [steps, setSteps] = useState<Step[]>([{ id: `${formId}-step-0`, value: '' }])
  const [error, setError] = useState<string | null>(null)
  const [stepCounter, setStepCounter] = useState(1)

  const createFeature = useCreateFeature(projectName)
  const isBug = itemType === 'bug'

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Filter out empty steps
    const filteredSteps = steps
      .map(s => s.value.trim())
      .filter(s => s.length > 0)

    try {
      await createFeature.mutateAsync({
        category: isBug ? 'bug' : category.trim(),
        name: name.trim(),
        description: description.trim(),
        steps: filteredSteps.length > 0 ? filteredSteps : (isBug ? ['Reproduce the bug'] : []),
        priority: isBug ? 0 : (priority ? parseInt(priority, 10) : undefined),
        item_type: itemType,
      })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ' + (isBug ? 'bug' : 'feature'))
    }
  }

  const isValid = (isBug || category.trim()) && name.trim() && description.trim()

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
          {error && (
            <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span className="text-sm sm:text-base">{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="ml-auto min-w-[32px] min-h-[32px] flex items-center justify-center"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Type Toggle: Feature / Bug */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setItemType('feature')}
              className={`neo-btn flex-1 flex items-center justify-center gap-2 min-h-[48px] ${
                !isBug ? 'neo-btn-primary' : 'neo-btn-ghost'
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
              <span className="text-sm sm:text-base">Bug Report</span>
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

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-4 border-t-3 border-[var(--color-neo-border)]">
            <button
              type="submit"
              disabled={!isValid || createFeature.isPending}
              className={`neo-btn flex-1 min-h-[48px] justify-center ${isBug ? 'neo-btn-danger' : 'neo-btn-success'}`}
            >
              {createFeature.isPending ? (
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
