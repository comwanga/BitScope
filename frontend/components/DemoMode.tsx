"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { DemoRunResponse, DemoStep, runDemoMode } from "@/lib/api";
import { useLabContext } from "@/lib/labContext";

export function DemoMode() {
  const { setContext } = useLabContext();
  const [walletName, setWalletName] = useState("bitscope-demo");
  const [freshWallet, setFreshWallet] = useState(true);
  const [mineBlocks, setMineBlocks] = useState(101);
  const [sendAmount, setSendAmount] = useState(1);
  const [includeScriptSample, setIncludeScriptSample] = useState(true);
  const [result, setResult] = useState<DemoRunResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setCopied(false);
    try {
      const demo = await runDemoMode(walletName.trim(), freshWallet, mineBlocks, sendAmount, includeScriptSample);
      setResult(demo);
      setContext({
        walletName: demo.wallet_name,
        lastAddress: demo.recipient_address
      });
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Demo Mode could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  async function copyLog() {
    if (!result) return;
    await navigator.clipboard.writeText(result.export_markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  function downloadLog() {
    if (!result) return;
    const blob = new Blob([result.export_markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `bitscope-demo-${result.session_id}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Demo mode</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Run a guided regtest session</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Create a clean wallet, mine mature coins, send a transaction, decode script, and export the command trail.
        </p>
      </header>

      <WarningBox title="Regtest boundary">
        <p>Demo Mode is blocked unless the backend is configured with `BITCOIN_NETWORK=regtest`.</p>
      </WarningBox>

      {error ? (
        <WarningBox title="Demo unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <form onSubmit={submit} className="grid gap-4 xl:grid-cols-[minmax(18rem,1fr)_minmax(8rem,10rem)_minmax(9rem,12rem)]">
          <label className="min-w-0 grid gap-2 text-sm font-medium text-stone-600">
            Wallet prefix
            <input
              value={walletName}
              onChange={(event) => setWalletName(event.target.value)}
              className="w-full min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            />
          </label>
          <label className="min-w-0 grid gap-2 text-sm font-medium text-stone-600">
            Blocks
            <input
              type="number"
              min={101}
              max={500}
              value={mineBlocks}
              onChange={(event) => setMineBlocks(Number(event.target.value))}
              className="w-full min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
            />
          </label>
          <label className="min-w-0 grid gap-2 text-sm font-medium text-stone-600">
            Send BTC
            <input
              type="number"
              min={0.00000001}
              step={0.00000001}
              value={sendAmount}
              onChange={(event) => setSendAmount(Number(event.target.value))}
              className="w-full min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
            />
          </label>
          <div className="flex min-w-0 flex-col gap-3 xl:col-span-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
                <input type="checkbox" checked={freshWallet} onChange={(event) => setFreshWallet(event.target.checked)} className="h-4 w-4 accent-forest" />
                Fresh timestamped wallet
              </label>
              <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
                <input
                  type="checkbox"
                  checked={includeScriptSample}
                  onChange={(event) => setIncludeScriptSample(event.target.checked)}
                  className="h-4 w-4 accent-forest"
                />
                Include script decode
              </label>
            </div>
            <button type="submit" disabled={loading} className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70 sm:w-auto">
              {loading ? "Running demo" : "Run Demo Mode"}
            </button>
          </div>
        </form>
      </section>

      {result ? <DemoResult result={result} copied={copied} onCopy={copyLog} onDownload={downloadLog} /> : <DemoPreview />}
    </div>
  );
}

function DemoResult({
  result,
  copied,
  onCopy,
  onDownload
}: {
  result: DemoRunResponse;
  copied: boolean;
  onCopy: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Session" value={result.session_id} detail="Exportable teaching log" />
        <StatusCard label="Wallet" value={result.wallet_name} detail="Persisted for later labs" />
        <StatusCard label="Blocks" value={String(result.block_hashes.length)} detail="Maturity priming" />
        <StatusCard label="Transaction" value={result.txid ?? "not sent"} detail="Confirmed regtest send" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">Session links</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600">{result.explanation}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onCopy} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50">
              {copied ? "Copied" : "Copy log"}
            </button>
            <button type="button" onClick={onDownload} className="rounded-md bg-forest px-3 py-2 text-sm font-semibold text-white hover:bg-ink">
              Export log
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {result.txid ? <DeepLink href={`/transactions?txid=${result.txid}`} label="Inspect transaction" value={result.txid} /> : null}
          {result.block_hashes.at(-1) ? <DeepLink href={`/blocks/${result.block_hashes.at(-1)}`} label="Open latest block" value={result.block_hashes.at(-1) ?? ""} /> : null}
          <DeepLink href="/wallet" label="Continue in wallet lab" value={result.wallet_name} />
        </div>
      </section>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Guided sequence</h2>
        <div className="mt-4 grid gap-3">
          {result.steps.map((step, index) => (
            <DemoStepCard key={step.id} step={step} index={index} />
          ))}
        </div>
      </section>

      <CommandExplanationCard
        title="Demo Mode command trail"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify({ wallet_name: result.wallet_name, session_id: result.session_id }, null, 2)}
        explanation="This is the terminal-equivalent trail for the guided demo session."
        concepts={result.concepts}
        rawJson={{ steps: result.steps }}
      />
    </div>
  );
}

function DemoStepCard({ step, index }: { step: DemoStep; index: number }) {
  return (
    <article className="rounded-md border border-stone-200 bg-white p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase text-forest">Step {index + 1}</div>
          <h3 className="mt-1 text-base font-semibold text-ink">{step.title}</h3>
        </div>
        <span className="w-fit rounded-md bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-700">{step.status}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-stone-600">{step.summary}</p>
      <pre className="mt-3 overflow-x-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100">
        <code>{step.cli_commands.join("\n")}</code>
      </pre>
    </article>
  );
}

function DeepLink({ href, label, value }: { href: string; label: string; value: string }) {
  return (
    <Link href={href} className="min-w-0 rounded-md border border-stone-300 bg-white p-3 text-sm hover:bg-stone-50">
      <span className="block font-semibold text-ink">{label}</span>
      <span className="mt-2 block break-all font-mono text-xs text-forest">{value}</span>
    </Link>
  );
}

function DemoPreview() {
  const steps = ["Create/load wallet", "Mine 101 blocks", "Inspect balance", "Send transaction", "Decode script", "Export log"];
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Demo sequence</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {steps.map((step, index) => (
          <div key={step} className="rounded-md border border-stone-200 bg-white p-3">
            <div className="text-xs font-semibold uppercase text-forest">Step {index + 1}</div>
            <div className="mt-1 text-sm font-semibold text-ink">{step}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
