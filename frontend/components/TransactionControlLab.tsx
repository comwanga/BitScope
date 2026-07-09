"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  CpfpChildResponse,
  RbfBumpResponse,
  TransactionPolicyResponse,
  bumpRbfTransaction,
  createCpfpChild,
  fetchTransactionPolicy
} from "@/lib/api";

export function TransactionControlLab() {
  const [txid, setTxid] = useState("");
  const [policy, setPolicy] = useState<TransactionPolicyResponse | null>(null);
  const [policyError, setPolicyError] = useState("");
  const [loadingPolicy, setLoadingPolicy] = useState(false);

  async function inspectPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!txid.trim()) {
      setPolicyError("Enter an unconfirmed transaction id.");
      return;
    }

    setLoadingPolicy(true);
    setPolicyError("");
    try {
      setPolicy(await fetchTransactionPolicy(txid.trim()));
    } catch (caught) {
      setPolicy(null);
      setPolicyError(caught instanceof Error ? caught.message : "Transaction policy data could not be loaded.");
    } finally {
      setLoadingPolicy(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Transaction control lab</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Study RBF and CPFP policy</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Inspect unconfirmed transaction policy, bump wallet-owned replaceable transactions, and build child-pays-for-parent transactions on regtest.
        </p>
      </header>

      <WarningBox title="Regtest safety boundary">
        <p>RBF and CPFP actions can broadcast transactions. BitScope only enables the action endpoints when the backend is configured for regtest.</p>
      </WarningBox>

      <form onSubmit={inspectPolicy} className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Mempool transaction id
            <input
              value={txid}
              onChange={(event) => setTxid(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="64-character txid"
            />
          </label>
          <button type="submit" disabled={loadingPolicy} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loadingPolicy ? "Inspecting" : "Inspect policy"}
          </button>
        </div>
      </form>

      {policyError ? (
        <WarningBox title="Policy unavailable">
          <p>{policyError}</p>
        </WarningBox>
      ) : null}

      {policy ? <PolicyResult policy={policy} /> : <EmptyPolicy />}

      <section className="grid gap-6 xl:grid-cols-2">
        <RbfPanel defaultTxid={policy?.txid ?? txid} />
        <CpfpPanel defaultTxid={policy?.txid ?? txid} />
      </section>
    </div>
  );
}

function PolicyResult({ policy }: { policy: TransactionPolicyResponse }) {
  return (
    <div className="space-y-5">
      {policy.warnings.length ? (
        <WarningBox title="Policy warning">
          <ul className="space-y-1">
            {policy.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </WarningBox>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="RBF" value={policy.can_rbf ? "Available" : "Not signaled"} detail="BIP125 replaceability" />
        <StatusCard label="CPFP" value={policy.can_cpfp ? "Possible" : "Unavailable"} detail="Spend an unconfirmed output" />
        <StatusCard label="Fee rate" value={formatSatVb(policy.fee_rate_sat_vb)} detail="Base fee divided by vsize" />
        <StatusCard label="Virtual size" value={formatVbytes(policy.vsize)} detail="Fee-rate denominator" />
        <StatusCard label="Ancestors" value={formatNumber(policy.ancestor_count)} detail={`${formatBtc(policy.ancestor_fees_btc)} package fees`} />
        <StatusCard label="Descendants" value={formatNumber(policy.descendant_count)} detail={`${formatBtc(policy.descendant_fees_btc)} package fees`} />
        <StatusCard label="Base fee" value={formatBtc(policy.fee_btc)} detail="Transaction fee" />
        <StatusCard label="Modified fee" value={formatBtc(policy.modified_fee_btc)} detail="After prioritization" />
      </section>

      <CommandExplanationCard
        title="Mempool policy lookup"
        command={policy.cli_commands.join("\n")}
        rpcMethod={policy.rpc_methods.join(", ")}
        parameters={`["${policy.txid}"]`}
        explanation={policy.explanation}
        concepts={policy.concepts}
        rawJson={policy.raw}
      />
    </div>
  );
}

function RbfPanel({ defaultTxid }: { defaultTxid: string }) {
  const [walletName, setWalletName] = useState("");
  const [txid, setTxid] = useState(defaultTxid);
  const [feeRate, setFeeRate] = useState(10);
  const [confTarget, setConfTarget] = useState(3);
  const [result, setResult] = useState<RbfBumpResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!walletName.trim() || !txid.trim()) {
      setError("Provide a wallet name and replaceable transaction id.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      setResult(await bumpRbfTransaction(walletName.trim(), txid.trim(), feeRate, confTarget));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "RBF fee bump could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div>
        <p className="text-sm font-semibold uppercase text-forest">Replace-by-fee</p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">Bump a wallet transaction</h2>
        <p className="mt-3 text-sm leading-6 text-stone-700">Uses Bitcoin Core wallet `bumpfee` for wallet-owned unconfirmed transactions that signal BIP125.</p>
      </div>

      <ControlFields walletName={walletName} setWalletName={setWalletName} txid={txid} setTxid={setTxid} />
      <div className="grid gap-3 sm:grid-cols-2">
        <NumberField label="Fee rate sats/vB" value={feeRate} onChange={setFeeRate} min={0.1} step={0.1} />
        <NumberField label="Confirmation target" value={confTarget} onChange={setConfTarget} min={1} step={1} />
      </div>
      <button type="button" onClick={() => void submit()} disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
        {loading ? "Bumping" : "Create replacement"}
      </button>

      {error ? (
        <WarningBox title="RBF unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {result ? <RbfResult result={result} /> : null}
    </section>
  );
}

function CpfpPanel({ defaultTxid }: { defaultTxid: string }) {
  const [walletName, setWalletName] = useState("");
  const [parentTxid, setParentTxid] = useState(defaultTxid);
  const [parentVout, setParentVout] = useState(0);
  const [destinationAddress, setDestinationAddress] = useState("");
  const [amountBtc, setAmountBtc] = useState(0.001);
  const [feeRate, setFeeRate] = useState(20);
  const [broadcast, setBroadcast] = useState(false);
  const [result, setResult] = useState<CpfpChildResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!walletName.trim() || !parentTxid.trim() || !destinationAddress.trim()) {
      setError("Provide a wallet, parent txid, parent output, and destination address.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      setResult(await createCpfpChild(walletName.trim(), parentTxid.trim(), parentVout, destinationAddress.trim(), amountBtc, feeRate, broadcast));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "CPFP child transaction could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div>
        <p className="text-sm font-semibold uppercase text-forest">Child pays for parent</p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">Build a high-fee child</h2>
        <p className="mt-3 text-sm leading-6 text-stone-700">Spends a wallet-owned unconfirmed parent output, tests mempool acceptance, and optionally broadcasts on regtest.</p>
      </div>

      <ControlFields walletName={walletName} setWalletName={setWalletName} txid={parentTxid} setTxid={setParentTxid} txidLabel="Parent txid" />
      <div className="grid gap-3 sm:grid-cols-2">
        <NumberField label="Parent vout" value={parentVout} onChange={setParentVout} min={0} step={1} />
        <NumberField label="Amount BTC" value={amountBtc} onChange={setAmountBtc} min={0.00000001} step={0.00000001} />
        <NumberField label="Fee rate sats/vB" value={feeRate} onChange={setFeeRate} min={0.1} step={0.1} />
        <label className="grid gap-2 text-sm font-medium text-stone-600">
          Destination address
          <input
            value={destinationAddress}
            onChange={(event) => setDestinationAddress(event.target.value)}
            className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            placeholder="bcrt1..."
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
        <input type="checkbox" checked={broadcast} onChange={(event) => setBroadcast(event.target.checked)} className="h-4 w-4 accent-forest" />
        Broadcast child after testmempoolaccept
      </label>
      <button type="button" onClick={() => void submit()} disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
        {loading ? "Creating" : broadcast ? "Create and broadcast" : "Create child"}
      </button>

      {error ? (
        <WarningBox title="CPFP unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {result ? <CpfpResult result={result} /> : null}
    </section>
  );
}

function RbfResult({ result }: { result: RbfBumpResponse }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatusCard label="Replacement" value={result.replacement_txid ? "created" : "not returned"} detail={result.replacement_txid ?? "No txid returned"} />
        <StatusCard label="Original fee" value={formatBtc(result.original_fee_btc)} detail="Previous transaction fee" />
        <StatusCard label="Fee delta" value={formatBtc(result.fee_delta_btc)} detail="Added fee" />
      </div>
      {result.errors.length ? (
        <WarningBox title="Bitcoin Core bumpfee notes">
          <ul className="space-y-1">{result.errors.map((item) => <li key={item}>{item}</li>)}</ul>
        </WarningBox>
      ) : null}
      <CommandExplanationCard title="RBF bumpfee" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`["${result.original_txid}"]`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
      {result.replacement_txid ? <ExplorerLink txid={result.replacement_txid} /> : null}
    </div>
  );
}

function CpfpResult({ result }: { result: CpfpChildResponse }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatusCard label="Signed" value={result.complete ? "complete" : "incomplete"} detail="Wallet signing result" />
        <StatusCard label="Fee" value={formatBtc(result.fee_btc)} detail="Child transaction fee" />
        <StatusCard label="Broadcast" value={result.broadcast ? "yes" : "no"} detail={result.child_txid ?? "Built for review"} />
      </div>
      <HexField label="Signed hex" value={result.signed_hex ?? "not available"} />
      <CommandExplanationCard title="CPFP child transaction" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`["${result.parent_txid}:${result.parent_vout}"]`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
      {result.child_txid ? <ExplorerLink txid={result.child_txid} /> : null}
    </div>
  );
}

function ControlFields({
  walletName,
  setWalletName,
  txid,
  setTxid,
  txidLabel = "Transaction id"
}: {
  walletName: string;
  setWalletName: (value: string) => void;
  txid: string;
  setTxid: (value: string) => void;
  txidLabel?: string;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-2 text-sm font-medium text-stone-600">
        Wallet name
        <input value={walletName} onChange={(event) => setWalletName(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="Loaded regtest wallet" />
      </label>
      <label className="grid gap-2 text-sm font-medium text-stone-600">
        {txidLabel}
        <input value={txid} onChange={(event) => setTxid(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="64-character txid" />
      </label>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  step
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  step: number;
}) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input type="number" min={min} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest" />
    </label>
  );
}

function HexField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-stone-300 bg-white p-4">
      <div className="text-sm font-medium text-stone-500">{label}</div>
      <div className="mt-2 break-all font-mono text-xs leading-5 text-stone-800">{value}</div>
    </div>
  );
}

function ExplorerLink({ txid }: { txid: string }) {
  return (
    <Link href={`/transactions?txid=${txid}`} className="inline-block break-all rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-forest hover:bg-stone-50 hover:text-ink">
      Open transaction explorer
    </Link>
  );
}

function EmptyPolicy() {
  return (
    <WarningBox title="Start with mempool policy">
      <p>Paste an unconfirmed transaction id. Empty regtest mempools are normal; create a transaction without mining it to inspect RBF and CPFP behavior.</p>
    </WarningBox>
  );
}

function formatNumber(value: number | null) {
  return value === null ? "unknown" : value.toLocaleString();
}

function formatBtc(value: number | null) {
  return value === null ? "unknown" : `${value.toFixed(8)} BTC`;
}

function formatSatVb(value: number | null) {
  return value === null ? "unknown" : `${value.toFixed(2)} sats/vB`;
}

function formatVbytes(value: number | null) {
  return value === null ? "unknown" : `${value.toLocaleString()} vB`;
}
