import { Check, ChevronDown, ChevronUp, Sparkles, Code, Wrench } from 'lucide-react'
import { useState } from 'react'

export interface SkillMatch {
  name: string
  displayName: string
  description: string
  relevanceScore: number
  matchReasons: string[]
  category: string
  tags: string[]
  capabilities: string[]
  hasScripts: boolean
  hasReferences: boolean
}

interface SkillCardProps {
  skill: SkillMatch
  selected: boolean
  disabled?: boolean
  onToggle: () => void
  compact?: boolean
}

export function SkillCard({
  skill,
  selected,
  disabled = false,
  onToggle,
  compact = false,
}: SkillCardProps) {
  const [expanded, setExpanded] = useState(false)

  // Relevance score color
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'var(--color-neo-success)'
    if (score >= 0.5) return 'var(--color-neo-progress)'
    return 'var(--color-neo-pending)'
  }

  // Category icon
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'frontend':
        return <Sparkles size={14} />
      case 'backend':
        return <Code size={14} />
      case 'testing':
        return <Wrench size={14} />
      default:
        return <Code size={14} />
    }
  }

  return (
    <div
      className={`
        border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]
        transition-all duration-150
        ${selected ? 'shadow-neo-sm translate-x-0 translate-y-0' : 'shadow-neo-xs translate-x-0 translate-y-0'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-neo-sm'}
        ${selected ? 'border-[var(--color-neo-accent)]' : ''}
      `}
      onClick={() => !disabled && onToggle()}
    >
      {/* Header */}
      <div className="p-3 flex items-start gap-3">
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
            <span className="font-display font-bold text-sm truncate">
              {skill.displayName}
            </span>
            <span
              className="px-2 py-0.5 text-xs font-bold uppercase border-2 border-[var(--color-neo-border)] flex items-center gap-1"
              style={{ backgroundColor: `${getScoreColor(skill.relevanceScore)}20` }}
            >
              {getCategoryIcon(skill.category)}
              {skill.category}
            </span>
          </div>

          {/* Relevance Score */}
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-2 bg-[var(--color-neo-bg-alt)] border-2 border-[var(--color-neo-border)]">
              <div
                className="h-full transition-all duration-300"
                style={{
                  width: `${skill.relevanceScore * 100}%`,
                  backgroundColor: getScoreColor(skill.relevanceScore),
                }}
              />
            </div>
            <span className="text-xs font-bold" style={{ color: getScoreColor(skill.relevanceScore) }}>
              {Math.round(skill.relevanceScore * 100)}%
            </span>
          </div>

          {/* Match Reasons */}
          {!compact && skill.matchReasons.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {skill.matchReasons.slice(0, 3).map((reason, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 text-xs bg-[var(--color-neo-bg-alt)] border border-[var(--color-neo-border)]"
                >
                  {reason}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Expand button */}
        {!compact && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              setExpanded(!expanded)
            }}
            className="p-1 hover:bg-[var(--color-neo-bg-alt)] border-2 border-transparent hover:border-[var(--color-neo-border)]"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>

      {/* Expanded Content */}
      {expanded && !compact && (
        <div className="px-3 pb-3 pt-0 border-t-2 border-[var(--color-neo-border)] mt-0">
          {/* Description */}
          <p className="text-xs text-[var(--color-neo-muted)] mt-2 line-clamp-3">
            {skill.description}
          </p>

          {/* Tags */}
          {skill.tags.length > 0 && (
            <div className="mt-2">
              <span className="text-xs font-bold uppercase">Tags: </span>
              <span className="text-xs text-[var(--color-neo-muted)]">
                {skill.tags.join(', ')}
              </span>
            </div>
          )}

          {/* Capabilities */}
          {skill.capabilities.length > 0 && (
            <div className="mt-2">
              <span className="text-xs font-bold uppercase">Capabilities:</span>
              <ul className="mt-1 space-y-0.5">
                {skill.capabilities.slice(0, 5).map((cap, i) => (
                  <li key={i} className="text-xs text-[var(--color-neo-muted)] flex items-start gap-1">
                    <span className="text-[var(--color-neo-accent)]">•</span>
                    {cap}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Features */}
          <div className="mt-2 flex gap-2">
            {skill.hasScripts && (
              <span className="px-2 py-0.5 text-xs bg-[var(--color-neo-progress)]/20 border border-[var(--color-neo-progress)]">
                Has Scripts
              </span>
            )}
            {skill.hasReferences && (
              <span className="px-2 py-0.5 text-xs bg-[var(--color-neo-success)]/20 border border-[var(--color-neo-success)]">
                Has Docs
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
