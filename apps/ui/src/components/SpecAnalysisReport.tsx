/**
 * Spec Analysis Report Component
 *
 * Displays the results of spec validation and Claude analysis.
 * Shows:
 * - Quality score badge
 * - Validation checklist
 * - Strengths (green)
 * - Improvements (with accept/reject buttons)
 * - Critical issues (red)
 * - Custom feedback field
 * - Action buttons
 */

import { useState } from 'react'
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Info,
  Sparkles,
  Target,
  Check,
  X,
  MessageSquare,
} from 'lucide-react'
import type { SpecValidationResponse, SpecAnalysisResponse } from '../lib/api'

export interface SuggestionDecisions {
  accepted: number[]
  rejected: number[]
  customFeedback: string
}

interface SpecAnalysisReportProps {
  validation: SpecValidationResponse
  analysis?: SpecAnalysisResponse | null
  onApprove?: () => void
  onRefine?: (decisions: SuggestionDecisions) => void
  onCancel?: () => void
  showActions?: boolean
  isLoading?: boolean
  interactive?: boolean
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'bg-[var(--color-neo-done)]'
  if (score >= 60) return 'bg-[var(--color-neo-progress)]'
  if (score >= 40) return 'bg-[var(--color-neo-pending)]'
  return 'bg-[var(--color-neo-danger)]'
}

function getScoreLabel(score: number): string {
  if (score >= 80) return 'Excellent'
  if (score >= 60) return 'Good'
  if (score >= 40) return 'Fair'
  return 'Needs Work'
}

export function SpecAnalysisReport({
  validation,
  analysis,
  onApprove,
  onRefine,
  onCancel,
  showActions = true,
  isLoading = false,
  interactive = false,
}: SpecAnalysisReportProps) {
  // Track which suggestions are accepted/rejected in interactive mode
  const [acceptedSuggestions, setAcceptedSuggestions] = useState<Set<number>>(new Set())
  const [rejectedSuggestions, setRejectedSuggestions] = useState<Set<number>>(new Set())
  const [customFeedback, setCustomFeedback] = useState('')

  const handleAcceptSuggestion = (index: number) => {
    setAcceptedSuggestions(prev => {
      const next = new Set(prev)
      next.add(index)
      return next
    })
    setRejectedSuggestions(prev => {
      const next = new Set(prev)
      next.delete(index)
      return next
    })
  }

  const handleRejectSuggestion = (index: number) => {
    setRejectedSuggestions(prev => {
      const next = new Set(prev)
      next.add(index)
      return next
    })
    setAcceptedSuggestions(prev => {
      const next = new Set(prev)
      next.delete(index)
      return next
    })
  }

  const handleRefineClick = () => {
    if (onRefine) {
      onRefine({
        accepted: Array.from(acceptedSuggestions),
        rejected: Array.from(rejectedSuggestions),
        customFeedback,
      })
    }
  }

  const hasDecisions = acceptedSuggestions.size > 0 || rejectedSuggestions.size > 0 || customFeedback.trim().length > 0

  const sections = [
    { name: 'Project Name', present: validation.has_project_name },
    { name: 'Overview', present: validation.has_overview },
    { name: 'Tech Stack', present: validation.has_tech_stack },
    { name: 'Feature Count', present: validation.has_feature_count },
    { name: 'Core Features', present: validation.has_core_features },
  ]

  const optionalSections = [
    { name: 'Database Schema', present: validation.has_database_schema },
    { name: 'API Endpoints', present: validation.has_api_endpoints },
    { name: 'Implementation Steps', present: validation.has_implementation_steps },
    { name: 'Success Criteria', present: validation.has_success_criteria },
  ]

  return (
    <div className="space-y-6">
      {/* Score Badge */}
      <div className="flex items-center gap-4">
        <div
          className={`
            w-20 h-20 flex flex-col items-center justify-center
            ${getScoreColor(validation.score)}
            border-3 border-[var(--color-neo-border)]
            shadow-[4px_4px_0px_rgba(0,0,0,1)]
          `}
        >
          <span className="text-2xl font-display font-bold">{validation.score}</span>
          <span className="text-xs font-bold">/100</span>
        </div>
        <div>
          <h3 className="font-display font-bold text-xl">
            {getScoreLabel(validation.score)}
          </h3>
          <p className="text-[var(--color-neo-text-secondary)] text-sm">
            {validation.is_valid ? 'Valid spec structure' : 'Invalid spec - fix errors below'}
          </p>
          {validation.project_name && (
            <p className="text-sm mt-1">
              <span className="text-[var(--color-neo-text-secondary)]">Project:</span>{' '}
              <span className="font-mono font-bold">{validation.project_name}</span>
            </p>
          )}
          {validation.feature_count && (
            <p className="text-sm">
              <span className="text-[var(--color-neo-text-secondary)]">Features:</span>{' '}
              <span className="font-bold">{validation.feature_count}</span>
            </p>
          )}
        </div>
      </div>

      {/* Required Sections */}
      <div>
        <h4 className="font-bold text-sm text-[var(--color-neo-text-secondary)] mb-2 flex items-center gap-2">
          <Target size={14} />
          Required Sections
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {sections.map((section) => (
            <div
              key={section.name}
              className="flex items-center gap-2 text-sm"
            >
              {section.present ? (
                <CheckCircle2 size={16} className="text-[var(--color-neo-done)]" />
              ) : (
                <AlertCircle size={16} className="text-[var(--color-neo-danger)]" />
              )}
              <span className={section.present ? '' : 'text-[var(--color-neo-danger)]'}>
                {section.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Optional Sections */}
      <div>
        <h4 className="font-bold text-sm text-[var(--color-neo-text-secondary)] mb-2 flex items-center gap-2">
          <Info size={14} />
          Optional Sections
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {optionalSections.map((section) => (
            <div
              key={section.name}
              className="flex items-center gap-2 text-sm"
            >
              {section.present ? (
                <CheckCircle2 size={16} className="text-[var(--color-neo-done)]" />
              ) : (
                <div className="w-4 h-4 border-2 border-[var(--color-neo-text-secondary)] rounded-sm" />
              )}
              <span className={section.present ? '' : 'text-[var(--color-neo-text-secondary)]'}>
                {section.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Errors */}
      {validation.errors.length > 0 && (
        <div className="p-4 bg-red-50 border-3 border-[var(--color-neo-danger)]">
          <h4 className="font-bold text-[var(--color-neo-danger)] flex items-center gap-2 mb-2">
            <AlertCircle size={16} />
            Errors
          </h4>
          <ul className="space-y-1">
            {validation.errors.map((error, i) => (
              <li key={i} className="text-sm text-[var(--color-neo-danger)]">
                {error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {validation.warnings.length > 0 && (
        <div className="p-4 bg-yellow-50 border-3 border-[var(--color-neo-pending)]">
          <h4 className="font-bold text-[#8B6914] flex items-center gap-2 mb-2">
            <AlertTriangle size={16} />
            Warnings
          </h4>
          <ul className="space-y-1">
            {validation.warnings.map((warning, i) => (
              <li key={i} className="text-sm text-[#8B6914]">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Claude Analysis */}
      {analysis && (
        <>
          {/* Strengths */}
          {analysis.strengths.length > 0 && (
            <div className="p-4 bg-green-50 border-3 border-[var(--color-neo-done)]">
              <h4 className="font-bold text-green-700 flex items-center gap-2 mb-2">
                <Sparkles size={16} />
                Strengths
              </h4>
              <ul className="space-y-1">
                {analysis.strengths.map((strength, i) => (
                  <li key={i} className="text-sm text-green-700 flex items-start gap-2">
                    <CheckCircle2 size={14} className="mt-0.5 flex-shrink-0" />
                    {strength}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Improvements */}
          {analysis.improvements.length > 0 && (
            <div className="p-4 bg-blue-50 border-3 border-[var(--color-neo-progress)]">
              <h4 className="font-bold text-blue-700 flex items-center gap-2 mb-2">
                <Info size={16} />
                Suggested Improvements
              </h4>
              <ul className="space-y-2">
                {analysis.improvements.map((improvement, i) => {
                  const isAccepted = acceptedSuggestions.has(i)
                  const isRejected = rejectedSuggestions.has(i)

                  return (
                    <li
                      key={i}
                      className={`text-sm flex items-start gap-2 p-2 -mx-2 rounded transition-colors ${
                        isAccepted ? 'bg-green-100 text-green-700' :
                        isRejected ? 'bg-red-100 text-red-400 line-through' :
                        'text-blue-700'
                      }`}
                    >
                      <span className="font-bold flex-shrink-0">{i + 1}.</span>
                      <span className="flex-1">{improvement}</span>
                      {interactive && (
                        <div className="flex gap-1 flex-shrink-0 ml-2">
                          <button
                            type="button"
                            onClick={() => handleAcceptSuggestion(i)}
                            className={`p-1 rounded border-2 transition-colors ${
                              isAccepted
                                ? 'bg-green-500 text-white border-green-600'
                                : 'bg-white text-green-600 border-green-300 hover:bg-green-50'
                            }`}
                            title="Accept this suggestion"
                          >
                            <Check size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRejectSuggestion(i)}
                            className={`p-1 rounded border-2 transition-colors ${
                              isRejected
                                ? 'bg-red-500 text-white border-red-600'
                                : 'bg-white text-red-600 border-red-300 hover:bg-red-50'
                            }`}
                            title="Reject this suggestion"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {/* Custom Feedback */}
          {interactive && (
            <div className="p-4 bg-purple-50 border-3 border-purple-300">
              <h4 className="font-bold text-purple-700 flex items-center gap-2 mb-2">
                <MessageSquare size={16} />
                Your Suggestions
              </h4>
              <textarea
                value={customFeedback}
                onChange={(e) => setCustomFeedback(e.target.value)}
                placeholder="Add your own suggestions or modifications here..."
                className="w-full p-3 border-2 border-purple-200 rounded resize-none h-24 text-sm focus:border-purple-400 focus:outline-none"
              />
            </div>
          )}

          {/* Critical Issues */}
          {analysis.critical_issues.length > 0 && (
            <div className="p-4 bg-red-50 border-3 border-[var(--color-neo-danger)]">
              <h4 className="font-bold text-[var(--color-neo-danger)] flex items-center gap-2 mb-2">
                <AlertCircle size={16} />
                Critical Issues (Must Fix)
              </h4>
              <ul className="space-y-1">
                {analysis.critical_issues.map((issue, i) => (
                  <li key={i} className="text-sm text-[var(--color-neo-danger)] flex items-start gap-2">
                    <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Analysis metadata */}
          <p className="text-xs text-[var(--color-neo-text-secondary)] text-right">
            Analyzed with {analysis.analysis_model}
          </p>
        </>
      )}

      {/* Action Buttons */}
      {showActions && (
        <div className="flex gap-3 pt-4 border-t-3 border-[var(--color-neo-border)]">
          {onCancel && (
            <button
              onClick={onCancel}
              className="neo-btn neo-btn-ghost"
              disabled={isLoading}
            >
              Cancel
            </button>
          )}
          <div className="flex-1" />
          {onRefine && interactive && hasDecisions && (
            <button
              onClick={handleRefineClick}
              className="neo-btn neo-btn-secondary"
              disabled={isLoading || !validation.is_valid}
            >
              Apply Changes & Refine
            </button>
          )}
          {onRefine && !interactive && (
            <button
              onClick={() => onRefine({ accepted: [], rejected: [], customFeedback: '' })}
              className="neo-btn neo-btn-secondary"
              disabled={isLoading || !validation.is_valid}
            >
              Refine Spec
            </button>
          )}
          {onApprove && (
            <button
              onClick={onApprove}
              className="neo-btn neo-btn-primary"
              disabled={isLoading || !validation.is_valid}
            >
              {isLoading ? 'Importing...' : 'Import Spec'}
            </button>
          )}
        </div>
      )}

      {/* Interactive mode refine button (shown even when showActions is false) */}
      {!showActions && interactive && hasDecisions && onRefine && (
        <div className="flex justify-end pt-4 border-t-3 border-[var(--color-neo-border)]">
          <button
            onClick={handleRefineClick}
            className="neo-btn neo-btn-secondary"
            disabled={isLoading || !validation.is_valid}
          >
            Apply Changes & Refine
          </button>
        </div>
      )}
    </div>
  )
}
