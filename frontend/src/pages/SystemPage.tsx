import { cn } from '../lib/utils';
import { useVersion } from '../api/version';

// ── Static UI library manifest ──────────────────────────────────────────────

const UI_LIBRARIES = [
  { label: 'React', value: '18', detail: '^18.3.1' },
  { label: 'React Router', value: 'v6', detail: '^6.28.0' },
  { label: 'React Query', value: 'v5', detail: '^5.62.7' },
  { label: 'Tailwind CSS', value: 'v3', detail: '^3.4.16' },
  { label: 'shadcn/ui', value: '—', detail: 'component library' },
] as const;

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionPanel({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border border-slate-200 bg-white overflow-hidden',
      )}
    >
      {/* Header bar with left accent stripe */}
      <div className={cn('flex items-center gap-3 border-b border-slate-200 px-6 py-4', accent)}>
        <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
          {title}
        </h2>
      </div>
      <div className="divide-y divide-slate-100">{children}</div>
    </div>
  );
}

function DataRow({
  label,
  value,
  mono = false,
  muted = false,
  skeleton = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
  muted?: boolean;
  skeleton?: boolean;
}) {
  return (
    <div className="flex items-center px-6 py-3.5 gap-4">
      <span className="w-44 shrink-0 text-sm text-slate-500">{label}</span>
      {skeleton ? (
        <div className="h-4 w-32 animate-pulse rounded bg-slate-100" />
      ) : (
        <span
          className={cn(
            'text-sm',
            mono && 'font-mono',
            muted ? 'text-slate-400 italic' : 'text-slate-900',
          )}
        >
          {value ?? <span className="text-slate-300 italic">unavailable</span>}
        </span>
      )}
    </div>
  );
}

function LibraryRow({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="flex items-center px-6 py-3.5 gap-4">
      <span className="w-44 shrink-0 text-sm text-slate-500">{label}</span>
      <span className="font-mono text-sm text-slate-900">{value}</span>
      <span className="ml-2 text-xs text-slate-400">{detail}</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SystemPage() {
  const { data, isLoading, error } = useVersion();

  // Resolve frontend version: prefer API response, fall back to build-time inject.
  const frontendVersion =
    data?.frontend_version ?? (import.meta.env.VITE_APP_VERSION as string | undefined) ?? null;

  const gitSha = data?.git_sha ? data.git_sha.slice(0, 8) : null;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">System</h1>
        <p className="mt-1 text-sm text-slate-500">
          Deployment and dependency information for all components.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Could not reach the version endpoint. Component versions may be incomplete.
        </div>
      )}

      <div className="flex flex-col gap-6">
        {/* ── Component Versions ── */}
        <SectionPanel title="Component Versions" accent="bg-white">
          <DataRow
            label="Backend"
            value={data?.backend_version}
            mono
            skeleton={isLoading}
          />
          <DataRow
            label="Bot"
            value={data?.bot_version}
            mono
            skeleton={isLoading}
          />
          <DataRow
            label="Frontend"
            value={frontendVersion}
            mono
            skeleton={isLoading}
          />
          <DataRow
            label="Git SHA"
            value={gitSha}
            mono
            muted={!gitSha}
            skeleton={isLoading}
          />
        </SectionPanel>

        {/* ── UI Libraries ── */}
        <SectionPanel title="UI Libraries" accent="bg-white">
          {UI_LIBRARIES.map((lib) => (
            <LibraryRow key={lib.label} label={lib.label} value={lib.value} detail={lib.detail} />
          ))}
        </SectionPanel>
      </div>
    </div>
  );
}
