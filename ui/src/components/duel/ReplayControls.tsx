import { Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import { cn } from '@/lib/cn'

const SPEEDS = [0.5, 1, 2, 4]

export function ReplayControls({
  index,
  total,
  playing,
  speed,
  onSeek,
  onTogglePlay,
  onSpeed,
}: {
  index: number
  total: number
  playing: boolean
  speed: number
  onSeek: (index: number) => void
  onTogglePlay: () => void
  onSpeed: (speed: number) => void
}) {
  const last = Math.max(0, total - 1)
  return (
    <div className="flex items-center gap-2.5 border border-edge bg-panel px-3 py-2">
      <button
        type="button"
        onClick={() => onSeek(Math.max(0, index - 1))}
        disabled={index === 0}
        aria-label="Previous step"
        className="text-faint transition-colors hover:text-gold disabled:opacity-30 disabled:hover:text-faint"
      >
        <SkipBack size={14} />
      </button>

      <button
        type="button"
        onClick={onTogglePlay}
        aria-label={playing ? 'Pause' : 'Play'}
        className="bevel-sm flex size-8 items-center justify-center bg-gold text-void transition-colors hover:bg-[#eec96f]"
      >
        {playing ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
      </button>

      <button
        type="button"
        onClick={() => onSeek(Math.min(last, index + 1))}
        disabled={index >= last}
        aria-label="Next step"
        className="text-faint transition-colors hover:text-gold disabled:opacity-30 disabled:hover:text-faint"
      >
        <SkipForward size={14} />
      </button>

      <input
        type="range"
        min={0}
        max={last}
        value={index}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Duel timeline"
        className="min-w-0 flex-1 accent-[var(--color-gold)]"
      />

      <span className="shrink-0 font-mono text-[10.5px] tabular text-faint">
        {index + 1}/{total}
      </span>

      <div className="flex shrink-0 items-center">
        {SPEEDS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onSpeed(option)}
            className={cn(
              'px-1.5 py-0.5 font-mono text-[10px] tabular transition-colors',
              speed === option ? 'text-gold' : 'text-faint hover:text-muted',
            )}
          >
            {option}x
          </button>
        ))}
      </div>
    </div>
  )
}
