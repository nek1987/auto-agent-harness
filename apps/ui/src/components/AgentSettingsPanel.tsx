import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Lock, RotateCcw, SlidersHorizontal, Unlock } from 'lucide-react'
import {
  AGENT_MODEL_OPTIONS,
  DEFAULT_AGENT_MODEL,
  getAgentModel,
  setAgentModel,
} from '../lib/agentSettings'

interface AgentSettingsPanelProps {
  projectName: string
}

const MODEL_STAGES = [
  {
    key: 'spec_creation',
    label: 'Spec Creation',
    description: 'Interactive spec chat sessions',
    summaryLabel: 'Spec',
  },
  {
    key: 'spec_analysis',
    label: 'Spec Analysis',
    description: 'Analyze / refine / enhance specs',
    summaryLabel: 'Analysis',
  },
  {
    key: 'coding',
    label: 'Coding & Initializer',
    description: 'Initializer, coding, and regression runs',
    summaryLabel: 'Coding',
  },
  {
    key: 'redesign',
    label: 'Redesign Planner',
    description: 'Token extraction and redesign planning',
    summaryLabel: 'Redesign',
  },
]

export function AgentSettingsPanel({ projectName }: AgentSettingsPanelProps) {
  const [models, setModels] = useState<Record<string, string>>({})
  const [isExpanded, setIsExpanded] = useState(false)
  const [isLocked, setIsLocked] = useState(true)

  useEffect(() => {
    const next: Record<string, string> = {}
    MODEL_STAGES.forEach(stage => {
      next[stage.key] = getAgentModel(projectName, stage.key)
    })
    setModels(next)
  }, [projectName])

  const handleChange = (key: string, value: string) => {
    if (isLocked) return
    const trimmed = value.trim()
    if (!trimmed) return
    setModels(prev => ({ ...prev, [key]: trimmed }))
    setAgentModel(projectName, trimmed, key)
  }

  const handleReset = () => {
    if (isLocked) return
    const next: Record<string, string> = {}
    MODEL_STAGES.forEach(stage => {
      next[stage.key] = DEFAULT_AGENT_MODEL
      setAgentModel(projectName, DEFAULT_AGENT_MODEL, stage.key)
    })
    setModels(next)
  }

  const summaryText = useMemo(() => {
    return MODEL_STAGES.map(stage => {
      const value = models[stage.key] || DEFAULT_AGENT_MODEL
      return `${stage.summaryLabel}: ${value}`
    }).join(' • ')
  }, [models])

  return (
    <div className="neo-card p-4 sm:p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-bold uppercase">
            Agent Settings
          </h3>
          <p className="text-xs text-[var(--color-neo-text-secondary)]">
            {isExpanded
              ? 'Choose models per workflow stage (stored locally per project)'
              : summaryText || 'Choose models per workflow stage'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLocked(prev => !prev)}
            className={`neo-btn text-xs ${isLocked ? 'neo-btn-secondary' : 'neo-btn-warning'}`}
            title={isLocked ? 'Unlock to change models' : 'Lock settings'}
          >
            {isLocked ? <Unlock size={14} /> : <Lock size={14} />}
            {isLocked ? 'Unlock' : 'Lock'}
          </button>
          <button
            onClick={() => setIsExpanded(prev => !prev)}
            className="neo-btn neo-btn-ghost text-xs"
            title={isExpanded ? 'Hide settings' : 'Show settings'}
          >
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {isExpanded ? 'Hide' : 'Show'}
          </button>
          {isExpanded && (
            <button
              onClick={handleReset}
              className="neo-btn neo-btn-ghost text-xs"
              disabled={isLocked}
            >
              <RotateCcw size={14} />
              Reset
            </button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {MODEL_STAGES.map(stage => {
            const currentModel = models[stage.key] || DEFAULT_AGENT_MODEL
            const options = AGENT_MODEL_OPTIONS.includes(currentModel)
              ? AGENT_MODEL_OPTIONS
              : [currentModel, ...AGENT_MODEL_OPTIONS]

            return (
              <div
                key={stage.key}
                className="p-3 border-3 border-[var(--color-neo-border)] bg-white space-y-2"
              >
                <div className="flex items-center gap-2 text-sm font-bold uppercase">
                  <SlidersHorizontal size={16} />
                  {stage.label}
                </div>
                <p className="text-xs text-[var(--color-neo-text-secondary)]">
                  {stage.description}
                </p>
                <select
                  className="neo-input w-full text-xs"
                  value={currentModel}
                  onChange={(event) => handleChange(stage.key, event.target.value)}
                  disabled={isLocked}
                >
                  {options.map(option => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
