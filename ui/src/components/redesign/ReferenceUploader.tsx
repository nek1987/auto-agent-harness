import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Upload,
  Link,
  Image,
  X,
  Loader2,
  Plus,
  ExternalLink,
  FileArchive,
  FileCode,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  MapPin,
} from 'lucide-react'
import type { RedesignReference, DetectedPage, UploadedPageReference } from '../../lib/types'

interface UploadedComponent {
  filename: string
  framework: string
  file_type: string
  size: number
}

interface ReferenceUploaderProps {
  projectName: string
  references: RedesignReference[]
  onReferenceAdded: () => void
  onComponentsUploaded?: (count: number, sessionId: number) => void
  redesignSessionId?: number
}

export function ReferenceUploader({
  projectName,
  references,
  onReferenceAdded,
  onComponentsUploaded,
  redesignSessionId,
}: ReferenceUploaderProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [isDraggingZip, setIsDraggingZip] = useState(false)
  const [uploadedComponents, setUploadedComponents] = useState<UploadedComponent[]>([])
  const [isUploadingZip, setIsUploadingZip] = useState(false)
  const [zipUploadSuccess, setZipUploadSuccess] = useState(false)
  const [zipFilename, setZipFilename] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const zipInputRef = useRef<HTMLInputElement>(null)

  // Page selection state for ZIP uploads
  const [showPageSelector, setShowPageSelector] = useState(false)
  const [detectedPages, setDetectedPages] = useState<DetectedPage[]>([])
  const [isLoadingPages, setIsLoadingPages] = useState(false)
  const [selectedPage, setSelectedPage] = useState<string>('')
  const [customPageName, setCustomPageName] = useState('')
  const [uploadedPageRefs, setUploadedPageRefs] = useState<UploadedPageReference[]>([])

  // Fetch detected pages when page selector is shown
  useEffect(() => {
    if (showPageSelector && detectedPages.length === 0 && !isLoadingPages) {
      setIsLoadingPages(true)
      fetch(`/api/projects/${projectName}/component-reference/pages`)
        .then(res => res.ok ? res.json() : Promise.reject(new Error('Failed to scan pages')))
        .then(data => {
          setDetectedPages([...data.pages || [], ...data.layouts || []])
        })
        .catch(err => {
          console.error('Failed to scan project pages:', err)
        })
        .finally(() => {
          setIsLoadingPages(false)
        })
    }
  }, [showPageSelector, projectName, detectedPages.length, isLoadingPages])

  // Get the effective page identifier for upload
  const getPageIdentifier = useCallback((): string | null => {
    if (customPageName.trim()) {
      // Custom page name takes priority
      const name = customPageName.trim()
      return name.startsWith('/') ? name : `/${name}`
    }
    if (selectedPage) {
      return selectedPage
    }
    return null
  }, [selectedPage, customPageName])

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

  // ZIP file upload handlers
  const handleZipUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return

    const file = files[0]
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError(`Invalid file type: ${file.name}. Must be a ZIP archive.`)
      return
    }

    if (file.size > 50 * 1024 * 1024) {
      setError(`File too large: ${file.name}. Max size: 50MB`)
      return
    }

    setIsUploadingZip(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('source_type', 'custom')

      // Link to redesign session if provided
      if (redesignSessionId) {
        formData.append('redesign_session_id', redesignSessionId.toString())
      }

      // Add page identifier if specified
      const pageId = getPageIdentifier()
      if (pageId) {
        formData.append('page_identifier', pageId)
      }

      const response = await fetch(
        `/api/projects/${projectName}/component-reference/upload-zip`,
        {
          method: 'POST',
          body: formData,
        }
      )

      if (response.ok) {
        const data = await response.json()
        const components = data.components || []
        setUploadedComponents(components)
        setZipUploadSuccess(true)
        setZipFilename(file.name)
        onReferenceAdded()

        // Track uploaded page reference if one was created
        if (data.page_reference_id && pageId) {
          setUploadedPageRefs(prev => [...prev, {
            session_id: data.session_id,
            page_reference_id: data.page_reference_id,
            page_identifier: pageId,
            filename: file.name,
            components_count: components.length,
          }])
          // Reset page selection after successful upload
          setSelectedPage('')
          setCustomPageName('')
        }

        if (onComponentsUploaded && data.session_id) {
          onComponentsUploaded(components.length, data.session_id)
        }
      } else {
        const err = await response.json()
        setError(err.detail || 'ZIP upload failed')
      }
    } catch (err) {
      setError('Failed to upload ZIP file')
    } finally {
      setIsUploadingZip(false)
    }
  }, [projectName, onReferenceAdded, onComponentsUploaded, redesignSessionId, getPageIdentifier])

  const handleZipDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDraggingZip(true)
  }, [])

  const handleZipDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDraggingZip(false)
  }, [])

  const handleZipDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDraggingZip(false)
    handleZipUpload(e.dataTransfer.files)
  }, [handleZipUpload])

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

      {/* ZIP Component Upload Area with Page Selector */}
      <div className="space-y-3">
        {/* Page Selector Toggle */}
        <button
          onClick={() => setShowPageSelector(!showPageSelector)}
          className="w-full flex items-center justify-between p-3 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)] hover:border-[var(--color-neo-accent)] transition-colors"
        >
          <div className="flex items-center gap-2">
            <MapPin size={18} className="text-[var(--color-neo-accent)]" />
            <span className="font-display font-bold text-sm">Target Page (Optional)</span>
            {getPageIdentifier() && (
              <span className="text-xs bg-[var(--color-neo-accent)] text-white px-2 py-0.5">
                {getPageIdentifier()}
              </span>
            )}
          </div>
          {showPageSelector ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {/* Page Selector Panel */}
        {showPageSelector && (
          <div className="p-4 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)] space-y-3">
            <p className="text-xs text-[var(--color-neo-muted)]">
              Specify which page these components are for (e.g., /login, /dashboard).
              This helps the agent match components to the right features.
            </p>

            {/* Detected Pages Dropdown */}
            <div className="space-y-1">
              <label className="text-xs font-bold uppercase">Detected Pages</label>
              {isLoadingPages ? (
                <div className="flex items-center gap-2 text-sm text-[var(--color-neo-muted)]">
                  <Loader2 size={14} className="animate-spin" />
                  Scanning project...
                </div>
              ) : (
                <select
                  value={selectedPage}
                  onChange={e => {
                    setSelectedPage(e.target.value)
                    if (e.target.value) setCustomPageName('')
                  }}
                  className="neo-input w-full text-sm"
                >
                  <option value="">-- Select a page --</option>
                  {detectedPages.map((page, idx) => (
                    <option key={idx} value={page.route || page.file_path}>
                      {page.element_name} ({page.route || page.file_path})
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Custom Page Name Input */}
            <div className="space-y-1">
              <label className="text-xs font-bold uppercase">Or Enter Custom</label>
              <input
                type="text"
                value={customPageName}
                onChange={e => {
                  setCustomPageName(e.target.value)
                  if (e.target.value) setSelectedPage('')
                }}
                placeholder="/login, /dashboard, /settings..."
                className="neo-input w-full text-sm"
              />
            </div>

            {/* Clear Button */}
            {(selectedPage || customPageName) && (
              <button
                onClick={() => {
                  setSelectedPage('')
                  setCustomPageName('')
                }}
                className="text-xs text-[var(--color-neo-danger)] hover:underline"
              >
                Clear selection
              </button>
            )}
          </div>
        )}

        {/* ZIP Upload Drop Zone */}
        <div
          className={`
            border-3 p-6 text-center transition-colors
            ${zipUploadSuccess
              ? 'border-[var(--color-neo-success)] bg-[var(--color-neo-success)]/10 border-solid'
              : isDraggingZip
                ? 'border-[var(--color-neo-success)] bg-[var(--color-neo-success)]/10 border-dashed'
                : 'border-[var(--color-neo-border)] bg-[var(--color-neo-bg-alt)] border-dashed'
            }
          `}
          onDragOver={handleZipDragOver}
          onDragLeave={handleZipDragLeave}
          onDrop={handleZipDrop}
        >
        {zipUploadSuccess ? (
          <>
            <CheckCircle2 className="mx-auto mb-3 text-[var(--color-neo-success)]" size={36} />
            <h3 className="font-display font-bold mb-1 text-sm text-[var(--color-neo-success)]">
              ZIP Uploaded Successfully!
            </h3>
            {zipFilename && (
              <p className="text-xs font-medium mb-1 truncate max-w-full px-2">
                {zipFilename}
              </p>
            )}
            <p className="text-xs text-[var(--color-neo-muted)] mb-3">
              {uploadedComponents.length} components extracted
            </p>
            <button
              onClick={() => {
                setZipUploadSuccess(false)
                setUploadedComponents([])
                setZipFilename(null)
              }}
              className="neo-btn neo-btn-ghost text-sm"
            >
              <FileArchive size={16} />
              Upload Another
            </button>
          </>
        ) : (
          <>
            {isUploadingZip ? (
              <>
                <Loader2 className="mx-auto mb-3 text-[var(--color-neo-accent)] animate-spin" size={36} />
                <h3 className="font-display font-bold mb-1 text-sm">
                  Uploading & Extracting...
                </h3>
                <p className="text-xs text-[var(--color-neo-muted)]">
                  Processing ZIP file, please wait
                </p>
              </>
            ) : (
              <>
                <FileArchive className="mx-auto mb-3 text-[var(--color-neo-muted)]" size={36} />
                <h3 className="font-display font-bold mb-1 text-sm">
                  Component Reference (ZIP)
                </h3>
                <p className="text-xs text-[var(--color-neo-muted)] mb-3">
                  Upload ZIP with React/Vue/Svelte components (up to 50MB)
                </p>
                <button
                  onClick={() => zipInputRef.current?.click()}
                  className="neo-btn neo-btn-ghost text-sm"
                >
                  <FileArchive size={16} />
                  Upload ZIP
                </button>
              </>
            )}
          </>
        )}
          <input
            ref={zipInputRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={e => handleZipUpload(e.target.files)}
          />
        </div>

        {/* Uploaded Page References List */}
        {uploadedPageRefs.length > 0 && (
          <div className="p-3 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-2 mb-2">
              <MapPin size={16} className="text-[var(--color-neo-accent)]" />
              <h4 className="font-display font-bold text-xs uppercase">
                Page-Specific References ({uploadedPageRefs.length})
              </h4>
            </div>
            <div className="space-y-1">
              {uploadedPageRefs.map((ref, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-white border-2 border-[var(--color-neo-border)] text-sm"
                >
                  <FileArchive size={14} className="text-[var(--color-neo-muted)]" />
                  <span className="font-medium truncate flex-1">{ref.filename}</span>
                  <span className="text-xs bg-[var(--color-neo-accent)] text-white px-2 py-0.5">
                    {ref.page_identifier}
                  </span>
                  <span className="text-xs text-[var(--color-neo-muted)]">
                    {ref.components_count} components
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Uploaded Components List */}
      {uploadedComponents.length > 0 && (
        <div className="p-4 bg-[var(--color-neo-bg-alt)] border-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="text-[var(--color-neo-success)]" size={18} />
            <h4 className="font-display font-bold text-sm">
              Uploaded Components ({uploadedComponents.length})
            </h4>
          </div>
          <div className="space-y-2">
            {uploadedComponents.map((comp, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-2 bg-white border-2 border-[var(--color-neo-border)]"
              >
                <FileCode size={16} className="text-[var(--color-neo-accent)]" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{comp.filename}</p>
                  <p className="text-xs text-[var(--color-neo-muted)]">
                    {comp.framework} • {comp.file_type} • {Math.round(comp.size / 1024)}KB
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
