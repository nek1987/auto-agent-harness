import { useState, useCallback, useRef } from 'react'
import {
  Upload,
  Link,
  Image,
  X,
  Loader2,
  Plus,
  ExternalLink,
} from 'lucide-react'
import type { RedesignReference } from '../../lib/types'

interface ReferenceUploaderProps {
  projectName: string
  references: RedesignReference[]
  onReferenceAdded: () => void
}

export function ReferenceUploader({
  projectName,
  references,
  onReferenceAdded,
}: ReferenceUploaderProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return

    setIsUploading(true)
    setError(null)

    for (const file of Array.from(files)) {
      // Validate file type
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
        setError(`Invalid file type: ${file.name}. Allowed: PNG, JPG, WebP`)
        continue
      }

      // Validate file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        setError(`File too large: ${file.name}. Max size: 10MB`)
        continue
      }

      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(
          `/api/projects/${projectName}/redesign/upload-reference`,
          {
            method: 'POST',
            body: formData,
          }
        )

        if (!response.ok) {
          const err = await response.json()
          setError(err.detail || 'Upload failed')
        } else {
          onReferenceAdded()
        }
      } catch (err) {
        setError('Failed to upload file')
      }
    }

    setIsUploading(false)
  }, [projectName, onReferenceAdded])

  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) return

    setIsUploading(true)
    setError(null)

    try {
      const response = await fetch(
        `/api/projects/${projectName}/redesign/add-url-reference`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ref_type: 'url',
            data: urlInput.trim(),
          }),
        }
      )

      if (response.ok) {
        setUrlInput('')
        setShowUrlInput(false)
        onReferenceAdded()
      } else {
        const err = await response.json()
        setError(err.detail || 'Failed to capture URL')
      }
    } catch (err) {
      setError('Failed to add URL reference')
    } finally {
      setIsUploading(false)
    }
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFileUpload(e.dataTransfer.files)
  }, [handleFileUpload])

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div
        className={`
          border-3 border-dashed p-8 text-center transition-colors
          ${isDragging
            ? 'border-[var(--color-neo-accent)] bg-[var(--color-neo-accent)]/10'
            : 'border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)]'
          }
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Upload className="mx-auto mb-4 text-[var(--color-neo-muted)]" size={48} />
        <h3 className="font-display font-bold mb-2">
          Drop reference images here
        </h3>
        <p className="text-sm text-[var(--color-neo-muted)] mb-4">
          or click to browse (PNG, JPG, WebP up to 10MB)
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="neo-btn neo-btn-primary"
          >
            <Image size={18} />
            Upload Images
          </button>
          <button
            onClick={() => setShowUrlInput(true)}
            disabled={isUploading}
            className="neo-btn neo-btn-ghost"
          >
            <Link size={18} />
            Add URL
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          className="hidden"
          onChange={e => handleFileUpload(e.target.files)}
        />
      </div>

      {/* URL Input */}
      {showUrlInput && (
        <div className="flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={e => setUrlInput(e.target.value)}
            placeholder="https://example.com/design-reference"
            className="neo-input flex-1"
            onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
          />
          <button
            onClick={handleUrlSubmit}
            disabled={isUploading || !urlInput.trim()}
            className="neo-btn neo-btn-primary"
          >
            {isUploading ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <Plus size={18} />
            )}
            Add
          </button>
          <button
            onClick={() => {
              setShowUrlInput(false)
              setUrlInput('')
            }}
            className="neo-btn neo-btn-ghost"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
          <span className="text-sm">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Reference List */}
      {references.length > 0 && (
        <div>
          <h4 className="font-display font-bold mb-3 uppercase text-sm">
            Uploaded References ({references.length})
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {references.map((ref, idx) => (
              <div
                key={idx}
                className="border-3 border-[var(--color-neo-border)] bg-white overflow-hidden"
              >
                {/* Thumbnail */}
                <div className="aspect-video bg-[var(--color-neo-bg-alt)] flex items-center justify-center">
                  {ref.type === 'image' || ref.type === 'url' ? (
                    <img
                      src={`data:image/png;base64,${ref.data}`}
                      alt={ref.metadata?.filename || `Reference ${idx + 1}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Image className="text-[var(--color-neo-muted)]" size={32} />
                  )}
                </div>
                {/* Info */}
                <div className="p-2 border-t-3 border-[var(--color-neo-border)]">
                  <p className="text-xs font-medium truncate">
                    {ref.type === 'url' && ref.metadata?.original_url ? (
                      <span className="flex items-center gap-1">
                        <ExternalLink size={12} />
                        {new URL(ref.metadata.original_url).hostname}
                      </span>
                    ) : (
                      ref.metadata?.filename || `Reference ${idx + 1}`
                    )}
                  </p>
                  <p className="text-xs text-[var(--color-neo-muted)] uppercase">
                    {ref.type}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {references.length === 0 && (
        <div className="text-center py-4 text-[var(--color-neo-muted)]">
          <p className="text-sm">
            No references added yet. Upload images or add URLs to extract design tokens.
          </p>
        </div>
      )}
    </div>
  )
}
