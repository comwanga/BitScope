"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import {
  ScriptOpcode,
  ScriptTemplateResponse,
  ScriptTestResponse,
  createScriptTemplate,
  testScriptSpend
} from "@/lib/api";

const SAMPLE_PUBKEY = "02aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const SAMPLE_FALLBACK_PUBKEY = "03bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const SAMPLE_PUBKEY_HASH = "89abcdefabbaabbaabbaabbaabbaabbaabbaabba";
const SAMPLE_HASH = "1111111111111111111111111111111111111111111111111111111111111111";

const TEMPLATE_LABELS: Record<string, string> = {
  p2pkh: "P2PKH",
  hashlock: "Hashlock",
  conditional: "Conditional"
};

export function ScriptLab() {
  const [template, setTemplate] = useState("p2pkh");
  const [pubkeyHex, setPubkeyHex] = useState(SAMPLE_PUBKEY);
  const [fallbackPubkeyHex, setFallbackPubkeyHex] = useState(SAMPLE_FALLBACK_PUBKEY);
  const [pubkeyHashHex, setPubkeyHashHex] = useState(SAMPLE_PUBKEY_HASH);
  const [hashHex, setHashHex] = useState(SAMPLE_HASH);
  const [transactionHex, setTransactionHex] = useState("");
  const [templateResult, setTemplateResult] = useState<ScriptTemplateResponse | null>(null);
  const [testResult, setTestResult] = useState<ScriptTestResponse | null>(null);
  const [error, setError] = useState("");
  const [templateLoading, setTemplateLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);

  async function submitTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTemplateLoading(true);
    setError("");
    try {
      setTemplateResult(await createScriptTemplate(template, pubkeyHex.trim(), fallbackPubkeyHex.trim(), pubkeyHashHex.trim(), hashHex.trim()));
    } catch (caught) {
      setTemplateResult(null);
      setError(caught instanceof Error ? caught.message : "Script template could not be generated.");
    } finally {
      setTemplateLoading(false);
    }
  }

  async function submitTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!transactionHex.trim()) {
      setError("Paste a fully formed transaction hex.");
      return;
    }
    setTestLoading(true);
    setError("");
    try {
      setTestResult(await testScriptSpend(transactionHex.trim()));
    } catch (caught) {
      setTestResult(null);
      setError(caught instanceof Error ? caught.message : "Transaction could not be tested.");
    } finally {
      setTestLoading(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Script design lab</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Build and test Bitcoin Script templates</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Compare conditional branches, P2SH/P2WSH wrappers, hashlocks, and full transaction validation through Bitcoin Core RPC.
        </p>
      </header>

      <WarningBox title="Script testing boundary">
        <p>
          Bitcoin Core decodes scripts and validates complete transactions. This lab builds redeem-script templates, then uses
          <code className="mx-1 rounded bg-stone-100 px-1 font-mono text-sm">testmempoolaccept</code>
          when you provide a full spending transaction.
        </p>
      </WarningBox>

      {error ? (
        <WarningBox title="Script lab action unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(18rem,24rem)_1fr]">
        <form onSubmit={submitTemplate} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div>
            <p className="text-sm font-semibold uppercase text-forest">Template builder</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">Choose a script pattern</h2>
          </div>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Template
            <select
              value={template}
              onChange={(event) => setTemplate(event.target.value)}
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
            >
              <option value="p2pkh">P2PKH</option>
              <option value="hashlock">Hashlock + signature</option>
              <option value="conditional">IF/ELSE signature branches</option>
            </select>
          </label>

          {template === "p2pkh" ? <TextField label="Public key hash" value={pubkeyHashHex} onChange={setPubkeyHashHex} /> : null}
          {template === "hashlock" ? (
            <>
              <TextField label="SHA256 hash" value={hashHex} onChange={setHashHex} />
              <TextField label="Public key" value={pubkeyHex} onChange={setPubkeyHex} />
            </>
          ) : null}
          {template === "conditional" ? (
            <>
              <TextField label="Primary public key" value={pubkeyHex} onChange={setPubkeyHex} />
              <TextField label="Fallback public key" value={fallbackPubkeyHex} onChange={setFallbackPubkeyHex} />
            </>
          ) : null}

          <button
            type="submit"
            disabled={templateLoading}
            className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
          >
            {templateLoading ? "Generating" : "Generate script"}
          </button>
        </form>

        <form onSubmit={submitTest} className="space-y-4 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div>
            <p className="text-sm font-semibold uppercase text-forest">Spend validator</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">Test a complete transaction</h2>
          </div>
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Raw transaction hex
            <textarea
              value={transactionHex}
              onChange={(event) => setTransactionHex(event.target.value)}
              className="min-h-44 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
              spellCheck={false}
            />
          </label>
          <button
            type="submit"
            disabled={testLoading}
            className="w-full rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
          >
            {testLoading ? "Testing" : "Run testmempoolaccept"}
          </button>
        </form>
      </div>

      {templateResult ? <TemplateResult result={templateResult} /> : <EmptyTemplateState label={TEMPLATE_LABELS[template]} />}
      {testResult ? <TestResult result={testResult} /> : null}
    </div>
  );
}

function TemplateResult({ result }: { result: ScriptTemplateResponse }) {
  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Template" value={TEMPLATE_LABELS[result.template] ?? result.template} detail="Redeem-script pattern" />
        <StatusCard label="Type" value={result.script_type ?? "nonstandard"} detail="Bitcoin Core classification" />
        <StatusCard label="Opcodes" value={String(result.opcodes.length)} detail="Parsed script elements" />
        <StatusCard label="P2SH wrapper" value={result.p2sh ? "available" : "unavailable"} detail="Nested address from decodescript" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Generated script</h2>
        <Field label="Hex" value={result.script_hex} />
        <Field label="ASM" value={result.asm ?? "unavailable"} />
        <Field label="P2SH" value={result.p2sh ?? "unavailable"} />
        <Field label="SegWit" value={result.segwit ? JSON.stringify(result.segwit, null, 2) : "unavailable"} />
      </section>

      <OpcodeTable opcodes={result.opcodes} />

      <CommandExplanationCard
        title="Script template"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={result.script_hex}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function TestResult({ result }: { result: ScriptTestResponse }) {
  const status = result.accepted === null ? "unknown" : result.accepted ? "accepted" : "rejected";
  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard label="Mempool result" value={status} detail="Consensus and policy preflight" />
        <StatusCard label="RPC method" value="testmempoolaccept" detail="No broadcast performed" />
        <StatusCard label="Transaction bytes" value={String(result.transaction_hex.length / 2)} detail="Raw hex payload size" />
      </div>
      <CommandExplanationCard
        title="Spend validation"
        command={result.cli_commands.join("\n")}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={result.transaction_hex}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </section>
  );
}

function OpcodeTable({ opcodes }: { opcodes: ScriptOpcode[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Stack walkthrough</h2>
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

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-xs text-ink outline-none focus:border-forest sm:text-sm"
        spellCheck={false}
      />
    </label>
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

function EmptyTemplateState({ label }: { label: string }) {
  return (
    <WarningBox title="Generate a script template">
      <p>Select {label}, review the inputs, and generate a redeem script before testing a spend transaction.</p>
    </WarningBox>
  );
}
