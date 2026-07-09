"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  MultisigCreateResponse,
  MultisigFundResponse,
  MultisigSpendResponse,
  createMultisig,
  fundMultisig,
  spendMultisigPsbt
} from "@/lib/api";
import { useLabContext } from "@/lib/labContext";

export function MultisigLab() {
  const { context, setContext } = useLabContext();
  const [walletName, setWalletName] = useState(context.walletName);
  const [requiredSignatures, setRequiredSignatures] = useState(2);
  const [signerCount, setSignerCount] = useState(3);
  const [addressType, setAddressType] = useState("bech32");
  const [multisigAddress, setMultisigAddress] = useState(context.multisigAddress);
  const [fundAmount, setFundAmount] = useState(1);
  const [mineConfirmation, setMineConfirmation] = useState(true);
  const [destinationAddress, setDestinationAddress] = useState(context.lastAddress);
  const [spendAmount, setSpendAmount] = useState(0.5);
  const [extract, setExtract] = useState(false);
  const [created, setCreated] = useState<MultisigCreateResponse | null>(null);
  const [funded, setFunded] = useState<MultisigFundResponse | null>(null);
  const [spent, setSpent] = useState<MultisigSpendResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<"create" | "fund" | "spend" | null>(null);

  useEffect(() => {
    if (context.walletName) {
      setWalletName((current) => current || context.walletName);
    }
    if (context.multisigAddress) {
      setMultisigAddress((current) => current || context.multisigAddress);
    }
    if (context.lastAddress) {
      setDestinationAddress((current) => current || context.lastAddress);
    }
  }, [context.walletName, context.multisigAddress, context.lastAddress]);

  async function run(mode: "create" | "fund" | "spend", action: () => Promise<void>) {
    setLoading(mode);
    setError("");
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Multisig action failed.");
    } finally {
      setLoading(null);
    }
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("create", async () => {
      const result = await createMultisig(walletName.trim(), requiredSignatures, signerCount, addressType);
      setCreated(result);
      setMultisigAddress(result.multisig_address);
      setContext({ walletName: result.wallet_name, multisigAddress: result.multisig_address });
    });
  }

  async function submitFund(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("fund", async () => {
      const result = await fundMultisig(walletName.trim(), multisigAddress.trim(), fundAmount, mineConfirmation);
      setFunded(result);
      setContext({ walletName: result.wallet_name, multisigAddress: result.multisig_address });
    });
  }

  async function submitSpend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("spend", async () => {
      const result = await spendMultisigPsbt(walletName.trim(), multisigAddress.trim(), destinationAddress.trim(), spendAmount, extract);
      setSpent(result);
      setContext({ walletName: result.wallet_name, multisigAddress: result.multisig_address, lastAddress: result.destination_address });
    });
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Multisig laboratory</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Create, fund, and spend multisig</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Generate wallet-backed public keys, register an m-of-n multisig address, fund it on regtest, then spend from it with a PSBT.
        </p>
      </header>

      <WarningBox title="Expected regtest sequence">
        <p>Create or load a wallet, mine 101 blocks to make spendable coins, create the multisig address, fund it, then build the PSBT spend. Destination fields expect Bitcoin addresses, not wallet names.</p>
      </WarningBox>

      {error ? (
        <WarningBox title="Multisig action unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-3">
        <form onSubmit={submitCreate} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-xl font-semibold text-ink">1. Create address</h2>
          <WalletField walletName={walletName} onChange={setWalletName} />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <NumberField label="Required signatures" value={requiredSignatures} onChange={setRequiredSignatures} min={1} max={15} step={1} />
            <NumberField label="Signer keys" value={signerCount} onChange={setSignerCount} min={1} max={15} step={1} />
          </div>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Address type
            <select value={addressType} onChange={(event) => setAddressType(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest">
              <option value="bech32">bech32 P2WSH</option>
              <option value="p2sh-segwit">P2SH-SegWit</option>
              <option value="legacy">legacy P2SH</option>
            </select>
          </label>
          <button type="submit" disabled={loading !== null} className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading === "create" ? "Creating" : "Create multisig"}
          </button>
        </form>

        <form onSubmit={submitFund} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-xl font-semibold text-ink">2. Fund address</h2>
          <WalletField walletName={walletName} onChange={setWalletName} />
          <AddressField label="Multisig address" value={multisigAddress} onChange={setMultisigAddress} />
          <NumberField label="Amount BTC" value={fundAmount} onChange={setFundAmount} min={0.00000001} step={0.00000001} />
          <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
            <input type="checkbox" checked={mineConfirmation} onChange={(event) => setMineConfirmation(event.target.checked)} className="h-4 w-4 accent-forest" />
            Mine confirmation
          </label>
          <button type="submit" disabled={loading !== null} className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading === "fund" ? "Funding" : "Fund multisig"}
          </button>
        </form>

        <form onSubmit={submitSpend} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-xl font-semibold text-ink">3. Spend with PSBT</h2>
          <WalletField walletName={walletName} onChange={setWalletName} />
          <AddressField label="Multisig address" value={multisigAddress} onChange={setMultisigAddress} />
          <AddressField label="Destination address" value={destinationAddress} onChange={setDestinationAddress} />
          <NumberField label="Amount BTC" value={spendAmount} onChange={setSpendAmount} min={0.00000001} step={0.00000001} />
          <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
            <input type="checkbox" checked={extract} onChange={(event) => setExtract(event.target.checked)} className="h-4 w-4 accent-forest" />
            Extract raw transaction hex
          </label>
          <button type="submit" disabled={loading !== null} className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading === "spend" ? "Spending" : "Create spend PSBT"}
          </button>
        </form>
      </section>

      {created ? <CreateResult result={created} /> : null}
      {funded ? <FundResult result={funded} /> : null}
      {spent ? <SpendResult result={spent} /> : null}
    </div>
  );
}

function CreateResult({ result }: { result: MultisigCreateResponse }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Policy" value={`${result.required_signatures}-of-${result.signer_count}`} detail={result.address_type} />
        <StatusCard label="Address" value={result.multisig_address} detail="Registered with wallet" />
        <StatusCard label="Pubkeys" value={String(result.pubkeys.length)} detail="Generated by Bitcoin Core" />
        <StatusCard label="Warnings" value={String(result.warnings.length)} detail="Bitcoin Core notes" />
      </section>
      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Generated public keys</h2>
        <div className="mt-4 space-y-2">
          {result.pubkeys.map((pubkey, index) => (
            <div key={`${pubkey}-${index}`} className="break-all rounded-md bg-stone-100 px-3 py-2 font-mono text-xs text-ink">
              {pubkey}
            </div>
          ))}
        </div>
      </section>
      <CommandExplanationCard title="Create multisig" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`${result.required_signatures}-of-${result.signer_count}`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
    </div>
  );
}

function FundResult({ result }: { result: MultisigFundResponse }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Funded" value={`${result.amount_btc.toFixed(8)} BTC`} detail="Sent to multisig" />
        <StatusCard label="Transaction" value={result.txid} detail="Open in explorer" />
        <StatusCard label="Confirmations mined" value={String(result.confirmation_block_hashes.length)} detail="Regtest block count" />
        <StatusCard label="Wallet" value={result.wallet_name} detail="Funding wallet" />
      </section>
      <Link href={`/transactions?txid=${result.txid}`} className="inline-block break-all rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-forest hover:bg-stone-50 hover:text-ink">
        Open funding transaction
      </Link>
      <CommandExplanationCard title="Fund multisig" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`["${result.multisig_address}", ${result.amount_btc}]`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
    </div>
  );
}

function SpendResult({ result }: { result: MultisigSpendResponse }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Complete" value={result.complete ? "yes" : "no"} detail="Signing threshold met" />
        <StatusCard label="Inputs" value={String(result.input_count)} detail="Multisig UTXOs selected" />
        <StatusCard label="Fee" value={result.fee_btc === null ? "unknown" : `${result.fee_btc.toFixed(8)} BTC`} detail="Funding result" />
        <StatusCard label="Change position" value={result.change_position === null ? "none" : String(result.change_position)} detail="Wallet-selected change" />
      </section>
      <TextArtifact title={result.hex ? "Raw transaction hex" : "Final PSBT"} value={result.hex ?? result.final_psbt ?? result.processed_psbt} />
      <CommandExplanationCard title="Spend multisig with PSBT" command={result.cli_commands.join("\n")} rpcMethod={result.rpc_methods.join(", ")} parameters={`["${result.multisig_address}", "${result.destination_address}", ${result.amount_btc}]`} explanation={result.explanation} concepts={result.concepts} rawJson={result.raw} />
    </div>
  );
}

function WalletField({ walletName, onChange }: { walletName: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      Wallet name
      <input value={walletName} onChange={(event) => onChange(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="Loaded regtest wallet" />
    </label>
  );
}

function AddressField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max?: number;
  step: number;
}) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest" />
    </label>
  );
}

function TextArtifact({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100">
        <code>{value}</code>
      </pre>
    </section>
  );
}
