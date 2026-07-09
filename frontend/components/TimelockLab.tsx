"use client";

import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  LocktimeTransactionResponse,
  TimelockScriptResponse,
  createLocktimeTransaction,
  createTimelockScriptTemplate
} from "@/lib/api";
import { useLabContext } from "@/lib/labContext";

const SAMPLE_PUBKEY = "02aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

export function TimelockLab() {
  const { context } = useLabContext();
  const [walletName, setWalletName] = useState(context.walletName);
  const [destinationAddress, setDestinationAddress] = useState(context.lastAddress);
  const [amountBtc, setAmountBtc] = useState(0.01);
  const [locktime, setLocktime] = useState(500);
  const [sequence, setSequence] = useState(1);
  const [mode, setMode] = useState("cltv");
  const [scriptValue, setScriptValue] = useState(500);
  const [pubkeyHex, setPubkeyHex] = useState(SAMPLE_PUBKEY);
  const [transaction, setTransaction] = useState<LocktimeTransactionResponse | null>(null);
  const [script, setScript] = useState<TimelockScriptResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<"transaction" | "script" | null>(null);

  useEffect(() => {
    if (context.walletName) {
      setWalletName((current) => current || context.walletName);
    }
    if (context.lastAddress) {
      setDestinationAddress((current) => current || context.lastAddress);
    }
  }, [context.walletName, context.lastAddress]);

  async function run(modeName: "transaction" | "script", action: () => Promise<void>) {
    setLoading(modeName);
    setError("");
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Timelock action failed.");
    } finally {
      setLoading(null);
    }
  }

  async function submitTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("transaction", async () => {
      setTransaction(await createLocktimeTransaction(walletName.trim(), destinationAddress.trim(), amountBtc, locktime, sequence));
    });
  }

  async function submitScript(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("script", async () => {
      setScript(await createTimelockScriptTemplate(mode, scriptValue, pubkeyHex.trim()));
    });
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Timelock laboratory</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Explore locktime, CLTV, CSV, and sequence</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Build a regtest transaction with explicit nLockTime and sequence values, then generate CLTV or CSV script templates for opcode-level inspection.
        </p>
      </header>

      <WarningBox title="Consensus and policy meet here">
        <p>Transaction locktime only matters when at least one input sequence is non-final. CLTV is an absolute script lock; CSV is relative and depends on input sequence age.</p>
      </WarningBox>

      {error ? (
        <WarningBox title="Timelock action unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <form onSubmit={submitTransaction} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div>
            <p className="text-sm font-semibold uppercase text-forest">Transaction locktime</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Build and test a non-final transaction</h2>
          </div>
          <TextField label="Wallet name" value={walletName} onChange={setWalletName} placeholder="Loaded regtest wallet" />
          <TextField label="Destination address" value={destinationAddress} onChange={setDestinationAddress} placeholder="bcrt1..." />
          <div className="grid gap-3 sm:grid-cols-3">
            <NumberField label="Amount BTC" value={amountBtc} onChange={setAmountBtc} min={0.00000001} step={0.00000001} />
            <NumberField label="Locktime" value={locktime} onChange={setLocktime} min={0} step={1} />
            <NumberField label="Sequence" value={sequence} onChange={setSequence} min={0} max={4294967295} step={1} />
          </div>
          <button type="submit" disabled={loading !== null} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading === "transaction" ? "Testing" : "Create and test"}
          </button>
        </form>

        <form onSubmit={submitScript} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div>
            <p className="text-sm font-semibold uppercase text-forest">Script locks</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Generate CLTV or CSV script</h2>
          </div>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest">
              <option value="cltv">CLTV absolute</option>
              <option value="csv">CSV relative</option>
            </select>
          </label>
          <NumberField label="Timelock value" value={scriptValue} onChange={setScriptValue} min={0} step={1} />
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Public key hex
            <textarea value={pubkeyHex} onChange={(event) => setPubkeyHex(event.target.value)} className="min-h-24 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-xs text-ink outline-none focus:border-forest" spellCheck={false} />
          </label>
          <button type="submit" disabled={loading !== null} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading === "script" ? "Generating" : "Generate script"}
          </button>
        </form>
      </section>

      {transaction ? <TransactionResult result={transaction} /> : null}
      {script ? <ScriptResult result={script} /> : null}
    </div>
  );
}

function TransactionResult({ result }: { result: LocktimeTransactionResponse }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Locktime" value={String(result.locktime)} detail="Transaction-level nLockTime" />
        <StatusCard label="Sequence" value={String(result.sequence)} detail="Input finality value" />
        <StatusCard label="Complete" value={result.complete ? "yes" : "no"} detail="Wallet signing result" />
        <StatusCard label="Fee" value={result.fee_btc === null ? "unknown" : `${result.fee_btc.toFixed(8)} BTC`} detail="Funding fee" />
      </section>
      <Artifact title="Signed transaction hex" value={result.signed_hex ?? result.sequence_hex} />
      <Artifact title="testmempoolaccept" value={JSON.stringify(result.mempool_accept, null, 2)} />
      <CommandExplanationCard title="Locktime transaction" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`locktime=${result.locktime}, sequence=${result.sequence}`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
    </div>
  );
}

function ScriptResult({ result }: { result: TimelockScriptResponse }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Mode" value={result.mode.toUpperCase()} detail="Script timelock opcode" />
        <StatusCard label="Value" value={String(result.value)} detail="Height, time, or relative age" />
        <StatusCard label="P2SH" value={result.p2sh ?? "unavailable"} detail="Nested address when available" />
        <StatusCard label="ASM" value={result.asm ?? "unavailable"} detail="Bitcoin Core decode" />
      </section>
      <Artifact title="Script hex" value={result.script_hex} />
      <CommandExplanationCard title="Timelock script template" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`${result.mode}:${result.value}`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
    </div>
  );
}

function TextField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" />
    </label>
  );
}

function NumberField({ label, value, onChange, min, max, step }: { label: string; value: number; onChange: (value: number) => void; min: number; max?: number; step: number }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest" />
    </label>
  );
}

function Artifact({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100">
        <code>{value}</code>
      </pre>
    </section>
  );
}
