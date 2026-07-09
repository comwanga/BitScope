"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  WalletActionResponse,
  WalletAddressResponse,
  WalletBalanceResponse,
  WalletSummaryResponse,
  WalletTransactionsResponse,
  WalletUtxo,
  WalletUtxosResponse,
  createWallet,
  fetchWalletBalance,
  fetchWalletTransactions,
  fetchWalletUtxos,
  fetchWallets,
  getNewWalletAddress,
  loadWallet
} from "@/lib/api";

export function WalletLab() {
  const [summary, setSummary] = useState<WalletSummaryResponse | null>(null);
  const [selectedWallet, setSelectedWallet] = useState("");
  const [balance, setBalance] = useState<WalletBalanceResponse | null>(null);
  const [utxos, setUtxos] = useState<WalletUtxosResponse | null>(null);
  const [transactions, setTransactions] = useState<WalletTransactionsResponse | null>(null);
  const [newAddress, setNewAddress] = useState<WalletAddressResponse | null>(null);
  const [lastAction, setLastAction] = useState<WalletActionResponse | null>(null);
  const [walletNameInput, setWalletNameInput] = useState("");
  const [labelInput, setLabelInput] = useState("bitscope");
  const [addressType, setAddressType] = useState("bech32");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void refreshWallets();
  }, []);

  async function refreshWallets() {
    setLoading(true);
    setError("");
    try {
      const wallets = await fetchWallets();
      setSummary(wallets);
      const preferredWallet = selectedWallet || wallets.configured_wallet || wallets.loaded_wallets[0] || wallets.available_wallets[0]?.wallet_name || "";
      setSelectedWallet(preferredWallet);
      if (preferredWallet) {
        await refreshWalletDetails(preferredWallet);
      }
    } catch (caught) {
      setSummary(null);
      setError(caught instanceof Error ? caught.message : "Wallets could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshWalletDetails(walletName: string) {
    if (!walletName) {
      return;
    }

    const [nextBalance, nextUtxos, nextTransactions] = await Promise.all([
      fetchWalletBalance(walletName),
      fetchWalletUtxos(walletName),
      fetchWalletTransactions(walletName, 20)
    ]);
    setBalance(nextBalance);
    setUtxos(nextUtxos);
    setTransactions(nextTransactions);
  }

  async function selectWallet(walletName: string) {
    setSelectedWallet(walletName);
    setNewAddress(null);
    setLastAction(null);
    setError("");
    setLoading(true);
    try {
      await refreshWalletDetails(walletName);
    } catch (caught) {
      setBalance(null);
      setUtxos(null);
      setTransactions(null);
      setError(caught instanceof Error ? caught.message : "Wallet details could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runWalletAction(createWallet);
  }

  async function runWalletAction(action: (walletName: string) => Promise<WalletActionResponse>) {
    const walletName = walletNameInput.trim();
    if (!walletName) {
      setError("Enter a wallet name.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await action(walletName);
      setLastAction(result);
      setSelectedWallet(result.wallet_name);
      setWalletNameInput("");
      await refreshWallets();
      await refreshWalletDetails(result.wallet_name);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Wallet action failed.");
    } finally {
      setLoading(false);
    }
  }

  async function submitNewAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWallet) {
      setError("Select a loaded wallet first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setNewAddress(await getNewWalletAddress(selectedWallet, labelInput, addressType));
    } catch (caught) {
      setNewAddress(null);
      setError(caught instanceof Error ? caught.message : "A new address could not be generated.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Wallet laboratory</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect and operate local wallets</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Load wallets, create a regtest learning wallet, generate receiving addresses, and inspect wallet-owned UTXOs.
        </p>
      </header>

      {error ? (
        <WarningBox title="Wallet unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {lastAction ? (
        <WarningBox title="Wallet action">
          <p>{lastAction.message}</p>
          {lastAction.warning ? <p className="mt-2">{lastAction.warning}</p> : null}
        </WarningBox>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink">Wallets</h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">Create, load, or select a wallet known to Bitcoin Core.</p>
            </div>
            <button
              type="button"
              onClick={refreshWallets}
              disabled={loading}
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50 disabled:cursor-wait disabled:opacity-70"
            >
              Refresh
            </button>
          </div>

          <form onSubmit={submitCreate} className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
            <input
              value={walletNameInput}
              onChange={(event) => setWalletNameInput(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
              placeholder="Wallet name"
            />
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              Create
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => void runWalletAction(loadWallet)}
              className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-stone-50 disabled:cursor-wait disabled:opacity-70"
            >
              Load
            </button>
          </form>

          <div className="mt-5 space-y-2">
            {summary?.available_wallets.length ? (
              summary.available_wallets.map((wallet) => (
                <button
                  type="button"
                  key={wallet.wallet_name}
                  onClick={() => void selectWallet(wallet.wallet_name)}
                  className={`block w-full rounded-md border px-3 py-3 text-left hover:border-forest ${
                    selectedWallet === wallet.wallet_name ? "border-forest bg-stone-50" : "border-stone-200 bg-white"
                  }`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <span className="break-all font-mono text-sm font-semibold text-ink">{wallet.wallet_name}</span>
                    <span className={`rounded-md px-2 py-1 text-xs font-medium ${wallet.loaded ? "bg-forest text-white" : "bg-stone-200 text-stone-700"}`}>
                      {wallet.loaded ? "loaded" : "available"}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-600">
                    <span>{formatBoolean(wallet.descriptors)} descriptors</span>
                    <span>{formatBoolean(wallet.private_keys_enabled)} private keys</span>
                    <span>{formatBoolean(wallet.blank)} blank</span>
                  </div>
                </button>
              ))
            ) : (
              <p className="rounded-md bg-stone-100 px-3 py-3 text-sm text-stone-700">
                No wallets found yet. Create one to begin a regtest wallet workflow.
              </p>
            )}
          </div>
        </section>

        <WalletDetail
          selectedWallet={selectedWallet}
          balance={balance}
          utxos={utxos}
          transactions={transactions}
          newAddress={newAddress}
          labelInput={labelInput}
          addressType={addressType}
          loading={loading}
          onLabelChange={setLabelInput}
          onAddressTypeChange={setAddressType}
          onNewAddress={submitNewAddress}
        />
      </div>

      {summary ? (
        <CommandExplanationCard
          title="Wallet discovery"
          command={summary.cli_commands.join("\n")}
          rpcMethod={summary.rpc_methods.join(", ")}
          parameters="[]"
          explanation={summary.explanation}
          concepts={summary.concepts}
          rawJson={summary.raw}
        />
      ) : null}
    </div>
  );
}

type WalletDetailProps = {
  selectedWallet: string;
  balance: WalletBalanceResponse | null;
  utxos: WalletUtxosResponse | null;
  transactions: WalletTransactionsResponse | null;
  newAddress: WalletAddressResponse | null;
  labelInput: string;
  addressType: string;
  loading: boolean;
  onLabelChange: (label: string) => void;
  onAddressTypeChange: (addressType: string) => void;
  onNewAddress: (event: FormEvent<HTMLFormElement>) => void;
};

function WalletDetail({
  selectedWallet,
  balance,
  utxos,
  transactions,
  newAddress,
  labelInput,
  addressType,
  loading,
  onLabelChange,
  onAddressTypeChange,
  onNewAddress
}: WalletDetailProps) {
  if (!selectedWallet) {
    return (
      <WarningBox title="No wallet selected">
        <p>Create or load a wallet to inspect balances, addresses, UTXOs, and wallet transaction records.</p>
      </WarningBox>
    );
  }

  return (
    <div className="min-w-0 space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Trusted" value={formatBtc(balance?.trusted_btc ?? null)} detail="Confirmed wallet balance" />
        <StatusCard label="Pending" value={formatBtc(balance?.untrusted_pending_btc ?? null)} detail="Unconfirmed wallet amount" />
        <StatusCard label="Immature" value={formatBtc(balance?.immature_btc ?? null)} detail="Coinbase still maturing" />
        <StatusCard label="UTXOs" value={String(utxos?.utxos.length ?? 0)} detail={formatBtc(utxos?.total_btc ?? null)} />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Receive address</h2>
        <form onSubmit={onNewAddress} className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_auto]">
          <input
            value={labelInput}
            onChange={(event) => onLabelChange(event.target.value)}
            className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
            placeholder="Label"
          />
          <select
            value={addressType}
            onChange={(event) => onAddressTypeChange(event.target.value)}
            className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
          >
            <option value="bech32">bech32</option>
            <option value="bech32m">bech32m</option>
            <option value="p2sh-segwit">p2sh-segwit</option>
            <option value="legacy">legacy</option>
          </select>
          <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            Generate
          </button>
        </form>
        {newAddress ? (
          <div className="mt-4 rounded-md bg-stone-100 p-3">
            <div className="text-xs font-medium uppercase text-stone-500">{newAddress.address_type} address</div>
            <Link href={`/address?address=${encodeURIComponent(newAddress.address)}`} className="mt-1 block break-all font-mono text-sm font-semibold text-forest hover:text-ink">
              {newAddress.address}
            </Link>
          </div>
        ) : null}
      </section>

      {utxos ? <WalletUtxoList utxos={utxos.utxos} /> : null}
      {transactions ? <WalletTransactionList transactions={transactions.transactions} /> : null}
    </div>
  );
}

function WalletUtxoList({ utxos }: { utxos: WalletUtxo[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Wallet UTXOs</h2>
      <div className="mt-4 max-h-[28rem] space-y-3 overflow-auto pr-1">
        {utxos.length ? (
          utxos.map((utxo) => (
            <article key={`${utxo.txid}:${utxo.vout}`} className="rounded-md border border-stone-200 bg-stone-50 p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <Link href={`/transactions?txid=${utxo.txid}`} className="break-all font-mono text-xs font-semibold text-forest hover:text-ink">
                  {utxo.txid}:{utxo.vout}
                </Link>
                <span className="shrink-0 rounded-md bg-white px-2 py-1 text-sm font-medium text-forest">{utxo.amount_btc.toFixed(8)} BTC</span>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-4">
                <span>{utxo.confirmations} confirmations</span>
                <span>{formatBoolean(utxo.spendable)} spendable</span>
                <span>{formatBoolean(utxo.solvable)} solvable</span>
                <span>{formatBoolean(utxo.safe)} safe</span>
              </div>
              {utxo.address ? <div className="mt-2 break-all font-mono text-xs text-stone-700">{utxo.address}</div> : null}
            </article>
          ))
        ) : (
          <p className="rounded-md bg-stone-100 px-3 py-3 text-sm text-stone-700">No spendable wallet UTXOs are available yet.</p>
        )}
      </div>
    </section>
  );
}

function WalletTransactionList({ transactions }: { transactions: WalletTransactionsResponse["transactions"] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Recent wallet transactions</h2>
      <div className="mt-4 max-h-[28rem] space-y-3 overflow-auto pr-1">
        {transactions.length ? (
          transactions.map((transaction, index) => (
            <article key={`${transaction.txid}-${index}`} className="rounded-md border border-stone-200 bg-stone-50 p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <Link href={`/transactions?txid=${transaction.txid}`} className="break-all font-mono text-xs font-semibold text-forest hover:text-ink">
                  {transaction.txid}
                </Link>
                <span className="shrink-0 rounded-md bg-white px-2 py-1 text-xs font-medium text-stone-700">{transaction.category ?? "wallet"}</span>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-4">
                <span>{formatBtc(transaction.amount_btc)}</span>
                <span>{transaction.confirmations ?? 0} confirmations</span>
                <span>{formatBoolean(transaction.trusted)} trusted</span>
                <span>{formatTimestamp(transaction.time)}</span>
              </div>
              {transaction.address ? <div className="mt-2 break-all font-mono text-xs text-stone-700">{transaction.address}</div> : null}
            </article>
          ))
        ) : (
          <p className="rounded-md bg-stone-100 px-3 py-3 text-sm text-stone-700">No wallet transaction records yet.</p>
        )}
      </div>
    </section>
  );
}

function formatBtc(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC`;
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "unknown";
  }
  return value ? "yes" : "no";
}

function formatTimestamp(value: number | null) {
  return value === null ? "no time" : new Date(value * 1000).toISOString();
}
