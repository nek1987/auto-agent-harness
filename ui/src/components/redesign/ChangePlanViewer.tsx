import { useState } from 'react'
import {
  FileCode,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  File,
  Loader2,
} from 'lucide-react'
import type { ChangePlan, PlanPhase, RedesignPlan, RedesignPagePlan } from '../../lib/types'

interface ChangePlanViewerProps {
  plan: RedesignPlan | null
  framework: string | null
  onApprovePhase?: (phase: string) => Promise<void>
}

export function ChangePlanViewer({
  plan,
  framework,
  onApprovePhase,
}: ChangePlanViewerProps) {
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set())
  const [approvingPhase, setApprovingPhase] = useState<string | null>(null)

  if (!plan) {
    return (
      <div className="text-center py-12">
        <FileCode className="mx-auto mb-4 text-[var(--color-neo-muted)]" size={48} />
        <h3 className="font-display font-bold mb-2">
          No Plan Generated Yet
        </h3>
        <p className="text-[var(--color-neo-muted)] text-sm">
          Run the redesign planner to generate the page plan
        </p>
      </div>
    )
  }

  const isPagePlan = (candidate: RedesignPlan): candidate is RedesignPagePlan =>
    Array.isArray((candidate as RedesignPagePlan).pages)

  const togglePhase = (phaseName: string) => {
    setExpandedPhases(prev => {
      const next = new Set(prev)
      if (next.has(phaseName)) {
        next.delete(phaseName)
      } else {
        next.add(phaseName)
      }
      return next
    })
  }

  const handleApprove = async (phaseName: string) => {
    if (!onApprovePhase) return
    setApprovingPhase(phaseName)
    try {
      await onApprovePhase(phaseName)
    } finally {
      setApprovingPhase(null)
    }
  }

  if (isPagePlan(plan)) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4 p-4 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
          <div>
            <span className="text-xs uppercase text-[var(--color-neo-muted)]">
              Design System
            </span>
            <p className="font-display font-bold">{plan.design_system_file}</p>
          </div>
          <div className="ml-auto">
            <span className="text-xs uppercase text-[var(--color-neo-muted)]">
              Pages
            </span>
            <p className="font-display font-bold">{plan.pages.length}</p>
          </div>
        </div>

        <div>
          <h4 className="font-display font-bold uppercase text-sm mb-3">
            Page Redesign Plan
          </h4>
          <div className="space-y-3">
            {plan.pages.map((page, idx) => (
              <div key={`${page.route}-${idx}`} className="border-3 border-[var(--color-neo-border)] bg-white p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="flex items-center justify-center w-8 h-8 bg-[var(--color-neo-accent)] text-white font-display font-bold">
                    {page.priority}
                  </span>
                  <div className="flex-1">
                    <h5 className="font-display font-bold">{page.route}</h5>
                    {page.reference && (
                      <p className="text-xs text-[var(--color-neo-muted)]">
                        Reference: {page.reference}
                      </p>
                    )}
                  </div>
                </div>
                {page.notes && (
                  <p className="text-sm text-[var(--color-neo-muted)]">
                    {page.notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const changePlan = plan as ChangePlan

  return (
    <div className="space-y-6">
      {/* Framework Info */}
      <div className="flex items-center gap-4 p-4 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
        <div>
          <span className="text-xs uppercase text-[var(--color-neo-muted)]">
            Detected Framework
          </span>
          <p className="font-display font-bold">{framework || 'Unknown'}</p>
        </div>
        <div className="ml-auto">
          <span className="text-xs uppercase text-[var(--color-neo-muted)]">
            Output Format
          </span>
          <p className="font-display font-bold">{changePlan.output_format}</p>
        </div>
      </div>

      {/* Phases */}
      <div>
        <h4 className="font-display font-bold uppercase text-sm mb-3">
          Implementation Phases ({changePlan.phases.length})
        </h4>

        <div className="space-y-3">
          {changePlan.phases.map((phase, idx) => (
            <PhaseCard
              key={phase.name}
              phase={phase}
              index={idx}
              isExpanded={expandedPhases.has(phase.name)}
              isApproving={approvingPhase === phase.name}
              onToggle={() => togglePhase(phase.name)}
              onApprove={() => handleApprove(phase.name)}
            />
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="p-4 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
        <h4 className="font-display font-bold uppercase text-sm mb-2">
          Summary
        </h4>
        <ul className="text-sm text-[var(--color-neo-muted)] space-y-1">
          <li>
            Total phases: <strong>{changePlan.phases.length}</strong>
          </li>
          <li>
            Total files to modify:{' '}
            <strong>
              {changePlan.phases.reduce((acc, p) => acc + p.files.length, 0)}
            </strong>
          </li>
          <li>
            Approve each phase to allow the agent to apply changes.
          </li>
        </ul>
      </div>
    </div>
  )
}

interface PhaseCardProps {
  phase: PlanPhase
  index: number
  isExpanded: boolean
  isApproving: boolean
  onToggle: () => void
  onApprove: () => void
}

function PhaseCard({
  phase,
  index,
  isExpanded,
  isApproving,
  onToggle,
  onApprove,
}: PhaseCardProps) {
  return (
    <div className="border-3 border-[var(--color-neo-border)] bg-white">
      {/* Header */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-[var(--color-neo-bg-alt)]"
        onClick={onToggle}
      >
        <span className="flex items-center justify-center w-8 h-8 bg-[var(--color-neo-accent)] text-white font-display font-bold">
          {index + 1}
        </span>

        <div className="flex-1">
          <h5 className="font-display font-bold capitalize">
            {phase.name}
          </h5>
          <p className="text-sm text-[var(--color-neo-muted)]">
            {phase.description}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--color-neo-muted)]">
            {phase.files.length} file(s)
          </span>
          {isExpanded ? (
            <ChevronDown size={18} />
          ) : (
            <ChevronRight size={18} />
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t-3 border-[var(--color-neo-border)]">
          {/* Files */}
          <div className="p-4 space-y-3">
            {phase.files.map((file, idx) => (
              <div
                key={idx}
                className="p-3 bg-[var(--color-neo-bg-alt)] border-2 border-[var(--color-neo-border)]"
              >
                <div className="flex items-center gap-2 mb-2">
                  <File size={14} className="text-[var(--color-neo-muted)]" />
                  <span className="font-mono text-sm">{file.path}</span>
                  <span className={`
                    ml-auto text-xs px-2 py-0.5 uppercase
                    ${file.action === 'create'
                      ? 'bg-green-100 text-green-700'
                      : file.action === 'modify'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-red-100 text-red-700'
                    }
                  `}>
                    {file.action}
                  </span>
                </div>

                {/* Changes Preview */}
                <div className="space-y-1">
                  {file.changes.slice(0, 3).map((change, cIdx) => (
                    <div
                      key={cIdx}
                      className="text-xs text-[var(--color-neo-muted)] font-mono"
                    >
                      <span className="text-[var(--color-neo-accent)]">
                        {change.type}
                      </span>
                      {change.name && (
                        <span>: {change.name}</span>
                      )}
                    </div>
                  ))}
                  {file.changes.length > 3 && (
                    <span className="text-xs text-[var(--color-neo-muted)]">
                      +{file.changes.length - 3} more changes
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Approve Button */}
          <div className="p-4 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)]">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onApprove()
              }}
              disabled={isApproving}
              className="neo-btn neo-btn-success w-full"
            >
              {isApproving ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <CheckCircle2 size={18} />
              )}
              Approve Phase
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
