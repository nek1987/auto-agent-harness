import { useState } from 'react'
import { ChevronDown, Plus, FolderOpen, Loader2, Download, Trash2 } from 'lucide-react'
import type { ProjectSummary } from '../lib/types'
import { NewProjectModal } from './NewProjectModal'
import { ImportProjectModal } from './ImportProjectModal'
import { DeleteProjectModal } from './DeleteProjectModal'

interface ProjectSelectorProps {
  projects: ProjectSummary[]
  selectedProject: string | null
  onSelectProject: (name: string | null) => void
  onProjectDeleted?: () => void
  isLoading: boolean
}

export function ProjectSelector({
  projects,
  selectedProject,
  onSelectProject,
  onProjectDeleted,
  isLoading,
}: ProjectSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [showNewProjectModal, setShowNewProjectModal] = useState(false)
  const [showImportProjectModal, setShowImportProjectModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null)

  const handleProjectCreated = (projectName: string) => {
    onSelectProject(projectName)
    setIsOpen(false)
  }

  const handleDeleteClick = (e: React.MouseEvent, projectName: string) => {
    e.stopPropagation()
    setProjectToDelete(projectName)
    setShowDeleteModal(true)
  }

  const handleProjectDeleted = () => {
    // If deleted project was selected, clear selection
    if (projectToDelete === selectedProject) {
      onSelectProject(null)
    }
    setShowDeleteModal(false)
    setProjectToDelete(null)
    onProjectDeleted?.()
  }

  const selectedProjectData = projects.find(p => p.name === selectedProject)

  return (
    <div className="relative flex-1 sm:flex-initial">
      {/* Dropdown Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="neo-btn bg-white text-[var(--color-neo-text)] w-full sm:w-auto sm:min-w-[200px] min-h-[44px] justify-between"
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 size={18} className="animate-spin" />
        ) : selectedProject ? (
          <>
            <span className="flex items-center gap-2 truncate max-w-[120px] sm:max-w-none">
              <FolderOpen size={18} className="flex-shrink-0" />
              <span className="truncate">{selectedProject}</span>
            </span>
            {selectedProjectData && selectedProjectData.stats.total > 0 && (
              <span className="neo-badge bg-[var(--color-neo-done)] ml-2 flex-shrink-0">
                {selectedProjectData.stats.percentage}%
              </span>
            )}
          </>
        ) : (
          <span className="text-[var(--color-neo-text-secondary)]">
            Select Project
          </span>
        )}
        <ChevronDown size={18} className={`flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute top-full left-0 right-0 sm:right-auto mt-2 neo-dropdown z-50 w-full sm:w-auto sm:min-w-[280px] max-w-[calc(100vw-1rem)]">
            {projects.length > 0 ? (
              <div className="max-h-[300px] overflow-auto">
                {projects.map(project => (
                  <div
                    key={project.name}
                    className={`flex items-center group ${
                      project.name === selectedProject
                        ? 'bg-[var(--color-neo-pending)]'
                        : ''
                    }`}
                  >
                    <button
                      onClick={() => {
                        onSelectProject(project.name)
                        setIsOpen(false)
                      }}
                      className="flex-1 neo-dropdown-item flex items-center justify-between min-h-[48px]"
                    >
                      <span className="flex items-center gap-2 truncate">
                        <FolderOpen size={16} className="flex-shrink-0" />
                        <span className="truncate">{project.name}</span>
                      </span>
                      {project.stats.total > 0 && (
                        <span className="text-sm font-mono flex-shrink-0 ml-2">
                          {project.stats.passing}/{project.stats.total}
                        </span>
                      )}
                    </button>
                    <button
                      onClick={(e) => handleDeleteClick(e, project.name)}
                      className="p-3 min-w-[44px] min-h-[44px] opacity-100 sm:opacity-0 sm:group-hover:opacity-100 hover:text-[var(--color-neo-danger)] transition-all flex items-center justify-center"
                      title="Delete project"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-[var(--color-neo-text-secondary)]">
                No projects yet
              </div>
            )}

            {/* Divider */}
            <div className="border-t-3 border-[var(--color-neo-border)]" />

            {/* Create New */}
            <button
              onClick={() => {
                setShowNewProjectModal(true)
                setIsOpen(false)
              }}
              className="w-full neo-dropdown-item flex items-center gap-2 font-bold min-h-[48px]"
            >
              <Plus size={16} />
              New Project
            </button>

            {/* Import Existing */}
            <button
              onClick={() => {
                setShowImportProjectModal(true)
                setIsOpen(false)
              }}
              className="w-full neo-dropdown-item flex items-center gap-2 min-h-[48px]"
            >
              <Download size={16} />
              Import Existing
            </button>
          </div>
        </>
      )}

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={showNewProjectModal}
        onClose={() => setShowNewProjectModal(false)}
        onProjectCreated={handleProjectCreated}
      />

      {/* Import Project Modal */}
      <ImportProjectModal
        isOpen={showImportProjectModal}
        onClose={() => setShowImportProjectModal(false)}
        onProjectCreated={handleProjectCreated}
      />

      {/* Delete Project Modal */}
      {projectToDelete && (
        <DeleteProjectModal
          isOpen={showDeleteModal}
          projectName={projectToDelete}
          onClose={() => {
            setShowDeleteModal(false)
            setProjectToDelete(null)
          }}
          onDeleted={handleProjectDeleted}
        />
      )}
    </div>
  )
}
