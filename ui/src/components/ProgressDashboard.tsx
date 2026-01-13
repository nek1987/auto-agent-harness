import { Wifi, WifiOff } from 'lucide-react'

interface ProgressDashboardProps {
  passing: number
  total: number
  percentage: number
  isConnected: boolean
}

export function ProgressDashboard({
  passing,
  total,
  percentage,
  isConnected,
}: ProgressDashboardProps) {
  return (
    <div className="neo-card p-4 sm:p-6">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h2 className="font-display text-lg sm:text-xl font-bold uppercase">
          Progress
        </h2>
        <div className="flex items-center gap-1.5 sm:gap-2">
          {isConnected ? (
            <>
              <Wifi size={14} className="sm:w-4 sm:h-4 text-[var(--color-neo-done)]" />
              <span className="text-xs sm:text-sm text-[var(--color-neo-done)]">Live</span>
            </>
          ) : (
            <>
              <WifiOff size={14} className="sm:w-4 sm:h-4 text-[var(--color-neo-danger)]" />
              <span className="text-xs sm:text-sm text-[var(--color-neo-danger)]">Offline</span>
            </>
          )}
        </div>
      </div>

      {/* Large Percentage */}
      <div className="text-center mb-4 sm:mb-6">
        <span className="font-display text-4xl sm:text-5xl md:text-6xl font-bold">
          {percentage.toFixed(1)}
        </span>
        <span className="font-display text-xl sm:text-2xl md:text-3xl font-bold text-[var(--color-neo-text-secondary)]">
          %
        </span>
      </div>

      {/* Progress Bar */}
      <div className="neo-progress mb-3 sm:mb-4">
        <div
          className="neo-progress-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Stats */}
      <div className="flex justify-center gap-4 sm:gap-6 md:gap-8 text-center">
        <div>
          <span className="font-mono text-xl sm:text-2xl md:text-3xl font-bold text-[var(--color-neo-done)]">
            {passing}
          </span>
          <span className="block text-xs sm:text-sm text-[var(--color-neo-text-secondary)] uppercase">
            Passing
          </span>
        </div>
        <div className="text-2xl sm:text-3xl md:text-4xl text-[var(--color-neo-text-secondary)]">/</div>
        <div>
          <span className="font-mono text-xl sm:text-2xl md:text-3xl font-bold">
            {total}
          </span>
          <span className="block text-xs sm:text-sm text-[var(--color-neo-text-secondary)] uppercase">
            Total
          </span>
        </div>
      </div>
    </div>
  )
}
