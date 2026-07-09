"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { AddressResponse, AddressUtxo, fetchAddress } from "@/lib/api";

export function AddressExplorer() {
  const [query, setQuery] = useState("");
  const [address, setAddress] = useState<AddressResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const selectedAddress = params.get("address");
    if (selectedAddress) {
      setQuery(selectedAddress);
      void loadAddress(selectedAddress);
    }
  }, []);

  async function loadAddress(value: string) {
    setLoading(true);
    setError("");
    try {
      setAddress(await fetchAddress(value));
    } catch (caught) {
      setAddress(null);
      setError(caught instanceof Error ? caught.message : "That address could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a Bitcoin address.");
      return;
    }
    await loadAddress(trimmed);
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Address explorer</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Validate addresses and wallet UTXOs</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Check network validity, script details, wallet ownership, received amount, and spendable outputs.
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:flex-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
          placeholder="Bitcoin address"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
        >
          {loading ? "Loading" : "Inspect address"}
        </button>
      </form>

      {error ? (
        <WarningBox title="Address unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {address ? <AddressResult address={address} /> : <EmptyState />}
    </div>
  );
}

function AddressResult({ address }: { address: AddressResponse }) {
  return (
    <div className="space-y-8">
      {address.limitation ? (
        <WarningBox title="Address history limitation">
          <p>{address.limitation}</p>
        </WarningBox>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Validity" value={address.is_valid ? "valid" : "invalid"} detail="Validated by Bitcoin Core" />
        <StatusCard label="Network" value={address.network ?? "unavailable"} detail="Configured Core chain" />
        <StatusCard label="Type" value={address.address_type ?? "unknown"} detail="Inferred from wallet or witness data" />
        <StatusCard label="Wallet" value={formatWalletStatus(address)} detail={address.wallet_name ?? "No wallet context"} />
        <StatusCard label="Received" value={formatBtc(address.received_btc)} detail="Wallet RPC amount" />
        <StatusCard label="UTXOs" value={String(address.utxos.length)} detail="Unspent wallet outputs" />
        <StatusCard label="Watch-only" value={formatBoolean(address.is_watch_only)} detail="Known to wallet without private key" />
        <StatusCard label="Solvable" value={formatBoolean(address.solvable)} detail="Wallet can construct script satisfaction" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Address details</h2>
        <Field label="Address" value={address.address} />
        <Field label="scriptPubKey" value={address.script_pub_key ?? "unavailable"} />
        <Field label="Witness version" value={address.witness_version === null ? "unavailable" : String(address.witness_version)} />
        <Field label="Witness program" value={address.witness_program ?? "unavailable"} />
      </section>

      {address.utxos.length ? <UtxoList utxos={address.utxos} /> : null}

      <CommandExplanationCard
        title="Address lookup"
        command={address.cli_commands.join("\n")}
        rpcMethod={address.rpc_methods.join(", ")}
        parameters={`["${address.address}"]`}
        explanation={address.explanation}
        concepts={address.concepts}
        rawJson={address.raw}
      />
    </div>
  );
}

function UtxoList({ utxos }: { utxos: AddressUtxo[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-ink">Wallet UTXOs</h2>
      <div className="mt-4 space-y-3">
        {utxos.map((utxo) => (
          <article key={`${utxo.txid}:${utxo.vout}`} className="rounded-lg border border-stone-200 bg-stone-50 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <Link href={`/transactions?txid=${utxo.txid}`} className="break-all font-mono text-sm font-semibold text-forest hover:text-ink">
                {utxo.txid}:{utxo.vout}
              </Link>
              <div className="rounded-md bg-white px-2 py-1 text-sm font-medium text-forest">{utxo.amount_btc.toFixed(8)} BTC</div>
            </div>
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
              <MiniField label="Confirmations" value={String(utxo.confirmations)} />
              <MiniField label="Spendable" value={formatBoolean(utxo.spendable)} />
              <MiniField label="Solvable" value={formatBoolean(utxo.solvable)} />
              <MiniField label="Safe" value={formatBoolean(utxo.safe)} />
            </div>
            {utxo.descriptor ? <Field label="Descriptor" value={utxo.descriptor} /> : null}
          </article>
        ))}
      </div>
    </section>
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
    <div>
      <div className="text-xs font-medium uppercase text-stone-500">{label}</div>
      <div className="mt-1 font-mono text-stone-800">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Search by address">
      <p>Paste a regtest, testnet, signet, or mainnet address that matches your configured Bitcoin Core network.</p>
    </WarningBox>
  );
}

function formatWalletStatus(address: AddressResponse) {
  if (address.is_mine) {
    return "mine";
  }
  if (address.is_watch_only) {
    return "watch-only";
  }
  return "not wallet-owned";
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "unknown";
  }
  return value ? "yes" : "no";
}

function formatBtc(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC`;
}
