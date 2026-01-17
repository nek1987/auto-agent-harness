import { useState } from 'react'
import {
  X,
  Check,
  Edit2,
  Trash2,
  AlertCircle,
  Sparkles,
  Shield,
  Accessibility,
  Zap,
  FormInput,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react'

export interface Suggestion {
  id: string
  type: 'ui_extension' | 'validation' | 'accessibility' | 'performance' | 'security'
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
  skillSource: string
  implementationSteps: string[]
  selected: boolean
}

export interface ComplexityAssessment {
  score: number
  recommendation: 'simple' | 'split' | 'complex'
}

interface FeatureSuggestionsPanelProps {
  suggestions: Suggestion[]
  complexity: ComplexityAssessment | null
  isAnalyzing: boolean
  onToggleSuggestion: (id: string) => void
  onRemoveSuggestion: (id: string) => void
  onEditSuggestion: (id: string, updates: Partial<Suggestion>) => void
  onApply: (selectedSuggestions: Suggestion[]) => void
  onSkip: () => void
  onClose: () => void
}

const typeIcons = {
  ui_extension: Sparkles,
  validation: FormInput,
  accessibility: Accessibility,
  performance: Zap,
  security: Shield,
}

const typeLabels = {
  ui_extension: 'UI Extension',
  validation: 'Validation',
  accessibility: 'Accessibility',
  performance: 'Performance',
  security: 'Security',
}

const priorityColors = {
  high: 'bg-[var(--color-neo-danger)]',
  medium: 'bg-[var(--color-neo-warning)]',
  low: 'bg-[var(--color-neo-muted)]',
}

export function FeatureSuggestionsPanel({
  suggestions,
  complexity,
  isAnalyzing,
  onToggleSuggestion,
  onRemoveSuggestion,
  onEditSuggestion,
  onApply,
  onSkip,
  onClose,
}: FeatureSuggestionsPanelProps) {
  const [expandedSuggestions, setExpandedSuggestions] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const selectedSuggestions = suggestions.filter(s => s.selected)
  const hasSelections = selectedSuggestions.length > 0

  const toggleExpand = (id: string) => {
    const newExpanded = new Set(expandedSuggestions)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedSuggestions(newExpanded)
  }

  const startEdit = (suggestion: Suggestion) => {
    setEditingId(suggestion.id)
    setEditValue(suggestion.description)
  }

  const saveEdit = (id: string) => {
    onEditSuggestion(id, { description: editValue })
    setEditingId(null)
    setEditValue('')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditValue('')
  }

  return (
    <div className="mt-4 border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
      {/* Header */}
      <div className="flex items-center justify-between p-3 sm:p-4 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-accent)]/10">
        <div className="flex items-center gap-2">
          <Sparkles size={20} className="text-[var(--color-neo-accent)]" />
          <h3 className="font-display font-bold text-sm sm:text-base">
            AI Suggestions
          </h3>
          {isAnalyzing && (
            <Loader2 size={16} className="animate-spin text-[var(--color-neo-accent)]" />
          )}
        </div>
        <button
          onClick={onClose}
          className="neo-btn neo-btn-ghost p-1.5 min-h-[36px] min-w-[36px]"
        >
          <X size={16} />
        </button>
      </div>

      {/* Complexity Assessment */}
      {complexity && (
        <div className="p-3 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-muted)]/20">
          <div className="flex items-center justify-between text-xs sm:text-sm">
            <span className="font-bold">Complexity:</span>
            <div className="flex items-center gap-2">
              <div className="flex gap-0.5">
                {[...Array(10)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-2 h-4 border border-[var(--color-neo-border)] ${
                      i < complexity.score
                        ? complexity.score <= 3
                          ? 'bg-[var(--color-neo-success)]'
                          : complexity.score <= 6
                          ? 'bg-[var(--color-neo-warning)]'
                          : 'bg-[var(--color-neo-danger)]'
                        : 'bg-white'
                    }`}
                  />
                ))}
              </div>
              <span
                className={`px-2 py-0.5 font-bold uppercase text-xs border-2 border-[var(--color-neo-border)] ${
                  complexity.recommendation === 'simple'
                    ? 'bg-[var(--color-neo-success)] text-white'
                    : complexity.recommendation === 'split'
                    ? 'bg-[var(--color-neo-warning)]'
                    : 'bg-[var(--color-neo-danger)] text-white'
                }`}
              >
                {complexity.recommendation}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Suggestions List */}
      <div className="max-h-[300px] overflow-y-auto">
        {suggestions.length === 0 && isAnalyzing && (
          <div className="p-6 text-center text-[var(--color-neo-muted)]">
            <Loader2 size={24} className="animate-spin mx-auto mb-2" />
            <p className="text-sm">Analyzing feature...</p>
          </div>
        )}

        {suggestions.length === 0 && !isAnalyzing && (
          <div className="p-6 text-center text-[var(--color-neo-muted)]">
            <AlertCircle size={24} className="mx-auto mb-2" />
            <p className="text-sm">No suggestions available</p>
          </div>
        )}

        {suggestions.map((suggestion) => {
          const Icon = typeIcons[suggestion.type] || Sparkles
          const isExpanded = expandedSuggestions.has(suggestion.id)
          const isEditing = editingId === suggestion.id

          return (
            <div
              key={suggestion.id}
              className={`border-b-2 border-[var(--color-neo-border)] last:border-b-0 ${
                suggestion.selected ? 'bg-[var(--color-neo-accent)]/5' : ''
              }`}
            >
              {/* Suggestion Header */}
              <div className="flex items-start gap-2 p-3">
                {/* Checkbox */}
                <button
                  onClick={() => onToggleSuggestion(suggestion.id)}
                  className={`flex-shrink-0 w-6 h-6 border-2 border-[var(--color-neo-border)] flex items-center justify-center ${
                    suggestion.selected
                      ? 'bg-[var(--color-neo-accent)] text-white'
                      : 'bg-white'
                  }`}
                >
                  {suggestion.selected && <Check size={14} />}
                </button>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Icon size={14} className="text-[var(--color-neo-accent)] flex-shrink-0" />
                    <span className="font-bold text-sm truncate">{suggestion.title}</span>
                    <span
                      className={`px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                        priorityColors[suggestion.priority]
                      } ${suggestion.priority === 'high' ? 'text-white' : ''}`}
                    >
                      {suggestion.priority}
                    </span>
                  </div>

                  {/* Type Badge */}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] px-1.5 py-0.5 bg-[var(--color-neo-muted)]/30 border border-[var(--color-neo-border)]">
                      {typeLabels[suggestion.type]}
                    </span>
                    <span className="text-[10px] text-[var(--color-neo-muted)]">
                      via {suggestion.skillSource}
                    </span>
                  </div>

                  {/* Description */}
                  {isEditing ? (
                    <div className="mt-2">
                      <textarea
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="neo-input text-xs min-h-[60px] w-full resize-y"
                        autoFocus
                      />
                      <div className="flex gap-1 mt-1">
                        <button
                          onClick={() => saveEdit(suggestion.id)}
                          className="neo-btn neo-btn-success text-xs px-2 py-1 min-h-[28px]"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="neo-btn neo-btn-ghost text-xs px-2 py-1 min-h-[28px]"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--color-neo-muted)] mt-1 line-clamp-2">
                      {suggestion.description}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  {suggestion.implementationSteps.length > 0 && (
                    <button
                      onClick={() => toggleExpand(suggestion.id)}
                      className="neo-btn neo-btn-ghost p-1 min-h-[28px] min-w-[28px]"
                      title="Show steps"
                    >
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  )}
                  <button
                    onClick={() => startEdit(suggestion)}
                    className="neo-btn neo-btn-ghost p-1 min-h-[28px] min-w-[28px]"
                    title="Edit"
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => onRemoveSuggestion(suggestion.id)}
                    className="neo-btn neo-btn-ghost p-1 min-h-[28px] min-w-[28px] hover:text-[var(--color-neo-danger)]"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Expanded Steps */}
              {isExpanded && suggestion.implementationSteps.length > 0 && (
                <div className="px-3 pb-3 pl-11">
                  <div className="text-xs font-bold mb-1 text-[var(--color-neo-muted)]">
                    Implementation Steps:
                  </div>
                  <ol className="list-decimal list-inside text-xs space-y-0.5 text-[var(--color-neo-text)]">
                    {suggestion.implementationSteps.map((step, idx) => (
                      <li key={idx} className="pl-1">{step}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer Actions */}
      <div className="flex flex-col sm:flex-row gap-2 p-3 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
        <button
          onClick={() => onApply(selectedSuggestions)}
          disabled={!hasSelections || isAnalyzing}
          className="neo-btn neo-btn-success flex-1 min-h-[44px] justify-center text-sm"
        >
          <Check size={16} />
          Apply Selected ({selectedSuggestions.length})
        </button>
        <button
          onClick={onSkip}
          disabled={isAnalyzing}
          className="neo-btn neo-btn-ghost min-h-[44px] justify-center text-sm"
        >
          Skip Analysis
        </button>
      </div>
    </div>
  )
}
