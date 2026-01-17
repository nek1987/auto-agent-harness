import { Loader2, Palette, Type, Box, Square, Layers } from 'lucide-react'
import type { DesignTokens } from '../../lib/types'

interface DesignTokenPreviewProps {
  tokens: DesignTokens | null
  isExtracting: boolean
}

export function DesignTokenPreview({
  tokens,
  isExtracting,
}: DesignTokenPreviewProps) {
  if (isExtracting) {
    return (
      <div className="text-center py-12">
        <Loader2 className="animate-spin mx-auto mb-4" size={48} />
      <h3 className="font-display font-bold mb-2">
        Analyzing Design Tokens...
      </h3>
      <p className="text-[var(--color-neo-muted)] text-sm">
        The redesign planner is reviewing your references
      </p>
      </div>
    )
  }

  if (!tokens) {
    return (
      <div className="text-center py-12">
        <Palette className="mx-auto mb-4 text-[var(--color-neo-muted)]" size={48} />
      <h3 className="font-display font-bold mb-2">
        No Tokens Extracted Yet
      </h3>
      <p className="text-[var(--color-neo-muted)] text-sm">
        Run the redesign planner to extract tokens from your references
      </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Colors Section */}
      {tokens.colors && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Palette size={18} />
            <h4 className="font-display font-bold uppercase text-sm">
              Colors
            </h4>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Object.entries(tokens.colors).map(([category, scale]) => (
              <div
                key={category}
                className="border-3 border-[var(--color-neo-border)] p-4 bg-white"
              >
                <h5 className="font-display font-bold text-sm capitalize mb-3">
                  {category}
                </h5>
                {typeof scale === 'object' && scale !== null && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(scale as Record<string, unknown>).map(([shade, value]) => {
                      // Handle semantic colors with DEFAULT key
                      const colorValue = typeof value === 'object' && value !== null && 'DEFAULT' in (value as object)
                        ? (value as { DEFAULT: string }).DEFAULT
                        : typeof value === 'string'
                          ? value
                          : null

                      if (!colorValue) return null

                      return (
                        <div
                          key={shade}
                          className="flex flex-col items-center"
                          title={colorValue}
                        >
                          <div
                            className="w-10 h-10 border-3 border-[var(--color-neo-border)]"
                            style={{ backgroundColor: colorValue }}
                          />
                          <span className="text-xs mt-1 text-[var(--color-neo-muted)]">
                            {shade}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Typography Section */}
      {tokens.typography && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Type size={18} />
            <h4 className="font-display font-bold uppercase text-sm">
              Typography
            </h4>
          </div>
          <div className="border-3 border-[var(--color-neo-border)] p-4 bg-white space-y-4">
            {/* Font Families */}
            {tokens.typography.fontFamily && (
              <div>
                <h5 className="text-xs font-bold uppercase text-[var(--color-neo-muted)] mb-2">
                  Font Families
                </h5>
                <div className="space-y-2">
                  {Object.entries(tokens.typography.fontFamily).map(([key, fonts]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-sm font-bold capitalize w-16">{key}:</span>
                      <span className="text-sm text-[var(--color-neo-muted)]">
                        {Array.isArray(fonts) ? fonts.join(', ') : String(fonts)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Font Sizes */}
            {tokens.typography.fontSize && (
              <div>
                <h5 className="text-xs font-bold uppercase text-[var(--color-neo-muted)] mb-2">
                  Font Sizes
                </h5>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(tokens.typography.fontSize).map(([size, config]) => (
                    <div key={size} className="text-center">
                      <span
                        className="block font-display"
                        style={{ fontSize: typeof config === 'object' && config !== null && 'value' in config ? (config as { value: string }).value : '16px' }}
                      >
                        Aa
                      </span>
                      <span className="text-xs text-[var(--color-neo-muted)]">{size}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Font Weights */}
            {tokens.typography.fontWeight && (
              <div>
                <h5 className="text-xs font-bold uppercase text-[var(--color-neo-muted)] mb-2">
                  Font Weights
                </h5>
                <div className="flex flex-wrap gap-4">
                  {Object.entries(tokens.typography.fontWeight).map(([name, weight]) => (
                    <span
                      key={name}
                      className="text-sm"
                      style={{ fontWeight: weight }}
                    >
                      {name} ({weight})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Spacing Section */}
      {tokens.spacing && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Box size={18} />
            <h4 className="font-display font-bold uppercase text-sm">
              Spacing
            </h4>
          </div>
          <div className="border-3 border-[var(--color-neo-border)] p-4 bg-white">
            <div className="flex flex-wrap gap-3 items-end">
              {Object.entries(tokens.spacing).map(([key, value]) => (
                <div key={key} className="flex flex-col items-center">
                  <div
                    className="bg-[var(--color-neo-accent)]/30 border border-[var(--color-neo-accent)]"
                    style={{
                      width: value,
                      height: value,
                      minWidth: '8px',
                      minHeight: '8px',
                      maxWidth: '64px',
                      maxHeight: '64px',
                    }}
                  />
                  <span className="text-xs mt-1 text-[var(--color-neo-muted)]">
                    {key}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Borders Section */}
      {tokens.borders && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Square size={18} />
            <h4 className="font-display font-bold uppercase text-sm">
              Borders
            </h4>
          </div>
          <div className="border-3 border-[var(--color-neo-border)] p-4 bg-white">
            {tokens.borders.radius && (
              <div className="mb-4">
                <h5 className="text-xs font-bold uppercase text-[var(--color-neo-muted)] mb-2">
                  Border Radius
                </h5>
                <div className="flex flex-wrap gap-4">
                  {Object.entries(tokens.borders.radius).map(([size, value]) => (
                    <div key={size} className="flex flex-col items-center">
                      <div
                        className="w-12 h-12 bg-[var(--color-neo-accent)]/30 border-2 border-[var(--color-neo-accent)]"
                        style={{ borderRadius: value }}
                      />
                      <span className="text-xs mt-1 text-[var(--color-neo-muted)]">
                        {size} ({value})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Shadows Section */}
      {tokens.shadows && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Layers size={18} />
            <h4 className="font-display font-bold uppercase text-sm">
              Shadows
            </h4>
          </div>
          <div className="border-3 border-[var(--color-neo-border)] p-4 bg-white">
            <div className="flex flex-wrap gap-4">
              {Object.entries(tokens.shadows).map(([size, value]) => (
                <div key={size} className="flex flex-col items-center">
                  <div
                    className="w-16 h-16 bg-white"
                    style={{ boxShadow: value }}
                  />
                  <span className="text-xs mt-2 text-[var(--color-neo-muted)]">
                    {size}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
