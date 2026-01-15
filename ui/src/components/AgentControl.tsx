import { useState, useEffect } from 'react'
import { Play, Pause, Square, Loader2, Zap, Clock } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  usePauseAgent,
  useResumeAgent,
} from '../hooks/useProjects'
import type { AgentStatus } from '../lib/types'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
  yoloMode?: boolean  // From server status - whether currently running in YOLO mode
  mode?: string | null  // From server status - optional run mode
  lastLogTimestamp?: string | null  // ISO timestamp of last log for idle detection
}

export function AgentControl({ projectName, status, yoloMode = false, mode, lastLogTimestamp }: AgentControlProps) {
  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [idleSeconds, setIdleSeconds] = useState(0)

  // Update idle timer every second when agent is running
  useEffect(() => {
    if (status !== 'running' || !lastLogTimestamp) {
      setIdleSeconds(0)
      return
    }

    const updateIdle = () => {
      const lastTime = new Date(lastLogTimestamp).getTime()
      const now = Date.now()
      setIdleSeconds(Math.floor((now - lastTime) / 1000))
    }

    updateIdle() // Initial update
    const interval = setInterval(updateIdle, 1000)
    return () => clearInterval(interval)
  }, [status, lastLogTimestamp])

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const pauseAgent = usePauseAgent(projectName)
  const resumeAgent = useResumeAgent(projectName)

  const isLoading =
    startAgent.isPending ||
    stopAgent.isPending ||
    pauseAgent.isPending ||
    resumeAgent.isPending

  const handleStart = () => startAgent.mutate({ yoloMode: yoloEnabled })
  const handleStop = () => stopAgent.mutate()
  const handlePause = () => pauseAgent.mutate()
  const handleResume = () => resumeAgent.mutate()
  const handleRegression = () => startAgent.mutate({ mode: 'regression' })

  return (
    <div className="flex items-center gap-2">
      {/* Status Indicator */}
      <StatusIndicator status={status} />

      {/* Idle Timer Warning - shown when agent is idle for too long */}
      {status === 'running' && idleSeconds > 30 && (
        <div
          className={`flex items-center gap-1 px-2 py-1 border-3 border-[var(--color-neo-border)] ${
            idleSeconds > 60
              ? 'bg-[var(--color-neo-danger)] animate-pulse'
              : 'bg-[var(--color-neo-pending)]'
          }`}
          title="Time since last activity"
        >
          <Clock size={14} className={idleSeconds > 60 ? 'text-white' : 'text-yellow-900'} />
          <span
            className={`font-mono font-bold text-sm ${
              idleSeconds > 60 ? 'text-white' : 'text-yellow-900'
            }`}
          >
            {idleSeconds}s
          </span>
        </div>
      )}

      {/* Mode Indicator */}
      {(status === 'running' || status === 'paused') && (
        <>
          {mode === 'regression' && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-progress)] border-3 border-[var(--color-neo-border)]">
              <span className="font-display font-bold text-xs uppercase text-white">
                Regression
              </span>
            </div>
          )}
          {mode !== 'regression' && yoloMode && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
              <Zap size={14} className="text-yellow-900" />
              <span className="font-display font-bold text-xs uppercase text-yellow-900">
                YOLO
              </span>
            </div>
          )}
        </>
      )}

      {/* Control Buttons */}
      <div className="flex gap-1">
        {status === 'stopped' || status === 'crashed' ? (
          <>
            {/* YOLO Toggle - only shown when stopped */}
            <button
              onClick={() => setYoloEnabled(!yoloEnabled)}
              className={`neo-btn text-sm py-2 px-3 min-h-[44px] min-w-[44px] ${
                yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'
              }`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={18} className={yoloEnabled ? 'text-yellow-900' : ''} />
            </button>
            <button
              onClick={handleRegression}
              disabled={isLoading}
              className="neo-btn neo-btn-secondary text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title="Run Regression (verification only)"
            >
              <span className="font-display font-bold text-xs uppercase">
                RG
              </span>
            </button>
            <button
              onClick={handleStart}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title={yoloEnabled ? "Start Agent (YOLO Mode)" : "Start Agent"}
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Play size={18} />
              )}
            </button>
          </>
        ) : status === 'running' ? (
          <>
            <button
              onClick={handlePause}
              disabled={isLoading}
              className="neo-btn neo-btn-warning text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title="Pause Agent"
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Pause size={18} />
              )}
            </button>
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title="Stop Agent"
            >
              <Square size={18} />
            </button>
          </>
        ) : status === 'paused' ? (
          <>
            <button
              onClick={handleResume}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title="Resume Agent"
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Play size={18} />
              )}
            </button>
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3 min-h-[44px] min-w-[44px]"
              title="Stop Agent"
            >
              <Square size={18} />
            </button>
          </>
        ) : null}
      </div>
    </div>
  )
}

function StatusIndicator({ status }: { status: AgentStatus }) {
  const statusConfig = {
    stopped: {
      color: 'var(--color-neo-text-secondary)',
      label: 'Stopped',
      pulse: false,
    },
    running: {
      color: 'var(--color-neo-done)',
      label: 'Running',
      pulse: true,
    },
    paused: {
      color: 'var(--color-neo-pending)',
      label: 'Paused',
      pulse: false,
    },
    crashed: {
      color: 'var(--color-neo-danger)',
      label: 'Crashed',
      pulse: true,
    },
  }

  const config = statusConfig[status]

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-white border-3 border-[var(--color-neo-border)]">
      <span
        className={`w-3 h-3 rounded-full ${config.pulse ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: config.color }}
      />
      <span
        className="font-display font-bold text-sm uppercase"
        style={{ color: config.color }}
      >
        {config.label}
      </span>
    </div>
  )
}
