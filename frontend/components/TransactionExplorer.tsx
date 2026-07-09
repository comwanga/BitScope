"use client";

import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  RegtestTransactionBuildResponse,
  RegtestTransactionSendResponse,
  TransactionInput,
  TransactionOutput,
  TransactionResponse,
  buildRegtestTransaction,
  fetchTransaction,
  sendRegtestTransaction
} from "@/lib/api";

export function TransactionExplorer() {
  const [query, setQuery] = useState("");
  const [transaction, setTransaction] = useState<TransactionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const txid = params.get("txid");
    if (txid) {
      setQuery(txid);
      void loadTransaction(txid);
    }
  }, []);

  async function loadTransaction(txid: string) {
    setLoading(true);
    setError("");
    try {
      setTransaction(await fetchTransaction(txid));
    } catch (caught) {
      setTransaction(null);
      setError(caught instanceof Error ? caught.message : "That transaction could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a transaction id.");
      return;
    }
    await loadTransaction(trimmed);
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Transaction explorer</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect a transaction</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Decode inputs, outputs, scripts, witnesses, and mempool context from Bitcoin Core.
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:flex-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
          placeholder="Transaction id"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
        >
          {loading ? "Loading" : "Search"}
        </button>
      </form>

      {error ? (
        <WarningBox title="Transaction unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <RegtestTransactionBuilder onInspect={(txid) => {
        setQuery(txid);
        void loadTransaction(txid);
      }} />

      {transaction ? <TransactionResult transaction={transaction} /> : <EmptyState />}
    </div>
  );
}

function RegtestTransactionBuilder({ onInspect }: { onInspect: (txid: string) => void }) {
  const [walletName, setWalletName] = useState("");
  const [address, setAddress] = useState("");
  const [amount, setAmount] = useState(0.01);
  const [mineConfirmation, setMineConfirmation] = useState(true);
  const [result, setResult] = useState<RegtestTransactionBuildResponse | RegtestTransactionSendResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<"build" | "send" | null>(null);

  async function submit(mode: "build" | "send") {
    if (!walletName.trim() || !address.trim()) {
      setError("Provide a loaded wallet and destination address.");
      return;
    }
    setLoading(mode);
    setError("");
    try {
      const response =
        mode === "build"
          ? await buildRegtestTransaction(walletName.trim(), address.trim(), amount)
          : await sendRegtestTransaction(walletName.trim(), address.trim(), amount, mineConfirmation);
      setResult(response);
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Regtest transaction action failed.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <section className="space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Regtest transaction builder</p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">Build, sign, and broadcast with raw transaction RPCs</h2>
        <p className="mt-3 text-sm leading-6 text-stone-700">
          This flow is regtest-only and uses a loaded Bitcoin Core wallet to fund and sign a transaction before optional broadcast.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_1fr_10rem]">
        <label className="grid gap-1 text-sm font-medium text-stone-600">
          Wallet name
          <input
            value={walletName}
            onChange={(event) => setWalletName(event.target.value)}
            className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            placeholder="Loaded regtest wallet"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-stone-600">
          Destination address
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            placeholder="bcrt1..."
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-stone-600">
          Amount BTC
          <input
            type="number"
            min={0.00000001}
            step={0.00000001}
            value={amount}
            onChange={(event) => setAmount(Number(event.target.value))}
            className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
          />
        </label>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
          <input
            type="checkbox"
            checked={mineConfirmation}
            onChange={(event) => setMineConfirmation(event.target.checked)}
            className="h-4 w-4 accent-forest"
          />
          Mine one confirmation after broadcast
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => void submit("build")}
            disabled={loading !== null}
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-stone-50 disabled:cursor-wait disabled:opacity-70"
          >
            {loading === "build" ? "Building" : "Build only"}
          </button>
          <button
            type="button"
            onClick={() => void submit("send")}
            disabled={loading !== null}
            className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
          >
            {loading === "send" ? "Sending" : "Build and send"}
          </button>
        </div>
      </div>

      {error ? (
        <WarningBox title="Regtest transaction unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {result ? <RegtestBuilderResult result={result} onInspect={onInspect} /> : null}
    </section>
  );
}

function RegtestBuilderResult({
  result,
  onInspect
}: {
  result: RegtestTransactionBuildResponse | RegtestTransactionSendResponse;
  onInspect: (txid: string) => void;
}) {
  const confirmationHashes = "confirmation_block_hashes" in result ? result.confirmation_block_hashes : [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Signed" value={result.complete ? "complete" : "incomplete"} detail="Wallet signing result" />
        <StatusCard label="Fee" value={result.fee_btc === null ? "unknown" : `${result.fee_btc.toFixed(8)} BTC`} detail="fundrawtransaction estimate" />
        <StatusCard label="Change position" value={result.change_position === null ? "none" : String(result.change_position)} detail="Wallet-added change output" />
        <StatusCard label="Confirmations mined" value={String(confirmationHashes.length)} detail="Optional regtest block" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-white p-4">
        <h3 className="text-lg font-semibold text-ink">Transaction artifacts</h3>
        <HexField label="Unsigned hex" value={result.unsigned_hex} />
        <HexField label="Funded hex" value={result.funded_hex} />
        <HexField label="Signed hex" value={result.signed_hex ?? "not available"} />
        {result.txid ? (
          <button
            type="button"
            onClick={() => onInspect(result.txid as string)}
            className="mt-4 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-forest hover:bg-stone-50 hover:text-ink"
          >
            Inspect txid
          </button>
        ) : null}
      </section>

      <CommandExplanationCard
        title="Regtest transaction builder"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify({ [result.address]: result.amount_btc }, null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function HexField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[8rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-xs leading-5 text-stone-800">{value}</div>
    </div>
  );
}

function TransactionResult({ transaction }: { transaction: TransactionResponse }) {
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-2">
        <span className="rounded-md bg-forest px-3 py-1 text-sm font-medium text-white">
          {transaction.in_mempool ? "mempool" : transaction.confirmations ? "confirmed" : "not in mempool"}
        </span>
        <span className="rounded-md bg-stone-200 px-3 py-1 text-sm font-medium text-stone-700">
          {transaction.inputs.some((input) => input.coinbase) ? "coinbase" : "regular transaction"}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Confirmations" value={formatNullableNumber(transaction.confirmations)} detail="Blocks confirming this tx" />
        <StatusCard label="Inputs" value={formatNullableNumber(transaction.inputs.length)} detail="Previous outputs being spent" />
        <StatusCard label="Outputs" value={formatNullableNumber(transaction.outputs.length)} detail="New UTXOs created" />
        <StatusCard label="Fee" value={formatFee(transaction)} detail={transaction.fee_source ?? "Unavailable without enough context"} />
        <StatusCard label="Version" value={formatNullableNumber(transaction.version)} detail="Transaction format version" />
        <StatusCard label="Virtual size" value={formatVbytes(transaction.vsize)} detail="Fee-rate relevant size" />
        <StatusCard label="Weight" value={formatNullableNumber(transaction.weight)} detail="SegWit weight units" />
        <StatusCard label="Locktime" value={formatNullableNumber(transaction.locktime)} detail="Earliest valid inclusion rule" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Identity</h2>
        <div className="mt-4 grid gap-3 text-sm">
          <Field label="txid" value={transaction.txid} />
          <Field label="wtxid/hash" value={transaction.hash ?? "unavailable"} />
          <Field label="Block hash" value={transaction.block_hash ?? "unconfirmed or unavailable"} />
          <Field label="Block time" value={formatTimestamp(transaction.block_time)} />
        </div>
      </section>

      <UtxoFlow transaction={transaction} />

      <CommandExplanationCard
        title="Transaction lookup"
        command={transaction.cli_commands.join("\n")}
        rpcMethod={transaction.rpc_methods.join(", ")}
        parameters={`["${transaction.txid}", true]`}
        explanation={transaction.explanation}
        concepts={transaction.concepts}
        rawJson={transaction.raw}
      />
    </div>
  );
}

function UtxoFlow({ transaction }: { transaction: TransactionResponse }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-ink">UTXO flow</h2>
      <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_auto_1fr]">
        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase text-stone-500">Inputs</h3>
          {transaction.inputs.map((input, index) => (
            <InputCard key={`${input.previous_txid ?? input.coinbase}-${index}`} input={input} index={index} />
          ))}
        </div>
        <div className="flex items-center justify-center">
          <div className="rounded-md bg-ink px-4 py-3 text-center text-sm font-semibold text-white">
            Transaction
          </div>
        </div>
        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase text-stone-500">Outputs</h3>
          {transaction.outputs.map((output) => (
            <OutputCard key={output.n} output={output} />
          ))}
        </div>
      </div>
    </section>
  );
}

function InputCard({ input, index }: { input: TransactionInput; index: number }) {
  return (
    <article className="rounded-lg border border-stone-200 bg-stone-50 p-4">
      <div className="text-sm font-semibold text-ink">Input {index}</div>
      {input.coinbase ? (
        <Field label="Coinbase" value={input.coinbase} />
      ) : (
        <>
          <Field label="Previous txid" value={input.previous_txid ?? "unavailable"} />
          <Field label="vout" value={input.vout === null ? "unavailable" : String(input.vout)} />
        </>
      )}
      <Field label="Sequence" value={input.sequence === null ? "unavailable" : String(input.sequence)} />
      <Field label="scriptSig" value={input.script_sig_asm ?? input.script_sig_hex ?? "empty"} />
      <Field label="Witness" value={input.witness.length ? `${input.witness.length} stack item(s)` : "none"} />
    </article>
  );
}

function OutputCard({ output }: { output: TransactionOutput }) {
  return (
    <article className="rounded-lg border border-stone-200 bg-stone-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">Output {output.n}</div>
        <div className="rounded-md bg-white px-2 py-1 text-sm font-medium text-forest">{output.value_btc.toFixed(8)} BTC</div>
      </div>
      <Field label="Type" value={output.script_type ?? "unknown"} />
      <Field label="Address" value={output.address ?? "not address-bearing"} />
      <Field label="scriptPubKey" value={output.script_pub_key_asm ?? output.script_pub_key_hex ?? "unavailable"} />
    </article>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[8rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-stone-800">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Search by txid">
      <p>Paste a transaction id from the block explorer. Confirmed lookup works best when Bitcoin Core has `txindex=1` enabled.</p>
    </WarningBox>
  );
}

function formatNullableNumber(value: number | null) {
  return value === null ? "unavailable" : new Intl.NumberFormat("en-US").format(value);
}

function formatVbytes(value: number | null) {
  return value === null ? "unavailable" : `${formatNullableNumber(value)} vB`;
}

function formatFee(transaction: TransactionResponse) {
  return transaction.fee_btc === null ? "unavailable" : `${transaction.fee_btc.toFixed(8)} BTC`;
}

function formatTimestamp(value: number | null) {
  return value === null ? "unavailable" : new Date(value * 1000).toISOString();
}
