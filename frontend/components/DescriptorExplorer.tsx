"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  DescriptorAnalyzeResponse,
  WalletDescriptorInfo,
  WalletDescriptorsResponse,
  analyzeDescriptor,
  fetchWalletDescriptors
} from "@/lib/api";

const SAMPLE_DESCRIPTOR = "raw(51)";

export function DescriptorExplorer() {
  const [mode, setMode] = useState<"analyze" | "wallet">("analyze");
  const [descriptor, setDescriptor] = useState(SAMPLE_DESCRIPTOR);
  const [deriveStart, setDeriveStart] = useState(0);
  const [deriveEnd, setDeriveEnd] = useState(2);
  const [derive, setDerive] = useState(false);
  const [walletName, setWalletName] = useState("");
  const [analysis, setAnalysis] = useState<DescriptorAnalyzeResponse | null>(null);
  const [walletDescriptors, setWalletDescriptors] = useState<WalletDescriptorsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!descriptor.trim()) {
      setError("Paste a descriptor.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setAnalysis(await analyzeDescriptor(descriptor.trim(), derive ? deriveStart : null, derive ? deriveEnd : null));
    } catch (caught) {
      setAnalysis(null);
      setError(caught instanceof Error ? caught.message : "Descriptor could not be analyzed.");
    } finally {
      setLoading(false);
    }
  }

  async function submitWallet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!walletName.trim()) {
      setError("Enter a loaded wallet name.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setWalletDescriptors(await fetchWalletDescriptors(walletName.trim()));
    } catch (caught) {
      setWalletDescriptors(null);
      setError(caught instanceof Error ? caught.message : "Wallet descriptors could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Descriptor explorer</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect wallet descriptors</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Normalize descriptors, verify checksums, derive sample addresses, and inspect public wallet descriptor sets.
        </p>
      </header>

      <WarningBox title="Public descriptor view">
        <p>Wallet descriptor listing requests public descriptors only. Private keys are not returned to the browser.</p>
      </WarningBox>

      <div className="flex flex-wrap gap-2">
        <ModeButton active={mode === "analyze"} onClick={() => setMode("analyze")}>Analyze descriptor</ModeButton>
        <ModeButton active={mode === "wallet"} onClick={() => setMode("wallet")}>Wallet descriptors</ModeButton>
      </div>

      {mode === "analyze" ? (
        <form onSubmit={submitAnalyze} className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Descriptor
            <textarea
              value={descriptor}
              onChange={(event) => setDescriptor(event.target.value)}
              className="min-h-32 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              spellCheck={false}
            />
          </label>
          <div className="mt-4 grid gap-3 md:grid-cols-[auto_1fr_1fr] md:items-end">
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input type="checkbox" checked={derive} onChange={(event) => setDerive(event.target.checked)} className="h-4 w-4 accent-forest" />
              Derive range
            </label>
            <NumberField label="Start" value={deriveStart} onChange={setDeriveStart} disabled={!derive} />
            <NumberField label="End" value={deriveEnd} onChange={setDeriveEnd} disabled={!derive} />
          </div>
          <div className="mt-4 flex justify-end">
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              {loading ? "Analyzing" : "Analyze descriptor"}
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={submitWallet} className="flex flex-col gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:flex-row sm:p-5">
          <input
            value={walletName}
            onChange={(event) => setWalletName(event.target.value)}
            className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            placeholder="Loaded wallet name"
          />
          <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading ? "Loading" : "Load descriptors"}
          </button>
        </form>
      )}

      {error ? (
        <WarningBox title="Descriptor unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {mode === "analyze" && analysis ? <DescriptorAnalysis result={analysis} /> : null}
      {mode === "wallet" && walletDescriptors ? <WalletDescriptorResult result={walletDescriptors} /> : null}
      {!analysis && !walletDescriptors ? <EmptyState /> : null}
    </div>
  );
}

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-sm font-semibold ${active ? "border-forest bg-forest text-white" : "border-stone-300 bg-white text-ink hover:bg-stone-50"}`}
    >
      {children}
    </button>
  );
}

function DescriptorAnalysis({ result }: { result: DescriptorAnalyzeResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Checksum" value={result.checksum ?? "unavailable"} detail="Descriptor checksum" />
        <StatusCard label="Ranged" value={formatBoolean(result.is_range)} detail="Uses wildcard derivation" />
        <StatusCard label="Solvable" value={formatBoolean(result.is_solvable)} detail="Core can solve script template" />
        <StatusCard label="Private keys" value={formatBoolean(result.has_private_keys)} detail="Should usually be no in UI flows" />
      </div>
      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Descriptor details</h2>
        <Field label="Input" value={result.descriptor} />
        <Field label="Normalized" value={result.normalized_descriptor ?? "unavailable"} />
        {result.derived_addresses.length ? <AddressList addresses={result.derived_addresses} /> : null}
      </section>
      <CommandExplanationCard
        title="Descriptor analysis"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify([result.descriptor], null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function WalletDescriptorResult({ result }: { result: WalletDescriptorsResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard label="Wallet" value={result.wallet_name} detail="Wallet RPC context" />
        <StatusCard label="Descriptors" value={String(result.descriptors.length)} detail="Public descriptor entries" />
        <StatusCard label="Active" value={String(result.descriptors.filter((item) => item.active).length)} detail="Current receive/change pools" />
      </div>
      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Wallet descriptors</h2>
        <div className="mt-4 space-y-3">
          {result.descriptors.map((descriptor, index) => (
            <WalletDescriptorCard key={`${descriptor.descriptor}-${index}`} descriptor={descriptor} />
          ))}
        </div>
      </section>
      <CommandExplanationCard
        title="Wallet descriptor listing"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters="[false]"
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function WalletDescriptorCard({ descriptor }: { descriptor: WalletDescriptorInfo }) {
  return (
    <article className="rounded-md border border-stone-200 bg-white p-3">
      <div className="break-all font-mono text-xs leading-5 text-ink">{descriptor.descriptor}</div>
      <div className="mt-3 grid gap-3 text-sm md:grid-cols-5">
        <MiniField label="Active" value={formatBoolean(descriptor.active)} />
        <MiniField label="Internal" value={formatBoolean(descriptor.internal)} />
        <MiniField label="Range" value={descriptor.range ? descriptor.range.join(" to ") : "none"} />
        <MiniField label="Next" value={descriptor.next_index === null ? "unknown" : String(descriptor.next_index)} />
        <MiniField label="Timestamp" value={descriptor.timestamp === null ? "unknown" : String(descriptor.timestamp)} />
      </div>
    </article>
  );
}

function NumberField({ label, value, disabled, onChange }: { label: string; value: number; disabled: boolean; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-stone-600">
      {label}
      <input
        type="number"
        min={0}
        max={1000000}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest disabled:bg-stone-100"
      />
    </label>
  );
}

function AddressList({ addresses }: { addresses: string[] }) {
  return (
    <div className="mt-4">
      <h3 className="text-sm font-semibold uppercase text-stone-500">Derived addresses</h3>
      <div className="mt-2 space-y-2">
        {addresses.map((address) => (
          <a key={address} href={`/address?address=${encodeURIComponent(address)}`} className="block break-all rounded-md bg-stone-100 px-3 py-2 font-mono text-xs text-forest hover:bg-stone-200 hover:text-ink">
            {address}
          </a>
        ))}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[10rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-stone-800">{value}</div>
    </div>
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
    <WarningBox title="Start with a descriptor">
      <p>Analyze a descriptor such as `raw(51)`, or load public descriptors from a descriptor wallet.</p>
    </WarningBox>
  );
}

function formatBoolean(value: boolean | null) {
  if (value === null) return "unknown";
  return value ? "yes" : "no";
}
