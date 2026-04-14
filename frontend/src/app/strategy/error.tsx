"use client";

export default function StrategyError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Strategy</h2>
        <p className="text-sm text-muted mt-1">
          Manage vault strategy and deposits
        </p>
      </div>

      <div className="rounded-lg border border-accent-red/30 bg-accent-red/5 p-5">
        <h3 className="text-sm font-semibold text-accent-red mb-2">
          Failed to load strategy page
        </h3>
        <p className="text-xs text-muted mb-4">
          {error.message || "An unexpected error occurred."}
        </p>
        <button
          onClick={reset}
          className="px-5 py-2.5 rounded-lg text-sm font-medium bg-white/10 text-foreground hover:bg-white/20 transition-colors"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
