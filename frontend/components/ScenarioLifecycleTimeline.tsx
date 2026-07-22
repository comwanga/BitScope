"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  TransactionLifecycleEvent,
  TransactionLifecycleTimeline,
  fetchScenarioLifecycle
} from "@/lib/api";

const eventLabels: Record<TransactionLifecycleEvent["event_type"], string> = {
  wallet_prepared: "Wallet prepared",
  utxo_selected: "UTXO selected",
  raw_transaction_created: "Raw transaction created",
  transaction_funded: "Transaction funded",
  psbt_created: "PSBT created",
  psbt_partially_signed: "PSBT partially signed",
  psbt_completed: "PSBT completed",
  transaction_finalized: "Transaction finalized",
  mempool_preflight_completed: "Mempool preflight",
  transaction_broadcast: "Transaction broadcast",
  transaction_entered_mempool: "Entered mempool",
  transaction_replaced: "Transaction replaced",
  child_transaction_created: "Child transaction created",
  transaction_confirmed: "Transaction confirmed",
  timelock_matured: "Timelock matured",
  scenario_cleaned_up: "Scenario cleaned up"
};

const relationshipLabels: Record<NonNullable<TransactionLifecycleEvent["relationship"]>["relationship_type"], string> = {
  replaces: "Replaces",
  replaced_by: "Replaced by",
  child_of: "Child of",
  parent_of: "Parent of",
  conflicts_with: "Conflicts with"
};

export function ScenarioLifecycleTimelineView() {
  const [runId, setRunId] = useState("");
  const [labSessionId, setLabSessionId] = useState("");
  const [timeline, setTimeline] = useState<TransactionLifecycleTimeline | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setRunId(query.get("run_id") ?? "");
    setLabSessionId(query.get("lab_session_id") ?? "");
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runId.trim() || !labSessionId.trim()) {
      setError("Provide both the scenario run ID and its lab session ID.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setTimeline(await fetchScenarioLifecycle(runId.trim(), labSessionId.trim()));
    } catch (caught) {
      setTimeline(null);
      setError(caught instanceof Error ? caught.message : "The scenario lifecycle could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Scenario evidence</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Transaction lifecycle</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Inspect the exact transaction states recorded by the backend. Missing states are left missing; this view never derives events from neighboring evidence.
        </p>
      </header>

      <form onSubmit={submit} className="grid gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm md:grid-cols-[1fr_1fr_auto]">
        <label className="grid gap-1 text-sm font-medium text-stone-700">
          Scenario run ID
          <input value={runId} onChange={(event) => setRunId(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="UUID" />
        </label>
        <label className="grid gap-1 text-sm font-medium text-stone-700">
          Lab session ID
          <input value={labSessionId} onChange={(event) => setLabSessionId(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="Session owner" />
        </label>
        <button type="submit" disabled={loading} className="self-end rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
          {loading ? "Loading" : "Load timeline"}
        </button>
      </form>

      {error ? <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}
      {timeline ? <RecordedTimeline timeline={timeline} /> : null}
    </div>
  );
}

function RecordedTimeline({ timeline }: { timeline: TransactionLifecycleTimeline }) {
  return (
    <section className="space-y-5" aria-labelledby="lifecycle-title">
      <div>
        <p className="text-sm font-semibold uppercase text-forest">{timeline.scenario_id} · v{timeline.scenario_version}</p>
        <h2 id="lifecycle-title" className="mt-2 text-2xl font-semibold text-ink">Recorded events</h2>
        <p className="mt-2 text-sm text-stone-600">{timeline.events.length} persisted event{timeline.events.length === 1 ? "" : "s"} for run <code>{timeline.run_id}</code>.</p>
      </div>
      {timeline.events.length === 0 ? (
        <p className="rounded-lg border border-stone-300 bg-panel p-5 text-stone-700">The backend recorded no lifecycle events. No missing states are inferred.</p>
      ) : (
        <ol className="space-y-4">
          {timeline.events.map((event) => <LifecycleCard key={event.event_id} event={event} />)}
        </ol>
      )}
    </section>
  );
}

function LifecycleCard({ event }: { event: TransactionLifecycleEvent }) {
  const isMaturity = event.event_type === "timelock_matured";
  return (
    <li className={`rounded-lg border bg-panel p-4 shadow-sm sm:p-5 ${isMaturity ? "border-brass" : "border-stone-300"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">#{event.ordinal} · {event.track_id}</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">{eventLabels[event.event_type]}</h3>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">{event.transaction_state}</span>
          {event.block_height !== null ? <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">height {event.block_height}</span> : null}
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-stone-700">{event.explanation}</p>
      {event.relationship ? (
        <div className="mt-4 rounded-md border border-brass bg-stone-50 p-3 text-sm">
          <p className="font-semibold text-ink">{relationshipLabels[event.relationship.relationship_type]} → <code className="break-all">{event.relationship.related_txid}</code></p>
          <p className="mt-1 text-stone-700">{event.relationship.explanation}</p>
        </div>
      ) : null}
      <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Datum label="Transaction" value={event.transaction_id} mono />
        <Datum label="Evidence" value={event.evidence_id} mono />
        <Datum label="RPC" value={event.rpc_method} mono />
        <Datum label="Captured" value={new Date(event.timestamp).toLocaleString()} />
        <Datum label="Transaction hex ref" value={event.transaction_hex_ref} mono />
        <Datum label="PSBT ref" value={event.psbt_ref} mono />
        <Datum label="Fee" value={event.fee_btc === null ? null : `${event.fee_btc} BTC`} />
        <Datum label="Fee rate" value={event.fee_rate_sat_vb === null ? null : `${event.fee_rate_sat_vb} sat/vB`} />
        <Datum label="Locktime" value={event.locktime?.toString() ?? null} />
        <Datum label="Sequences" value={event.sequence_values.length ? event.sequence_values.join(", ") : null} mono />
      </dl>
      <details className="mt-4 rounded-md border border-stone-300 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-ink">Inspect RPC, CLI, and safe raw evidence</summary>
        <div className="mt-3 space-y-3">
          <p className="text-sm text-stone-700"><span className="font-semibold">Step:</span> <code>{event.step_id}</code></p>
          <pre className="overflow-x-auto rounded-md bg-stone-100 p-3 text-xs"><code>{formatCommand(event)}</code></pre>
          <pre className="max-h-96 overflow-auto rounded-md bg-stone-100 p-3 text-xs"><code>{JSON.stringify(event.raw_safe_core_result, null, 2)}</code></pre>
        </div>
      </details>
    </li>
  );
}

function Datum({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (value === null) return null;
  return <div className="min-w-0"><dt className="font-semibold text-stone-600">{label}</dt><dd className={`mt-0.5 break-all text-ink ${mono ? "font-mono" : ""}`}>{value}</dd></div>;
}

function formatCommand(event: TransactionLifecycleEvent): string {
  return [event.cli_command.executable, ...event.cli_command.arguments].join(" ");
}
