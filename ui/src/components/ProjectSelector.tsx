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
    <div className="relative">
      {/* Dropdown Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="neo-btn bg-white text-[var(--color-neo-text)] min-w-[200px] justify-between"
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 size={18} className="animate-spin" />
        ) : selectedProject ? (
          <>
            <span className="flex items-center gap-2">
              <FolderOpen size={18} />
              {selectedProject}
            </span>
            {selectedProjectData && selectedProjectData.stats.total > 0 && (
              <span className="neo-badge bg-[var(--color-neo-done)] ml-2">
                {selectedProjectData.stats.percentage}%
              </span>
            )}
          </>
        ) : (
          <span className="text-[var(--color-neo-text-secondary)]">
            Select Project
          </span>
        )}
        <ChevronDown size={18} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
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
          <div className="absolute top-full left-0 mt-2 w-full neo-dropdown z-50 min-w-[280px]">
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
                      className="flex-1 neo-dropdown-item flex items-center justify-between"
                    >
                      <span className="flex items-center gap-2">
                        <FolderOpen size={16} />
                        {project.name}
                      </span>
                      {project.stats.total > 0 && (
                        <span className="text-sm font-mono">
                          {project.stats.passing}/{project.stats.total}
                        </span>
                      )}
                    </button>
                    <button
                      onClick={(e) => handleDeleteClick(e, project.name)}
                      className="p-2 opacity-0 group-hover:opacity-100 hover:text-[var(--color-neo-danger)] transition-all"
                      title="Delete project"
                    >
                      <Trash2 size={14} />
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
              className="w-full neo-dropdown-item flex items-center gap-2 font-bold"
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
              className="w-full neo-dropdown-item flex items-center gap-2"
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
