import { Check, ChevronDown, ChevronUp, Edit2, Trash2, Link } from 'lucide-react'
import { useState } from 'react'

export interface SubTask {
  id: string
  title: string
  description: string
  type: 'implementation' | 'testing' | 'documentation'
  estimatedComplexity: number
  assignedSkills: string[]
  dependencies: string[]
  steps: string[]
  isExtension: boolean
}

interface TaskCardProps {
  task: SubTask
  selected: boolean
  onToggle: () => void
  onEdit: () => void
  onRemove: () => void
  disabled?: boolean
}

export function TaskCard({
  task,
  selected,
  onToggle,
  onEdit,
  onRemove,
  disabled = false,
}: TaskCardProps) {
  const [expanded, setExpanded] = useState(false)

  // Complexity indicator dots
  const ComplexityDots = ({ complexity }: { complexity: number }) => {
    const maxDots = 5
    const filledDots = Math.min(Math.ceil(complexity / 2), maxDots)

    return (
      <div className="flex gap-0.5">
        {Array.from({ length: maxDots }).map((_, i) => (
          <span
            key={i}
            className={`
              w-2 h-2 rounded-full border border-[var(--color-neo-border)]
              ${i < filledDots ? 'bg-[var(--color-neo-accent)]' : 'bg-transparent'}
            `}
          />
        ))}
      </div>
    )
  }

  // Type badge color
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'implementation':
        return 'var(--color-neo-progress)'
      case 'testing':
        return 'var(--color-neo-pending)'
      case 'documentation':
        return 'var(--color-neo-success)'
      default:
        return 'var(--color-neo-muted)'
    }
  }

  return (
    <div
      className={`
        border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]
        transition-all duration-150
        ${selected ? 'shadow-neo-sm' : 'shadow-neo-xs'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-neo-sm'}
        ${selected ? 'border-[var(--color-neo-accent)]' : ''}
        ${task.isExtension ? 'border-dashed' : ''}
      `}
    >
      {/* Header */}
      <div className="p-3 flex items-start gap-3" onClick={() => !disabled && onToggle()}>
        {/* Checkbox */}
        <div
          className={`
            w-6 h-6 flex-shrink-0 border-3 border-[var(--color-neo-border)]
            flex items-center justify-center
            ${selected ? 'bg-[var(--color-neo-accent)]' : 'bg-white'}
          `}
        >
          {selected && <Check size={14} className="text-white" strokeWidth={3} />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-display font-bold text-sm">
              {task.title}
            </span>
            {task.isExtension && (
              <span className="px-2 py-0.5 text-xs font-bold uppercase bg-[var(--color-neo-pending)]/20 border border-[var(--color-neo-pending)]">
                Extension
              </span>
            )}
          </div>

          {/* Meta row */}
          <div className="mt-2 flex items-center gap-3 flex-wrap">
            {/* Type */}
            <span
              className="px-2 py-0.5 text-xs font-bold uppercase border-2 border-[var(--color-neo-border)]"
              style={{ backgroundColor: `${getTypeColor(task.type)}20` }}
            >
              {task.type}
            </span>

            {/* Complexity */}
            <div className="flex items-center gap-1">
              <span className="text-xs text-[var(--color-neo-muted)]">Complexity:</span>
              <ComplexityDots complexity={task.estimatedComplexity} />
            </div>

            {/* Dependencies */}
            {task.dependencies.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-[var(--color-neo-muted)]">
                <Link size={12} />
                <span>Deps: {task.dependencies.join(', ')}</span>
              </div>
            )}
          </div>

          {/* Assigned Skills */}
          {task.assignedSkills.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {task.assignedSkills.map((skill, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 text-xs bg-[var(--color-neo-accent)]/10 border border-[var(--color-neo-accent)]"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onEdit()
            }}
            className="p-1.5 hover:bg-[var(--color-neo-bg-alt)] border-2 border-transparent hover:border-[var(--color-neo-border)]"
            title="Edit task"
          >
            <Edit2 size={14} />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onRemove()
            }}
            className="p-1.5 hover:bg-[var(--color-neo-danger)]/10 border-2 border-transparent hover:border-[var(--color-neo-danger)]"
            title="Remove task"
          >
            <Trash2 size={14} />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              setExpanded(!expanded)
            }}
            className="p-1.5 hover:bg-[var(--color-neo-bg-alt)] border-2 border-transparent hover:border-[var(--color-neo-border)]"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded Content - Steps */}
      {expanded && (
        <div className="px-3 pb-3 pt-0 border-t-2 border-[var(--color-neo-border)]">
          {/* Description */}
          <p className="text-xs text-[var(--color-neo-muted)] mt-2">
            {task.description}
          </p>

          {/* Steps */}
          {task.steps.length > 0 && (
            <div className="mt-3">
              <span className="text-xs font-bold uppercase">Implementation Steps:</span>
              <ol className="mt-1 space-y-1">
                {task.steps.map((step, i) => (
                  <li key={i} className="text-xs text-[var(--color-neo-muted)] flex items-start gap-2">
                    <span className="font-bold text-[var(--color-neo-accent)] w-4 flex-shrink-0">
                      {i + 1}.
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
