"use client";

import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { MempoolEntryResponse, MempoolSummaryResponse, fetchMempool, fetchMempoolEntry } from "@/lib/api";

export function MempoolExplorer() {
  const [summary, setSummary] = useState<MempoolSummaryResponse | null>(null);
  const [entry, setEntry] = useState<MempoolEntryResponse | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [entryError, setEntryError] = useState("");
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingEntry, setLoadingEntry] = useState(false);

  useEffect(() => {
    void loadSummary();
  }, []);

  async function loadSummary() {
    setLoadingSummary(true);
    setError("");
    try {
      setSummary(await fetchMempool());
    } catch (caught) {
      setSummary(null);
      setError(caught instanceof Error ? caught.message : "The mempool summary could not be loaded.");
    } finally {
      setLoadingSummary(false);
    }
  }

  async function loadEntry(txid: string) {
    setLoadingEntry(true);
    setEntryError("");
    try {
      setEntry(await fetchMempoolEntry(txid));
    } catch (caught) {
      setEntry(null);
      setEntryError(caught instanceof Error ? caught.message : "That transaction is not in the mempool.");
    } finally {
      setLoadingEntry(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setEntryError("Enter a mempool transaction id.");
      return;
    }
    await loadEntry(trimmed);
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Mempool laboratory</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Unconfirmed transactions</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Inspect your node&apos;s local mempool, fee policy, and individual unconfirmed entries.
        </p>
      </header>

      {loadingSummary ? (
        <WarningBox title="Loading mempool">
          <p>Asking Bitcoin Core for `getmempoolinfo` and `getrawmempool`.</p>
        </WarningBox>
      ) : null}

      {error ? (
        <WarningBox title="Mempool unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {summary ? (
        <>
          <Summary summary={summary} onSelectTxid={(txid) => { setQuery(txid); void loadEntry(txid); }} />

          <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="Mempool transaction id"
            />
            <button
              type="submit"
              disabled={loadingEntry}
              className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
            >
              {loadingEntry ? "Loading" : "Inspect entry"}
            </button>
          </form>

          {entryError ? (
            <WarningBox title="Entry unavailable">
              <p>{entryError}</p>
            </WarningBox>
          ) : null}

          {entry ? <Entry entry={entry} /> : null}
        </>
      ) : null}
    </div>
  );
}

function Summary({ summary, onSelectTxid }: { summary: MempoolSummaryResponse; onSelectTxid: (txid: string) => void }) {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Transactions" value={formatNullableNumber(summary.transaction_count)} detail="Unconfirmed txs known locally" />
        <StatusCard label="Virtual size" value={formatVbytes(summary.virtual_size)} detail="Approximate mempool vbytes" />
        <StatusCard label="Memory usage" value={formatBytes(summary.memory_usage)} detail="RAM used by mempool data" />
        <StatusCard label="Total fee" value={formatBtc(summary.total_fee_btc)} detail="Fees from current mempool txs" />
        <StatusCard label="Min mempool fee" value={formatBtcPerKvb(summary.mempool_min_fee)} detail="Eviction threshold" />
        <StatusCard label="Incremental relay" value={formatBtcPerKvb(summary.incremental_relay_fee)} detail="Replacement policy floor" />
        <StatusCard label="Max mempool" value={formatBytes(summary.max_mempool)} detail="Configured memory limit" />
        <StatusCard label="Samples" value={formatNullableNumber(summary.sample_transaction_ids.length)} detail="Clickable txids below" />
      </div>

      {summary.sample_transaction_ids.length ? (
        <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-ink">Sample transaction IDs</h2>
          <div className="mt-4 max-h-80 space-y-2 overflow-auto">
            {summary.sample_transaction_ids.map((txid) => (
              <button
                type="button"
                key={txid}
                onClick={() => onSelectTxid(txid)}
                className="block w-full break-all rounded-md bg-stone-100 px-3 py-2 text-left font-mono text-xs text-ink hover:bg-stone-200"
              >
                {txid}
              </button>
            ))}
          </div>
        </section>
      ) : (
        <WarningBox title="Empty mempool">
          <p>Your node currently has no unconfirmed transactions. This is normal on a quiet regtest node.</p>
        </WarningBox>
      )}

      <CommandExplanationCard
        title="Mempool summary"
        command={summary.cli_commands.join("\n")}
        rpcMethod={summary.rpc_methods.join(", ")}
        parameters="[]"
        explanation={summary.explanation}
        concepts={summary.concepts}
        rawJson={summary.raw}
      />
    </div>
  );
}

function Entry({ entry }: { entry: MempoolEntryResponse }) {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="vsize" value={formatVbytes(entry.vsize)} detail="Fee-rate relevant size" />
        <StatusCard label="Weight" value={formatNullableNumber(entry.weight)} detail="SegWit weight units" />
        <StatusCard label="Fee" value={formatBtc(entry.fee_btc)} detail="Base fee tracked by mempool" />
        <StatusCard label="Modified fee" value={formatBtc(entry.modified_fee_btc)} detail="After prioritization adjustments" />
        <StatusCard label="Ancestors" value={formatNullableNumber(entry.ancestor_count)} detail="Unconfirmed parents package" />
        <StatusCard label="Descendants" value={formatNullableNumber(entry.descendant_count)} detail="Unconfirmed children package" />
        <StatusCard label="BIP125" value={formatBoolean(entry.bip125_replaceable)} detail="Signals replace-by-fee" />
        <StatusCard label="Unbroadcast" value={formatBoolean(entry.unbroadcast)} detail="Known locally but not relayed" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Entry relationships</h2>
        <Field label="txid" value={entry.txid} />
        <Field label="Seen time" value={formatTimestamp(entry.time)} />
        <Field label="Mempool height" value={entry.height === null ? "unavailable" : String(entry.height)} />
        <Field label="Depends on" value={entry.depends.length ? entry.depends.join("\n") : "none"} />
        <Field label="Spent by" value={entry.spent_by.length ? entry.spent_by.join("\n") : "none"} />
      </section>

      <CommandExplanationCard
        title="Mempool entry"
        command={entry.cli_commands.join("\n")}
        rpcMethod={entry.rpc_methods.join(", ")}
        parameters={`["${entry.txid}"]`}
        explanation={entry.explanation}
        concepts={entry.concepts}
        rawJson={entry.raw}
      />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[9rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="whitespace-pre-wrap break-all font-mono text-stone-800">{value}</div>
    </div>
  );
}

function formatNullableNumber(value: number | null) {
  return value === null ? "unavailable" : new Intl.NumberFormat("en-US").format(value);
}

function formatVbytes(value: number | null) {
  return value === null ? "unavailable" : `${formatNullableNumber(value)} vB`;
}

function formatBytes(value: number | null) {
  if (value === null) {
    return "unavailable";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let scaled = value / 1024;
  let unitIndex = 0;
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024;
    unitIndex += 1;
  }
  return `${scaled.toFixed(1)} ${units[unitIndex]}`;
}

function formatBtc(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC`;
}

function formatBtcPerKvb(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC/kvB`;
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "unavailable";
  }
  return value ? "yes" : "no";
}

function formatTimestamp(value: number | null) {
  return value === null ? "unavailable" : new Date(value * 1000).toISOString();
}
