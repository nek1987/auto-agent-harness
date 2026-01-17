/**
 * Delete Project Modal Component
 *
 * Confirmation dialog for deleting a project with option to delete files.
 */

import { useState } from 'react'
import { X, Trash2, AlertTriangle, Loader2 } from 'lucide-react'
import { deleteProject } from '../lib/api'

interface DeleteProjectModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onDeleted: () => void
}

export function DeleteProjectModal({
  isOpen,
  projectName,
  onClose,
  onDeleted,
}: DeleteProjectModalProps) {
  const [deleteFiles, setDeleteFiles] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleClose = () => {
    if (isDeleting) return
    setDeleteFiles(false)
    setError(null)
    onClose()
  }

  const handleDelete = async () => {
    setIsDeleting(true)
    setError(null)

    try {
      await deleteProject(projectName, deleteFiles)
      onDeleted()
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete project')
    } finally {
      setIsDeleting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="neo-modal-backdrop" onClick={handleClose}>
      <div
        className="neo-modal w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-2">
            <AlertTriangle size={20} className="text-[var(--color-neo-danger)]" />
            <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
              Delete Project
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="neo-btn neo-btn-ghost p-2"
            disabled={isDeleting}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-[var(--color-neo-text)] mb-4">
            Are you sure you want to delete project{' '}
            <span className="font-bold font-mono">{projectName}</span>?
          </p>
          <p className="text-sm text-[var(--color-neo-text-secondary)] mb-6">
            This action cannot be undone.
          </p>

          {/* Delete files checkbox */}
          <label className="flex items-start gap-3 p-4 bg-[var(--color-neo-bg-secondary)] border-2 border-[var(--color-neo-border)] cursor-pointer hover:bg-[var(--color-neo-pending)] transition-colors">
            <input
              type="checkbox"
              checked={deleteFiles}
              onChange={(e) => setDeleteFiles(e.target.checked)}
              className="mt-0.5 w-5 h-5 border-2 border-[var(--color-neo-border)] accent-[var(--color-neo-danger)]"
              disabled={isDeleting}
            />
            <div>
              <span className="font-bold text-[#1a1a1a]">
                Also delete files from disk
              </span>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                This will permanently remove the project folder and all its contents.
              </p>
            </div>
          </label>

          {error && (
            <div className="mt-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={handleClose}
              className="neo-btn neo-btn-ghost flex-1"
              disabled={isDeleting}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              className="neo-btn flex-1 bg-[var(--color-neo-danger)] text-white hover:bg-red-600"
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 size={16} />
                  Delete Project
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
