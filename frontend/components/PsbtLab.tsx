"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  PsbtCreateResponse,
  PsbtDecodeResponse,
  PsbtFinalizeResponse,
  PsbtProcessResponse,
  createPsbt,
  decodePsbt,
  finalizePsbt,
  processPsbt
} from "@/lib/api";

export function PsbtLab() {
  const [walletName, setWalletName] = useState("");
  const [recipientAddress, setRecipientAddress] = useState("");
  const [amountBtc, setAmountBtc] = useState(1);
  const [psbt, setPsbt] = useState("");
  const [sign, setSign] = useState(true);
  const [extract, setExtract] = useState(false);
  const [created, setCreated] = useState<PsbtCreateResponse | null>(null);
  const [decoded, setDecoded] = useState<PsbtDecodeResponse | null>(null);
  const [processed, setProcessed] = useState<PsbtProcessResponse | null>(null);
  const [finalized, setFinalized] = useState<PsbtFinalizeResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run(action: () => Promise<void>) {
    setLoading(true);
    setError("");
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "PSBT action failed.");
    } finally {
      setLoading(false);
    }
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const result = await createPsbt(walletName.trim(), recipientAddress.trim(), amountBtc);
      setCreated(result);
      setDecoded(result.decoded);
      setProcessed(null);
      setFinalized(null);
      setPsbt(result.psbt);
    });
  }

  async function submitDecode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const result = await decodePsbt(psbt.trim());
      setDecoded(result);
    });
  }

  async function submitProcess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const result = await processPsbt(walletName.trim(), psbt.trim(), sign);
      setProcessed(result);
      setDecoded(result.decoded);
      setFinalized(null);
      setPsbt(result.psbt);
    });
  }

  async function submitFinalize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      setFinalized(await finalizePsbt(psbt.trim(), extract));
    });
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">PSBT laboratory</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Build, inspect, and finalize PSBTs</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Practice the Partially Signed Bitcoin Transaction flow without broadcasting raw transactions.
        </p>
      </header>

      <WarningBox title="No broadcast step">
        <p>BitScope can create, decode, process, and finalize PSBTs here. It does not broadcast the final transaction.</p>
      </WarningBox>

      {error ? (
        <WarningBox title="PSBT action unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Create funded PSBT</h2>
          <form onSubmit={submitCreate} className="mt-4 grid gap-3">
            <WalletInput walletName={walletName} onWalletNameChange={setWalletName} />
            <label className="grid gap-1 text-sm font-medium text-stone-600">
              Recipient address
              <input
                value={recipientAddress}
                onChange={(event) => setRecipientAddress(event.target.value)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-stone-600">
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
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              Create PSBT
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Current PSBT</h2>
          <form onSubmit={submitDecode} className="mt-4 grid gap-3">
            <textarea
              value={psbt}
              onChange={(event) => setPsbt(event.target.value)}
              className="min-h-40 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-xs text-ink outline-none focus:border-forest"
              placeholder="Paste base64 PSBT"
              spellCheck={false}
            />
            <button type="submit" disabled={loading} className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-stone-50 disabled:cursor-wait disabled:opacity-70">
              Decode PSBT
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Wallet process</h2>
          <form onSubmit={submitProcess} className="mt-4 grid gap-3">
            <WalletInput walletName={walletName} onWalletNameChange={setWalletName} />
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input type="checkbox" checked={sign} onChange={(event) => setSign(event.target.checked)} className="h-4 w-4 accent-forest" />
              Sign with wallet keys
            </label>
            <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
              Process PSBT
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Finalize</h2>
          <form onSubmit={submitFinalize} className="mt-4 grid gap-3">
            <label className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <input type="checkbox" checked={extract} onChange={(event) => setExtract(event.target.checked)} className="h-4 w-4 accent-forest" />
              Extract raw transaction hex
            </label>
            <button type="submit" disabled={loading} className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-stone-50 disabled:cursor-wait disabled:opacity-70">
              Finalize PSBT
            </button>
          </form>
        </section>
      </div>

      {decoded ? <DecodeSummary decoded={decoded} /> : null}
      {created ? <CreateResult result={created} /> : null}
      {processed ? <ProcessResult result={processed} /> : null}
      {finalized ? <FinalizeResult result={finalized} /> : null}
    </div>
  );
}

function WalletInput({ walletName, onWalletNameChange }: { walletName: string; onWalletNameChange: (walletName: string) => void }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-stone-600">
      Wallet name
      <input
        value={walletName}
        onChange={(event) => onWalletNameChange(event.target.value)}
        className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
      />
    </label>
  );
}

function DecodeSummary({ decoded }: { decoded: PsbtDecodeResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Inputs" value={String(decoded.input_count)} detail="PSBT input records" />
        <StatusCard label="Outputs" value={String(decoded.output_count)} detail="Unsigned transaction outputs" />
        <StatusCard label="Fee" value={decoded.fee_btc === null ? "unknown" : `${decoded.fee_btc.toFixed(8)} BTC`} detail="Known after funding" />
        <StatusCard label="Next role" value={decoded.next_role ?? "unknown"} detail={decoded.is_complete ? "Complete" : "Still in progress"} />
      </div>
      <CommandExplanationCard
        title="PSBT decode"
        command={decoded.cli_commands.join("\n")}
        rpcMethod={decoded.rpc_methods.join(", ")}
        parameters="[psbt]"
        explanation={decoded.explanation}
        concepts={decoded.concepts}
        rawJson={decoded.raw}
      />
    </div>
  );
}

function CreateResult({ result }: { result: PsbtCreateResponse }) {
  return (
    <CommandExplanationCard
      title="Funded PSBT"
      command={result.cli_commands.join("\n")}
      rpcMethod={result.rpc_methods.join(", ")}
      parameters={`["${result.recipient_address}", ${result.amount_btc}]`}
      explanation={result.explanation}
      concepts={result.concepts}
      rawJson={result.raw}
    />
  );
}

function ProcessResult({ result }: { result: PsbtProcessResponse }) {
  return (
    <CommandExplanationCard
      title="Wallet-processed PSBT"
      command={result.cli_commands.join("\n")}
      rpcMethod={result.rpc_methods.join(", ")}
      parameters={`[psbt, sign=${result.signed}]`}
      explanation={result.explanation}
      concepts={result.concepts}
      rawJson={result.raw}
    />
  );
}

function FinalizeResult({ result }: { result: PsbtFinalizeResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <StatusCard label="Complete" value={result.complete ? "yes" : "no"} detail="All required final scripts present" />
        <StatusCard label="Output" value={result.hex ? "raw hex" : result.psbt ? "final PSBT" : "none"} detail="No broadcast is performed" />
      </div>
      {result.hex || result.psbt ? (
        <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">{result.hex ? "Raw transaction hex" : "Final PSBT"}</h2>
          <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100">
            <code>{result.hex ?? result.psbt}</code>
          </pre>
        </section>
      ) : null}
      <CommandExplanationCard
        title="PSBT finalize"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters="[psbt]"
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}
