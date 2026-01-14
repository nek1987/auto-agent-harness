import { useState, useCallback, useRef, useEffect } from 'react'
import type { SkillMatch } from '../components/SkillCard'
import type { SubTask } from '../components/TaskCard'

// Timeout constants (milliseconds)
const CONNECTION_TIMEOUT = 10000  // 10 seconds
const ANALYSIS_TIMEOUT = 120000   // 2 minutes
const DECOMPOSITION_TIMEOUT = 180000  // 3 minutes

interface FeatureData {
  name: string
  category: string
  description: string
  steps: string[]
}

interface DecompositionResult {
  totalComplexity: number
  estimatedTime: string
  mainTasksCount: number
  extensionTasksCount: number
}

interface UseSkillsAnalysisReturn {
  skills: SkillMatch[]
  tasks: SubTask[]
  decompositionResult: DecompositionResult | null
  status: string | null
  error: string | null
  isLoading: boolean
  analyze: (feature: FeatureData) => void
  decompose: (selectedSkillIds: string[]) => void
  clearAnalysis: () => void
}

export function useSkillsAnalysis(projectName: string): UseSkillsAnalysisReturn {
  const [skills, setSkills] = useState<SkillMatch[]>([])
  const [tasks, setTasks] = useState<SubTask[]>([])
  const [decompositionResult, setDecompositionResult] = useState<DecompositionResult | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const currentFeatureRef = useRef<FeatureData | null>(null)
  const operationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clear operation timeout
  const clearOperationTimeout = useCallback(() => {
    if (operationTimeoutRef.current) {
      clearTimeout(operationTimeoutRef.current)
      operationTimeoutRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
      }
      clearOperationTimeout()
    }
  }, [clearOperationTimeout])

  const clearAnalysis = useCallback(() => {
    setSkills([])
    setTasks([])
    setDecompositionResult(null)
    setStatus(null)
    setError(null)
    setIsLoading(false)
    currentFeatureRef.current = null

    clearOperationTimeout()

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
  }, [clearOperationTimeout])

  const connectWebSocket = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      // Close existing connection
      if (wsRef.current) {
        wsRef.current.close()
      }

      // Determine WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/api/skills-analysis/ws/${projectName}`

      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        // Connection timeout
        const connectionTimeout = setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            ws.close()
            setError('Connection timeout. Please try again.')
            setIsLoading(false)
            reject(new Error('Connection timeout'))
          }
        }, CONNECTION_TIMEOUT)

        ws.onopen = () => {
          clearTimeout(connectionTimeout)

          // Set up ping interval
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }))
            }
          }, 30000)

          resolve(ws)
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)

            switch (data.type) {
              case 'status':
                setStatus(data.content)
                break

              case 'skills_suggested': {
                // Clear analysis timeout on success
                clearOperationTimeout()

                // Convert server response to SkillMatch format
                const selection = data.selection || {}
                const allMatches: SkillMatch[] = []

                // Primary skills
                if (selection.primary) {
                  selection.primary.forEach((match: {
                    skill: {
                      name: string
                      display_name?: string
                      displayName?: string
                      description?: string
                      tags?: string[]
                      capabilities?: string[]
                      has_scripts?: boolean
                      hasScripts?: boolean
                      has_references?: boolean
                      hasReferences?: boolean
                    }
                    relevance_score?: number
                    relevanceScore?: number
                    match_reasons?: string[]
                    matchReasons?: string[]
                    category?: string
                  }) => {
                    allMatches.push({
                      name: match.skill.name,
                      displayName: match.skill.display_name || match.skill.displayName || match.skill.name,
                      description: match.skill.description || '',
                      relevanceScore: match.relevance_score ?? match.relevanceScore ?? 0.8,
                      matchReasons: match.match_reasons ?? match.matchReasons ?? [],
                      category: match.category || 'primary',
                      tags: match.skill.tags || [],
                      capabilities: match.skill.capabilities || [],
                      hasScripts: match.skill.has_scripts ?? match.skill.hasScripts ?? false,
                      hasReferences: match.skill.has_references ?? match.skill.hasReferences ?? false,
                    })
                  })
                }

                // Secondary skills
                if (selection.secondary) {
                  selection.secondary.forEach((match: {
                    skill: {
                      name: string
                      display_name?: string
                      displayName?: string
                      description?: string
                      tags?: string[]
                      capabilities?: string[]
                      has_scripts?: boolean
                      hasScripts?: boolean
                      has_references?: boolean
                      hasReferences?: boolean
                    }
                    relevance_score?: number
                    relevanceScore?: number
                    match_reasons?: string[]
                    matchReasons?: string[]
                    category?: string
                  }) => {
                    allMatches.push({
                      name: match.skill.name,
                      displayName: match.skill.display_name || match.skill.displayName || match.skill.name,
                      description: match.skill.description || '',
                      relevanceScore: match.relevance_score ?? match.relevanceScore ?? 0.4,
                      matchReasons: match.match_reasons ?? match.matchReasons ?? [],
                      category: match.category || 'secondary',
                      tags: match.skill.tags || [],
                      capabilities: match.skill.capabilities || [],
                      hasScripts: match.skill.has_scripts ?? match.skill.hasScripts ?? false,
                      hasReferences: match.skill.has_references ?? match.skill.hasReferences ?? false,
                    })
                  })
                }

                setSkills(allMatches)
                setIsLoading(false)
                break
              }

              case 'skills_confirmed':
                setStatus(`Selected ${data.skills?.length || 0} skills`)
                break

              case 'task_generated': {
                // Add new task to list
                const task = data.task
                if (task) {
                  const subTask: SubTask = {
                    id: task.id || `task-${Date.now()}`,
                    title: task.title || '',
                    description: task.description || '',
                    type: task.type || 'implementation',
                    estimatedComplexity: task.estimated_complexity ?? task.estimatedComplexity ?? 5,
                    assignedSkills: task.assigned_skills ?? task.assignedSkills ?? [],
                    dependencies: task.dependencies || [],
                    steps: task.steps || [],
                    isExtension: task.is_extension ?? task.isExtension ?? false,
                  }
                  setTasks(prev => [...prev, subTask])
                }
                break
              }

              case 'decomposition_complete': {
                // Clear decomposition timeout on success
                clearOperationTimeout()

                const result = data.result || {}
                setDecompositionResult({
                  totalComplexity: result.total_complexity ?? result.totalComplexity ?? 0,
                  estimatedTime: result.estimated_time ?? result.estimatedTime ?? 'Unknown',
                  mainTasksCount: result.main_tasks_count ?? result.mainTasksCount ?? 0,
                  extensionTasksCount: result.extension_tasks_count ?? result.extensionTasksCount ?? 0,
                })
                setIsLoading(false)
                setStatus('Decomposition complete')
                break
              }

              case 'error':
                setError(data.content)
                setIsLoading(false)
                break

              case 'pong':
                // Ping response, ignore
                break

              case 'task_updated':
              case 'tasks_confirmed':
                // Acknowledgments, handled locally
                break

              default:
                console.warn('Unknown message type:', data.type)
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        ws.onerror = (event) => {
          console.error('WebSocket error:', event)
          setError('Connection error')
          setIsLoading(false)
          reject(new Error('WebSocket connection failed'))
        }

        ws.onclose = (event) => {
          if (event.code !== 1000 && event.code !== 1005) {
            // Abnormal close
            setError(event.reason || 'Connection closed unexpectedly')
          }
          setIsLoading(false)

          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current)
            pingIntervalRef.current = null
          }
        }
      } catch (e) {
        console.error('Failed to create WebSocket:', e)
        setError('Failed to connect to analysis server')
        setIsLoading(false)
        reject(e)
      }
    })
  }, [projectName])

  const analyze = useCallback(async (feature: FeatureData) => {
    // Clear previous analysis
    setSkills([])
    setTasks([])
    setDecompositionResult(null)
    setError(null)
    setIsLoading(true)
    setStatus('Connecting...')
    currentFeatureRef.current = feature
    clearOperationTimeout()

    try {
      const ws = await connectWebSocket()

      // Set analysis timeout
      operationTimeoutRef.current = setTimeout(() => {
        if (skills.length === 0) {
          setError('Analysis timed out. The feature may be too complex. Try simplifying the description.')
          setIsLoading(false)
          setStatus(null)
          if (wsRef.current) {
            wsRef.current.close()
          }
        }
      }, ANALYSIS_TIMEOUT)

      // Send analyze request
      ws.send(JSON.stringify({
        type: 'analyze',
        feature: {
          name: feature.name,
          category: feature.category,
          description: feature.description,
          steps: feature.steps,
        },
      }))

      setStatus('Analyzing feature...')
    } catch (e) {
      console.error('Failed to start analysis:', e)
      clearOperationTimeout()
      setError('Failed to connect to analysis server')
      setIsLoading(false)
    }
  }, [connectWebSocket, clearOperationTimeout, skills.length])

  const decompose = useCallback((selectedSkillIds: string[]) => {
    const ws = wsRef.current

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('Not connected to server')
      return
    }

    if (!currentFeatureRef.current) {
      setError('No feature data. Run analyze first.')
      return
    }

    if (selectedSkillIds.length === 0) {
      setError('No skills selected')
      return
    }

    // Clear previous tasks and timeout
    setTasks([])
    setDecompositionResult(null)
    setIsLoading(true)
    setStatus('Decomposing feature...')
    clearOperationTimeout()

    // Set decomposition timeout
    operationTimeoutRef.current = setTimeout(() => {
      setError('Decomposition timed out. The feature may be too complex.')
      setIsLoading(false)
      setStatus(null)
      if (wsRef.current) {
        wsRef.current.close()
      }
    }, DECOMPOSITION_TIMEOUT)

    ws.send(JSON.stringify({
      type: 'decompose',
      selected_skills: selectedSkillIds,
    }))
  }, [clearOperationTimeout])

  return {
    skills,
    tasks,
    decompositionResult,
    status,
    error,
    isLoading,
    analyze,
    decompose,
    clearAnalysis,
  }
}
