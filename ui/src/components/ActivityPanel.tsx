/**
 * Activity Panel Component
 *
 * Shows current agent activity - which tool is running, which feature is being worked on.
 * Parses log output to extract tool calls and feature information.
 */

import { useMemo } from 'react'
import { Wrench, FileCode, Loader2 } from 'lucide-react'
import type { AgentStatus } from '../lib/types'

interface ActivityPanelProps {
  logs: Array<{ line: string; timestamp: string }>
  agentStatus: AgentStatus
}

/**
 * Extract current tool from logs by finding the most recent [Tool: xxx] that hasn't completed
 */
function getCurrentTool(logs: Array<{ line: string }>): string | null {
  for (let i = logs.length - 1; i >= 0; i--) {
    const line = logs[i].line

    // Check if this is a tool start
    const toolMatch = line.match(/^\[Tool:\s*(.+?)\]/)
    if (toolMatch) {
      const toolName = toolMatch[1]

      // Check if tool has completed by looking at subsequent lines
      const subsequentLines = logs.slice(i + 1)
      const isDone = subsequentLines.some(l =>
        l.line.includes('[Done]') ||
        l.line.includes('[Error]') ||
        l.line.match(/^\[Tool:/)  // Another tool started
      )

      if (!isDone) {
        return toolName
      }
    }
  }
  return null
}

/**
 * Extract current feature from logs by parsing feature_get_next response
 */
function getCurrentFeature(logs: Array<{ line: string }>): { id: number; name: string; category: string } | null {
  // Look for feature_get_next or feature_mark_in_progress responses
  for (let i = logs.length - 1; i >= 0; i--) {
    const line = logs[i].line

    // Look for JSON response from feature tools
    if (line.includes('"type":') && line.includes('"feature"')) {
      try {
        // Try to parse JSON from the line
        const jsonMatch = line.match(/\{[\s\S]*"feature"[\s\S]*\}/)
        if (jsonMatch) {
          const data = JSON.parse(jsonMatch[0])
          if (data.feature) {
            return {
              id: data.feature.id,
              name: data.feature.name,
              category: data.feature.category
            }
          }
        }
      } catch {
        // Ignore parse errors
      }
    }

    // Also look for "Working on feature #X" patterns in Claude's output
    const featurePattern = line.match(/(?:Working on|Implementing|Starting)\s+(?:feature\s+)?#?(\d+)/i)
    if (featurePattern) {
      return {
        id: parseInt(featurePattern[1], 10),
        name: 'Feature #' + featurePattern[1],
        category: ''
      }
    }
  }
  return null
}

/**
 * Format tool name for display (shorten MCP tool names)
 */
function formatToolName(toolName: string): string {
  // Shorten MCP tool names like "mcp__features__feature_get_next" -> "feature_get_next"
  if (toolName.startsWith('mcp__')) {
    const parts = toolName.split('__')
    return parts[parts.length - 1]
  }
  return toolName
}

export function ActivityPanel({ logs, agentStatus }: ActivityPanelProps) {
  const currentTool = useMemo(() => getCurrentTool(logs), [logs])
  const currentFeature = useMemo(() => getCurrentFeature(logs), [logs])

  // Only show when agent is running and there's something to show
  if (agentStatus !== 'running' || (!currentTool && !currentFeature)) {
    return null
  }

  return (
    <div className="neo-card p-4">
      <h3 className="font-display text-sm font-bold uppercase mb-3 text-[var(--color-neo-text-secondary)]">
        Current Activity
      </h3>

      <div className="space-y-3">
        {/* Current Tool */}
        {currentTool && (
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)] rounded">
              <Wrench size={16} className="text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-[var(--color-neo-text-secondary)] uppercase">
                Tool
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold truncate">
                  {formatToolName(currentTool)}
                </span>
                <Loader2 size={14} className="animate-spin text-[var(--color-neo-progress)]" />
              </div>
            </div>
          </div>
        )}

        {/* Current Feature */}
        {currentFeature && (
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 bg-[var(--color-neo-pending)] border-2 border-[var(--color-neo-border)] rounded">
              <FileCode size={16} className="text-yellow-900" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-[var(--color-neo-text-secondary)] uppercase">
                Feature #{currentFeature.id}
                {currentFeature.category && (
                  <span className="ml-2 text-[var(--color-neo-progress)]">
                    [{currentFeature.category}]
                  </span>
                )}
              </div>
              <div className="font-mono text-sm font-bold truncate">
                {currentFeature.name}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
