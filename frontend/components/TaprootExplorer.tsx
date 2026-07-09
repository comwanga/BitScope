"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { TaprootInspectResponse, inspectTaproot } from "@/lib/api";

const SAMPLE_P2TR_SCRIPT = `5120${"11".repeat(32)}`;

export function TaprootExplorer() {
  const [address, setAddress] = useState("");
  const [scriptHex, setScriptHex] = useState(SAMPLE_P2TR_SCRIPT);
  const [result, setResult] = useState<TaprootInspectResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!address.trim() && !scriptHex.trim()) {
      setError("Provide a Taproot address or scriptPubKey hex.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setResult(await inspectTaproot(address.trim(), scriptHex.trim()));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Taproot data could not be inspected.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Taproot lab</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect P2TR outputs</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Identify SegWit v1 Taproot scripts, x-only output keys, and the difference between visible output shape and hidden spend paths.
        </p>
      </header>

      <WarningBox title="Taproot visibility limit">
        <p>A P2TR output reveals the output key. Script-path details are hidden until a transaction spends through that path.</p>
      </WarningBox>

      <form onSubmit={submit} className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="grid gap-4 lg:grid-cols-2">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Address
            <input
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="bc1p... or bcrt1p..."
            />
          </label>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            scriptPubKey hex
            <input
              value={scriptHex}
              onChange={(event) => setScriptHex(event.target.value)}
              className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              placeholder="5120..."
            />
          </label>
        </div>
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={loading} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">
            {loading ? "Inspecting" : "Inspect Taproot"}
          </button>
        </div>
      </form>

      {error ? (
        <WarningBox title="Taproot inspection unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {result ? <TaprootResult result={result} /> : <EmptyState />}
    </div>
  );
}

function TaprootResult({ result }: { result: TaprootInspectResponse }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Taproot" value={result.is_taproot ? "yes" : "no"} detail="P2TR output shape" />
        <StatusCard label="Witness version" value={result.witness_version === null ? "unknown" : String(result.witness_version)} detail="Taproot uses SegWit v1" />
        <StatusCard label="Script type" value={result.script_type ?? "unknown"} detail="Bitcoin Core classification" />
        <StatusCard label="Output key bytes" value={result.output_key ? "32" : "unknown"} detail="X-only public key length" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Taproot details</h2>
        <Field label="Address" value={result.address ?? "not provided"} />
        <Field label="scriptPubKey" value={result.script_hex ?? "unavailable"} />
        <Field label="ASM" value={result.asm ?? "unavailable"} />
        <Field label="Witness program" value={result.witness_program ?? "unavailable"} />
        <Field label="Output key" value={result.output_key ?? "unavailable"} />
      </section>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Spend model</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <InfoPanel title="Key path" text="The common path: spend with a Schnorr signature for the tweaked output key. No script is revealed." />
          <InfoPanel title="Script path" text="A spending transaction can reveal a Taproot leaf script plus control block proving it was committed to by the output key." />
        </div>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">
          {result.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>

      <CommandExplanationCard
        title="Taproot inspection"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify({ address: result.address, script_hex: result.script_hex }, null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function InfoPanel({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-md border border-stone-200 bg-white p-3">
      <div className="font-semibold text-ink">{title}</div>
      <p className="mt-2 text-sm leading-6 text-stone-600">{text}</p>
    </div>
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

function EmptyState() {
  return (
    <WarningBox title="Start with sample script">
      <p>The sample script is a synthetic P2TR scriptPubKey: OP_1 followed by a 32-byte x-only output key.</p>
    </WarningBox>
  );
}
