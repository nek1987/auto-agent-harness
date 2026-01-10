/**
 * Spec Analysis Report Component
 *
 * Displays the results of spec validation and Claude analysis.
 * Shows:
 * - Quality score badge
 * - Validation checklist
 * - Strengths (green)
 * - Improvements (yellow)
 * - Critical issues (red)
 * - Action buttons
 */

import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Info,
  Sparkles,
  Target,
} from 'lucide-react'
import type { SpecValidationResponse, SpecAnalysisResponse } from '../lib/api'

interface SpecAnalysisReportProps {
  validation: SpecValidationResponse
  analysis?: SpecAnalysisResponse | null
  onApprove?: () => void
  onRefine?: () => void
  onCancel?: () => void
  showActions?: boolean
  isLoading?: boolean
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
}: SpecAnalysisReportProps) {
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
              <ul className="space-y-1">
                {analysis.improvements.map((improvement, i) => (
                  <li key={i} className="text-sm text-blue-700 flex items-start gap-2">
                    <span className="font-bold">{i + 1}.</span>
                    {improvement}
                  </li>
                ))}
              </ul>
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
          {onRefine && (
            <button
              onClick={onRefine}
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
    </div>
  )
}
