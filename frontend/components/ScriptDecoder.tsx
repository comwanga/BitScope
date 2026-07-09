"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { DecodeScriptResponse, ScriptOpcode, decodeScript } from "@/lib/api";

const SAMPLE_SCRIPTS = [
  {
    label: "P2PKH",
    hex: "76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"
  },
  {
    label: "P2WPKH",
    hex: "001489abcdefabbaabbaabbaabbaabbaabbaabbaabba"
  },
  {
    label: "OP_RETURN",
    hex: "6a0d42697453636f7065206c6162"
  }
];

export function ScriptDecoder() {
  const [scriptHex, setScriptHex] = useState(SAMPLE_SCRIPTS[0].hex);
  const [decoded, setDecoded] = useState<DecodeScriptResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = scriptHex.trim();
    if (!trimmed) {
      setError("Enter script hex.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setDecoded(await decodeScript(trimmed));
    } catch (caught) {
      setDecoded(null);
      setError(caught instanceof Error ? caught.message : "Script hex could not be decoded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Script decoder</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Decode Bitcoin Script hex</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Turn raw script bytes into asm, standard script metadata, addresses, and opcode-by-opcode stack hints.
        </p>
      </header>

      <form onSubmit={submit} className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap gap-2">
          {SAMPLE_SCRIPTS.map((sample) => (
            <button
              type="button"
              key={sample.label}
              onClick={() => setScriptHex(sample.hex)}
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50"
            >
              {sample.label}
            </button>
          ))}
        </div>
        <label className="mt-4 grid gap-2 text-sm font-medium text-stone-600">
          Script hex
          <textarea
            value={scriptHex}
            onChange={(event) => setScriptHex(event.target.value)}
            className="min-h-32 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
            spellCheck={false}
          />
        </label>
        <div className="mt-4 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
          >
            {loading ? "Decoding" : "Decode script"}
          </button>
        </div>
      </form>

      {error ? (
        <WarningBox title="Script unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {decoded ? <ScriptResult decoded={decoded} /> : <EmptyState />}
    </div>
  );
}

function ScriptResult({ decoded }: { decoded: DecodeScriptResponse }) {
  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Type" value={decoded.script_type ?? "unknown"} detail="Bitcoin Core script classification" />
        <StatusCard label="Opcodes" value={String(decoded.opcodes.length)} detail="Parsed bytecode elements" />
        <StatusCard label="Required sigs" value={decoded.req_sigs === null ? "unknown" : String(decoded.req_sigs)} detail="Legacy standard metadata" />
        <StatusCard label="Addresses" value={String(decoded.addresses.length)} detail="Address extraction when standard" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Decoded script</h2>
        <Field label="Hex" value={decoded.script_hex} />
        <Field label="ASM" value={decoded.asm ?? "unavailable"} />
        <Field label="P2SH" value={decoded.p2sh ?? "unavailable"} />
        <Field label="SegWit" value={decoded.segwit ? JSON.stringify(decoded.segwit, null, 2) : "unavailable"} />
        <Field label="Addresses" value={decoded.addresses.length ? decoded.addresses.join("\n") : "none"} />
      </section>

      <OpcodeTable opcodes={decoded.opcodes} />

      <CommandExplanationCard
        title="Script decode"
        command={decoded.cli_commands.join("\n")}
        rpcMethod={decoded.rpc_methods.join(", ")}
        parameters={`["${decoded.script_hex}"]`}
        explanation={decoded.explanation}
        concepts={decoded.concepts}
        rawJson={decoded.raw}
      />
    </div>
  );
}

function OpcodeTable({ opcodes }: { opcodes: ScriptOpcode[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Opcode walkthrough</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-[44rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-xs uppercase text-stone-500">
              <th className="py-2 pr-3 font-semibold">Offset</th>
              <th className="py-2 pr-3 font-semibold">Opcode</th>
              <th className="py-2 pr-3 font-semibold">Data</th>
              <th className="py-2 font-semibold">Meaning</th>
            </tr>
          </thead>
          <tbody>
            {opcodes.map((opcode) => (
              <tr key={`${opcode.offset}-${opcode.opcode}`} className="border-b border-stone-100 align-top">
                <td className="py-3 pr-3 font-mono text-stone-700">{opcode.offset}</td>
                <td className="py-3 pr-3 font-mono font-semibold text-ink">{opcode.opcode}</td>
                <td className="max-w-sm break-all py-3 pr-3 font-mono text-xs text-stone-700">
                  {opcode.data_hex ?? "none"}
                  {opcode.data_length === null ? null : <span className="ml-2 text-stone-500">({opcode.data_length} bytes)</span>}
                </td>
                <td className="py-3 text-stone-700">{opcode.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[9rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="whitespace-pre-wrap break-all font-mono text-stone-800">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Start with a sample">
      <p>Choose one of the sample scripts or paste a scriptPubKey hex value from the transaction explorer.</p>
    </WarningBox>
  );
}
