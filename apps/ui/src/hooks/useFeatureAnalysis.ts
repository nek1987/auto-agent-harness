import { useState, useCallback, useRef, useEffect } from 'react'
import type { Suggestion, ComplexityAssessment } from '../components/FeatureSuggestionsPanel'

interface FeatureData {
  name: string
  category: string
  description: string
  steps: string[]
}

interface UseFeatureAnalysisReturn {
  suggestions: Suggestion[]
  complexity: ComplexityAssessment | null
  isAnalyzing: boolean
  error: string | null
  analyze: (feature: FeatureData) => void
  toggleSuggestion: (id: string) => void
  removeSuggestion: (id: string) => void
  editSuggestion: (id: string, updates: Partial<Suggestion>) => void
  clearAnalysis: () => void
}

export function useFeatureAnalysis(projectName: string): UseFeatureAnalysisReturn {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [complexity, setComplexity] = useState<ComplexityAssessment | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
      }
    }
  }, [])

  const clearAnalysis = useCallback(() => {
    setSuggestions([])
    setComplexity(null)
    setError(null)
    setIsAnalyzing(false)

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
  }, [])

  const analyze = useCallback((feature: FeatureData) => {
    // Clear previous analysis
    setSuggestions([])
    setComplexity(null)
    setError(null)
    setIsAnalyzing(true)

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/feature-analyze/ws/${projectName}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
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

        // Set up ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          switch (data.type) {
            case 'status':
              // Status updates are informational
              break

            case 'text':
              // Text chunks from Claude (streaming response)
              break

            case 'suggestion':
              // Add new suggestion with selected=true by default
              setSuggestions(prev => [...prev, {
                ...data.suggestion,
                selected: true,
              }])
              break

            case 'complexity':
              setComplexity(data.complexity)
              break

            case 'analysis_complete':
              setIsAnalyzing(false)
              break

            case 'error':
              setError(data.content)
              setIsAnalyzing(false)
              break

            case 'pong':
              // Ping response, ignore
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
        setIsAnalyzing(false)
      }

      ws.onclose = (event) => {
        if (event.code !== 1000 && event.code !== 1005) {
          // Abnormal close
          if (!error) {
            setError(event.reason || 'Connection closed unexpectedly')
          }
        }
        setIsAnalyzing(false)

        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
      }
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      setError('Failed to connect to analysis server')
      setIsAnalyzing(false)
    }
  }, [projectName, error])

  const toggleSuggestion = useCallback((id: string) => {
    setSuggestions(prev =>
      prev.map(s => s.id === id ? { ...s, selected: !s.selected } : s)
    )
  }, [])

  const removeSuggestion = useCallback((id: string) => {
    setSuggestions(prev => prev.filter(s => s.id !== id))
  }, [])

  const editSuggestion = useCallback((id: string, updates: Partial<Suggestion>) => {
    setSuggestions(prev =>
      prev.map(s => s.id === id ? { ...s, ...updates } : s)
    )
  }, [])

  return {
    suggestions,
    complexity,
    isAnalyzing,
    error,
    analyze,
    toggleSuggestion,
    removeSuggestion,
    editSuggestion,
    clearAnalysis,
  }
}
