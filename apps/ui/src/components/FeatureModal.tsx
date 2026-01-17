import { useState } from 'react'
import { X, CheckCircle2, Circle, SkipForward, Trash2, Loader2, AlertCircle } from 'lucide-react'
import { useSkipFeature, useDeleteFeature } from '../hooks/useProjects'
import type { Feature } from '../lib/types'

interface FeatureModalProps {
  feature: Feature
  projectName: string
  onClose: () => void
}

export function FeatureModal({ feature, projectName, onClose }: FeatureModalProps) {
  const [error, setError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const skipFeature = useSkipFeature(projectName)
  const deleteFeature = useDeleteFeature(projectName)

  const handleSkip = async () => {
    setError(null)
    try {
      await skipFeature.mutateAsync(feature.id)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to skip feature')
    }
  }

  const handleDelete = async () => {
    setError(null)
    try {
      await deleteFeature.mutateAsync(feature.id)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete feature')
    }
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-2xl p-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 sm:p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex-1 min-w-0 pr-2">
            <span className="neo-badge bg-[var(--color-neo-accent)] text-white mb-2 text-xs">
              {feature.category}
            </span>
            <h2 className="font-display text-xl sm:text-2xl font-bold truncate">
              {feature.name}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2 min-h-[44px] min-w-[44px] flex-shrink-0"
          >
            <X size={20} className="sm:w-6 sm:h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span className="text-sm sm:text-base">{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-auto min-w-[32px] min-h-[32px] flex items-center justify-center"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Status */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]">
            {feature.passes ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 size={20} className="sm:w-6 sm:h-6 text-[var(--color-neo-done)]" />
                <span className="font-display font-bold text-[var(--color-neo-done)]">
                  COMPLETE
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Circle size={20} className="sm:w-6 sm:h-6 text-[var(--color-neo-text-secondary)]" />
                <span className="font-display font-bold text-[var(--color-neo-text-secondary)]">
                  PENDING
                </span>
              </div>
            )}
            <span className="sm:ml-auto font-mono text-sm">
              Priority: #{feature.priority}
            </span>
          </div>

          {/* Description */}
          <div>
            <h3 className="font-display font-bold mb-2 uppercase text-xs sm:text-sm">
              Description
            </h3>
            <p className="text-sm sm:text-base text-[var(--color-neo-text-secondary)]">
              {feature.description}
            </p>
          </div>

          {/* Steps */}
          {feature.steps.length > 0 && (
            <div>
              <h3 className="font-display font-bold mb-2 uppercase text-xs sm:text-sm">
                Test Steps
              </h3>
              <ol className="list-decimal list-inside space-y-2">
                {feature.steps.map((step, index) => (
                  <li
                    key={index}
                    className="p-2 sm:p-3 text-sm sm:text-base bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]"
                  >
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Actions */}
        {!feature.passes && (
          <div className="p-4 sm:p-6 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
            {showDeleteConfirm ? (
              <div className="space-y-4">
                <p className="font-bold text-center text-sm sm:text-base">
                  Are you sure you want to delete this feature?
                </p>
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                  <button
                    onClick={handleDelete}
                    disabled={deleteFeature.isPending}
                    className="neo-btn neo-btn-danger flex-1 min-h-[48px] justify-center"
                  >
                    {deleteFeature.isPending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      'Yes, Delete'
                    )}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleteFeature.isPending}
                    className="neo-btn neo-btn-ghost flex-1 min-h-[48px] justify-center"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                <button
                  onClick={handleSkip}
                  disabled={skipFeature.isPending}
                  className="neo-btn neo-btn-warning flex-1 min-h-[48px] justify-center"
                >
                  {skipFeature.isPending ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <>
                      <SkipForward size={18} />
                      <span className="hidden sm:inline">Skip (Move to End)</span>
                      <span className="sm:hidden">Skip</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  disabled={skipFeature.isPending}
                  className="neo-btn neo-btn-danger min-h-[48px] min-w-[48px] justify-center"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
