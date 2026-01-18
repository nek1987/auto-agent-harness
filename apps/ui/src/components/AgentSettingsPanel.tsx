import { useEffect, useState } from 'react'
import { SlidersHorizontal, RotateCcw } from 'lucide-react'
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
  },
  {
    key: 'spec_analysis',
    label: 'Spec Analysis',
    description: 'Analyze / refine / enhance specs',
  },
  {
    key: 'coding',
    label: 'Coding & Initializer',
    description: 'Initializer, coding, and regression runs',
  },
  {
    key: 'redesign',
    label: 'Redesign Planner',
    description: 'Token extraction and redesign planning',
  },
]

export function AgentSettingsPanel({ projectName }: AgentSettingsPanelProps) {
  const [models, setModels] = useState<Record<string, string>>({})

  useEffect(() => {
    const next: Record<string, string> = {}
    MODEL_STAGES.forEach(stage => {
      next[stage.key] = getAgentModel(projectName, stage.key)
    })
    setModels(next)
  }, [projectName])

  const handleChange = (key: string, value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    setModels(prev => ({ ...prev, [key]: trimmed }))
    setAgentModel(projectName, trimmed, key)
  }

  const handleReset = () => {
    const next: Record<string, string> = {}
    MODEL_STAGES.forEach(stage => {
      next[stage.key] = DEFAULT_AGENT_MODEL
      setAgentModel(projectName, DEFAULT_AGENT_MODEL, stage.key)
    })
    setModels(next)
  }

  return (
    <div className="neo-card p-4 sm:p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-bold uppercase">
            Agent Settings
          </h3>
          <p className="text-xs text-[var(--color-neo-text-secondary)]">
            Choose models per workflow stage (stored locally per project)
          </p>
        </div>
        <button
          onClick={handleReset}
          className="neo-btn neo-btn-ghost text-xs"
        >
          <RotateCcw size={14} />
          Reset
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {MODEL_STAGES.map(stage => (
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
            <input
              className="neo-input w-full text-xs"
              list={`agent-settings-${projectName}-${stage.key}`}
              value={models[stage.key] || DEFAULT_AGENT_MODEL}
              onChange={(event) => handleChange(stage.key, event.target.value)}
              placeholder={DEFAULT_AGENT_MODEL}
            />
            <datalist id={`agent-settings-${projectName}-${stage.key}`}>
              {AGENT_MODEL_OPTIONS.map(option => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </div>
        ))}
      </div>
    </div>
  )
}
