"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { RegtestFaucetResponse, RegtestMineResponse, mineRegtestBlocks, sendRegtestFaucet } from "@/lib/api";
import { useLabContext } from "@/lib/labContext";

export function RegtestLab() {
  const { context, setContext } = useLabContext();
  const [mineBlocks, setMineBlocks] = useState(101);
  const [mineWallet, setMineWallet] = useState(context.walletName);
  const [mineAddress, setMineAddress] = useState("");
  const [faucetWallet, setFaucetWallet] = useState(context.walletName);
  const [faucetAddress, setFaucetAddress] = useState(context.lastAddress);
  const [faucetAmount, setFaucetAmount] = useState(1);
  const [mineConfirmation, setMineConfirmation] = useState(true);
  const [mineResult, setMineResult] = useState<RegtestMineResponse | null>(null);
  const [faucetResult, setFaucetResult] = useState<RegtestFaucetResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (context.walletName) {
      setMineWallet((current) => current || context.walletName);
      setFaucetWallet((current) => current || context.walletName);
    }
    if (context.lastAddress) {
      setFaucetAddress((current) => current || context.lastAddress);
    }
  }, [context.walletName, context.lastAddress]);

  async function submitMine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mineWallet.trim() && !mineAddress.trim()) {
      setError("Provide a wallet name or a mining address.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await mineRegtestBlocks(mineBlocks, mineWallet.trim(), mineAddress.trim());
      setMineResult(result);
      setContext({ walletName: result.wallet_name ?? mineWallet.trim(), lastAddress: result.address });
    } catch (caught) {
      setMineResult(null);
      setError(caught instanceof Error ? caught.message : "Regtest blocks could not be mined.");
    } finally {
      setLoading(false);
    }
  }

  async function submitFaucet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!faucetWallet.trim() || !faucetAddress.trim()) {
      setError("Provide a sending wallet and destination address.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await sendRegtestFaucet(faucetWallet.trim(), faucetAddress.trim(), faucetAmount, mineConfirmation);
      setFaucetResult(result);
      setContext({ walletName: result.wallet_name, lastAddress: result.address });
    } catch (caught) {
      setFaucetResult(null);
      setError(caught instanceof Error ? caught.message : "Regtest faucet transaction could not be sent.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Regtest automation</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Mine and fund local workflows</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Create blocks on demand and send wallet-funded regtest transactions without leaving the browser.
        </p>
      </header>

      <WarningBox title="Regtest only">
        <p>These actions are blocked unless the backend is configured with `BITCOIN_NETWORK=regtest`.</p>
      </WarningBox>

      {error ? (
        <WarningBox title="Regtest action unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Mine blocks</h2>
          <form onSubmit={submitMine} className="mt-4 grid gap-3">
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Blocks
              <input
                type="number"
                min={1}
                max={500}
                value={mineBlocks}
                onChange={(event) => setMineBlocks(Number(event.target.value))}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Wallet name
              <input
                value={mineWallet}
                onChange={(event) => setMineWallet(event.target.value)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                placeholder="Generate a mining address from this wallet"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Address
              <input
                value={mineAddress}
                onChange={(event) => setMineAddress(event.target.value)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                placeholder="Optional if wallet name is provided"
              />
            </label>
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              Mine blocks
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Send faucet coins</h2>
          <form onSubmit={submitFaucet} className="mt-4 grid gap-3">
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Sending wallet
              <input
                value={faucetWallet}
                onChange={(event) => setFaucetWallet(event.target.value)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                placeholder="Loaded wallet with spendable funds"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Destination address
              <input
                value={faucetAddress}
                onChange={(event) => setFaucetAddress(event.target.value)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                placeholder="Regtest address"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Amount BTC
              <input
                type="number"
                min={0.00000001}
                step={0.00000001}
                value={faucetAmount}
                onChange={(event) => setFaucetAmount(Number(event.target.value))}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
              />
            </label>
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input
                type="checkbox"
                checked={mineConfirmation}
                onChange={(event) => setMineConfirmation(event.target.checked)}
                className="h-4 w-4 accent-forest"
              />
              Mine one confirmation block
            </label>
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              Send faucet transaction
            </button>
          </form>
        </section>
      </div>

      {mineResult ? <MineResult result={mineResult} /> : null}
      {faucetResult ? <FaucetResult result={faucetResult} /> : null}
    </div>
  );
}

function MineResult({ result }: { result: RegtestMineResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Blocks mined" value={String(result.blocks)} detail="New regtest blocks" />
        <StatusCard label="Reward address" value={result.address} detail={result.wallet_name ?? "Provided address"} />
        <StatusCard label="First block" value={result.block_hashes[0] ?? "unavailable"} detail="Open from block explorer" />
        <StatusCard label="Last block" value={result.block_hashes.at(-1) ?? "unavailable"} detail="New chain tip if no competing blocks" />
      </div>
      <HashList title="Mined block hashes" hashes={result.block_hashes} hrefPrefix="/blocks/" />
      <CommandExplanationCard
        title="Regtest mining"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={`[${result.blocks}, "${result.address}"]`}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function FaucetResult({ result }: { result: RegtestFaucetResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Amount" value={`${result.amount_btc.toFixed(8)} BTC`} detail="Sent by wallet" />
        <StatusCard label="Sending wallet" value={result.wallet_name} detail="Wallet RPC context" />
        <StatusCard label="Transaction" value={result.txid} detail="Open from transaction explorer" />
        <StatusCard label="Confirmations mined" value={String(result.confirmation_block_hashes.length)} detail="Optional faucet confirmation" />
      </div>
      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Faucet transaction</h2>
        <Link href={`/transactions?txid=${result.txid}`} className="mt-3 block break-all font-mono text-sm font-semibold text-forest hover:text-ink">
          {result.txid}
        </Link>
        <div className="mt-3 break-all font-mono text-sm text-stone-700">{result.address}</div>
      </section>
      {result.confirmation_block_hashes.length ? <HashList title="Confirmation block" hashes={result.confirmation_block_hashes} hrefPrefix="/blocks/" /> : null}
      <CommandExplanationCard
        title="Regtest faucet"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={`["${result.address}", ${result.amount_btc}]`}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function HashList({ title, hashes, hrefPrefix }: { title: string; hashes: string[]; hrefPrefix: string }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-4 max-h-80 space-y-2 overflow-auto">
        {hashes.map((hash) => (
          <Link key={hash} href={`${hrefPrefix}${hash}`} className="block break-all rounded-md bg-stone-100 px-3 py-2 font-mono text-xs text-forest hover:bg-stone-200 hover:text-ink">
            {hash}
          </Link>
        ))}
      </div>
    </section>
  );
}
