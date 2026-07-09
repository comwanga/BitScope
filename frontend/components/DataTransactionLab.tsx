"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { OpReturnTransactionResponse, createOpReturnTransaction } from "@/lib/api";
import { useLabContext } from "@/lib/labContext";

export function DataTransactionLab() {
  const { context, setContext } = useLabContext();
  const [walletName, setWalletName] = useState(context.walletName);
  const [dataFormat, setDataFormat] = useState("text");
  const [data, setData] = useState("BitScope lab");
  const [destinationAddress, setDestinationAddress] = useState(context.lastAddress);
  const [includePayment, setIncludePayment] = useState(false);
  const [amountBtc, setAmountBtc] = useState(0.001);
  const [broadcast, setBroadcast] = useState(false);
  const [mineConfirmation, setMineConfirmation] = useState(false);
  const [result, setResult] = useState<OpReturnTransactionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (context.walletName) {
      setWalletName((current) => current || context.walletName);
    }
    if (context.lastAddress) {
      setDestinationAddress((current) => current || context.lastAddress);
    }
  }, [context.walletName, context.lastAddress]);

  const byteCount = useMemo(() => estimateBytes(data, dataFormat), [data, dataFormat]);
  const bytesRemaining = byteCount === null ? null : 80 - byteCount;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!walletName.trim()) {
      setError("Provide a loaded regtest wallet.");
      return;
    }
    if (includePayment && !destinationAddress.trim()) {
      setError("Provide a destination address or turn off the payment output.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await createOpReturnTransaction(
        walletName.trim(),
        data.trim(),
        dataFormat,
        includePayment ? destinationAddress.trim() : "",
        includePayment ? amountBtc : null,
        broadcast,
        mineConfirmation
      );
      setResult(response);
      setContext({ walletName: response.wallet_name, lastAddress: response.destination_address ?? context.lastAddress });
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "OP_RETURN transaction could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Data transaction lab</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Build OP_RETURN transactions</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Commit small data payloads with a nulldata output, inspect the raw transaction, and test node policy before optional regtest broadcast.
        </p>
      </header>

      <WarningBox title="Use OP_RETURN sparingly">
        <p>
          OP_RETURN outputs are provably unspendable and do not add to the UTXO set, but block space is still scarce. BitScope limits
          payloads to 80 bytes and keeps this builder regtest-only.
        </p>
      </WarningBox>

      {error ? (
        <WarningBox title="Data transaction unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <form onSubmit={submit} className="space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_14rem]">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Wallet name
            <input
              value={walletName}
              onChange={(event) => setWalletName(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="Loaded regtest wallet"
            />
          </label>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Data format
            <select
              value={dataFormat}
              onChange={(event) => setDataFormat(event.target.value)}
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
            >
              <option value="text">UTF-8 text</option>
              <option value="hex">Hex bytes</option>
            </select>
          </label>
        </div>

        <label className="grid gap-2 text-sm font-medium text-stone-600">
          OP_RETURN payload
          <textarea
            value={data}
            onChange={(event) => setData(event.target.value)}
            className="min-h-32 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            spellCheck={false}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <span className="rounded-md bg-stone-100 px-3 py-1 text-sm font-medium text-stone-700">
            {byteCount === null ? "Invalid hex" : `${byteCount} / 80 bytes`}
          </span>
          {bytesRemaining === null ? null : (
            <span className={`rounded-md px-3 py-1 text-sm font-medium ${bytesRemaining < 0 ? "bg-red-100 text-red-700" : "bg-stone-100 text-stone-700"}`}>
              {bytesRemaining < 0 ? `${Math.abs(bytesRemaining)} bytes over limit` : `${bytesRemaining} bytes remaining`}
            </span>
          )}
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_12rem]">
          <label className="flex items-center gap-2 text-sm font-medium text-stone-600 lg:col-span-2">
            <input type="checkbox" checked={includePayment} onChange={(event) => setIncludePayment(event.target.checked)} className="h-4 w-4 accent-forest" />
            Add a normal payment output alongside the OP_RETURN output
          </label>
          {includePayment ? (
            <>
              <label className="grid gap-2 text-sm font-medium text-stone-600">
                Destination address
                <input
                  value={destinationAddress}
                  onChange={(event) => setDestinationAddress(event.target.value)}
                  className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                  placeholder="bcrt1..."
                />
              </label>
              <label className="grid gap-2 text-sm font-medium text-stone-600">
                Amount BTC
                <input
                  type="number"
                  min={0.00000001}
                  step={0.00000001}
                  value={amountBtc}
                  onChange={(event) => setAmountBtc(Number(event.target.value))}
                  className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
                />
              </label>
            </>
          ) : null}
        </div>

        <div className="flex flex-col gap-3 border-t border-stone-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="grid gap-2">
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input type="checkbox" checked={broadcast} onChange={(event) => setBroadcast(event.target.checked)} className="h-4 w-4 accent-forest" />
              Broadcast on regtest
            </label>
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input
                type="checkbox"
                checked={mineConfirmation}
                onChange={(event) => setMineConfirmation(event.target.checked)}
                disabled={!broadcast}
                className="h-4 w-4 accent-forest disabled:opacity-50"
              />
              Mine one confirmation after broadcast
            </label>
          </div>
          <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading ? "Building" : broadcast ? "Build and broadcast" : "Build and test"}
          </button>
        </div>
      </form>

      {result ? <DataTransactionResult result={result} /> : <EmptyState />}
    </div>
  );
}

function DataTransactionResult({ result }: { result: OpReturnTransactionResponse }) {
  const accepted = extractMempoolAllowed(result.mempool_accept);
  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Payload" value={`${result.data_bytes} bytes`} detail="OP_RETURN data size" />
        <StatusCard label="Signed" value={result.complete ? "complete" : "incomplete"} detail="Wallet signing result" />
        <StatusCard label="Policy" value={accepted === null ? "unknown" : accepted ? "accepted" : "rejected"} detail="testmempoolaccept result" />
        <StatusCard label="Fee" value={result.fee_btc === null ? "unknown" : `${result.fee_btc.toFixed(8)} BTC`} detail="Wallet funding fee" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">OP_RETURN output</h2>
        <Field label="Data hex" value={result.data_hex} />
        <Field label="Script hex" value={result.op_return_script_hex} />
        <Field label="Destination" value={result.destination_address ?? "no payment output"} />
        <Field label="Broadcast" value={result.broadcast ? "yes" : "no"} />
        {result.txid ? (
          <Link href={`/transactions?txid=${result.txid}`} className="mt-4 inline-block break-all rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-xs font-semibold text-forest hover:bg-stone-50 hover:text-ink">
            {result.txid}
          </Link>
        ) : null}
      </section>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Transaction artifacts</h2>
        <Field label="Unsigned hex" value={result.unsigned_hex} />
        <Field label="Funded hex" value={result.funded_hex} />
        <Field label="Signed hex" value={result.signed_hex ?? "not available"} />
      </section>

      <CommandExplanationCard
        title="OP_RETURN transaction"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify({ data: result.data_hex, destination: result.destination_address, amount_btc: result.amount_btc }, null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[9rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-xs leading-5 text-stone-800 sm:text-sm">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Build a data transaction">
      <p>Start with build and test mode. Broadcast only after reviewing the generated OP_RETURN script, fee, and policy result.</p>
    </WarningBox>
  );
}

function estimateBytes(value: string, dataFormat: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return 0;
  }
  if (dataFormat === "hex") {
    if (trimmed.length % 2 !== 0 || /[^0-9a-fA-F]/.test(trimmed)) {
      return null;
    }
    return trimmed.length / 2;
  }
  return new TextEncoder().encode(trimmed).length;
}

function extractMempoolAllowed(value: unknown): boolean | null {
  if (!Array.isArray(value) || !value.length || typeof value[0] !== "object" || value[0] === null) {
    return null;
  }
  const allowed = (value[0] as { allowed?: unknown }).allowed;
  return typeof allowed === "boolean" ? allowed : null;
}
