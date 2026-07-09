"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { AddressIndexScanResponse, IndexedAddressOutput, scanAddressIndex } from "@/lib/api";

export function LocalIndexer() {
  const [address, setAddress] = useState("");
  const [startHeight, setStartHeight] = useState(0);
  const [endHeight, setEndHeight] = useState(0);
  const [result, setResult] = useState<AddressIndexScanResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!address.trim()) {
      setError("Enter an address to scan for.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setResult(await scanAddressIndex(address.trim(), startHeight, endHeight));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Address index scan could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Local indexing experiment</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Scan blocks for address outputs</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Walk a small height range from your node, decode block transactions, and collect outputs that pay a target address.
        </p>
      </header>

      <WarningBox title="Bounded experiment">
        <p>This is not a full address index. It scans at most 50 blocks and reports matching outputs, not complete spend history or current balance.</p>
      </WarningBox>

      <form onSubmit={submit} className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_10rem_10rem]">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Address
            <input
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="Address matching your configured network"
            />
          </label>
          <NumberField label="Start height" value={startHeight} onChange={setStartHeight} />
          <NumberField label="End height" value={endHeight} onChange={setEndHeight} />
        </div>
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading ? "Scanning" : "Scan range"}
          </button>
        </div>
      </form>

      {error ? (
        <WarningBox title="Index scan unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {result ? <IndexScanResult result={result} /> : <EmptyState />}
    </div>
  );
}

function IndexScanResult({ result }: { result: AddressIndexScanResponse }) {
  return (
    <div className="space-y-6">
      <WarningBox title="Scan limitation">
        <p>{result.limitation}</p>
      </WarningBox>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Blocks scanned" value={String(result.blocks_scanned)} detail={`${result.start_height} to ${result.end_height}`} />
        <StatusCard label="Matches" value={String(result.outputs.length)} detail="Outputs paying address" />
        <StatusCard label="Received in range" value={`${result.total_received_btc_in_range.toFixed(8)} BTC`} detail="Output sum, not balance" />
        <StatusCard label="Address" value={result.address} detail="Target scriptPubKey address" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Matching outputs</h2>
        <div className="mt-4 space-y-3">
          {result.outputs.length ? result.outputs.map((output) => <IndexedOutputCard key={`${output.txid}:${output.vout}`} output={output} />) : (
            <p className="text-sm leading-6 text-stone-600">No matching outputs were found in this height range.</p>
          )}
        </div>
      </section>

      <CommandExplanationCard
        title="Local address output scan"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify({ address: result.address, start_height: result.start_height, end_height: result.end_height }, null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function IndexedOutputCard({ output }: { output: IndexedAddressOutput }) {
  return (
    <article className="rounded-md border border-stone-200 bg-white p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <Link href={`/transactions?txid=${output.txid}`} className="break-all font-mono text-sm font-semibold text-forest hover:text-ink">
          {output.txid}:{output.vout}
        </Link>
        <div className="rounded-md bg-stone-100 px-2 py-1 text-sm font-semibold text-forest">{output.value_btc.toFixed(8)} BTC</div>
      </div>
      <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
        <MiniField label="Block" value={String(output.block_height)} />
        <MiniField label="Type" value={output.script_type ?? "unknown"} />
        <MiniField label="Block hash" value={output.block_hash} />
      </div>
      {output.script_pub_key_hex ? <MiniField label="scriptPubKey" value={output.script_pub_key_hex} /> : null}
    </article>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input
        type="number"
        min={0}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
      />
    </label>
  );
}

function MiniField({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-medium uppercase text-stone-500">{label}</div>
      <div className="mt-1 break-all font-mono text-stone-800">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Try a recent regtest range">
      <p>Generate or find a wallet address, mine or send to it, then scan the small height range where that output should appear.</p>
    </WarningBox>
  );
}
