const STYLES: Record<string, { label: string; classes: string }> = {
  worked: { label: 'worked', classes: 'text-verdict-worked border-verdict-worked/50' },
  backfired: { label: 'backfired', classes: 'text-verdict-backfired border-verdict-backfired/50' },
  unclear: { label: 'unclear', classes: 'text-verdict-unclear border-verdict-unclear/50' },
  shifted: { label: 'shifted', classes: 'text-verdict-shifted border-verdict-shifted/50' },
  no_effect: { label: 'no effect', classes: 'text-verdict-noeffect border-verdict-noeffect/50' },
  excluded: { label: 'excluded', classes: 'text-verdict-noeffect border-verdict-noeffect/50' },
  insufficient_data: {
    label: 'insufficient data',
    classes: 'text-verdict-insufficient border-verdict-insufficient/50',
  },
}

export function VerdictBadge({ verdict }: { verdict: string }) {
  const style = STYLES[verdict] ?? {
    label: verdict,
    classes: 'text-gray-400 border-gray-600',
  }
  return (
    <span className={`text-xs uppercase tracking-wider border px-2 py-0.5 rounded-sm ${style.classes}`}>
      {style.label}
    </span>
  )
}
