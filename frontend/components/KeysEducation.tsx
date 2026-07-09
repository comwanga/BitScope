"use client";

import { useEffect, useMemo, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { DescriptorRecipe, DerivationPathInfo, KeyEducationResponse, PsbtFlowStep, fetchKeyEducation } from "@/lib/api";

const PURPOSE_BY_TEMPLATE: Record<string, string> = {
  pkh: "44h",
  "sh-wpkh": "49h",
  wpkh: "84h",
  tr: "86h"
};

const COIN_TYPE_BY_NETWORK: Record<string, string> = {
  mainnet: "0h",
  test: "1h"
};

export function KeysEducation() {
  const [guide, setGuide] = useState<KeyEducationResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [template, setTemplate] = useState("wpkh");
  const [network, setNetwork] = useState("test");
  const [fingerprint, setFingerprint] = useState("f23a9c01");
  const [account, setAccount] = useState(0);
  const [xpub, setXpub] = useState("vpub...");
  const [change, setChange] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await fetchKeyEducation();
        if (active) setGuide(response);
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Key education guide could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  const originPath = useMemo(() => {
    return `${PURPOSE_BY_TEMPLATE[template]}/${COIN_TYPE_BY_NETWORK[network]}/${account}h`;
  }, [template, network, account]);

  const composedDescriptor = useMemo(() => {
    const key = `[${fingerprint.trim() || "f23a9c01"}/${originPath}]${xpub.trim() || "vpub..."}/${change}/*`;
    if (template === "pkh") return `pkh(${key})`;
    if (template === "sh-wpkh") return `sh(wpkh(${key}))`;
    if (template === "tr") return `tr(${key})`;
    return `wpkh(${key})`;
  }, [template, fingerprint, originPath, xpub, change]);

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Key concepts</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Learn descriptors, xpubs, and hardware-wallet PSBT flow</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Study public key material, derivation paths, watch-only wallets, and signer handoff without entering private keys.
        </p>
      </header>

      <WarningBox title="No private keys">
        <p>{guide?.safety_model.message ?? "This page never asks for seed words, private extended keys, WIF keys, or hardware-wallet PINs."}</p>
      </WarningBox>

      {error ? (
        <WarningBox title="Key guide unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Private keys" value={guide?.safety_model.handles_private_keys ? "handled" : "never handled"} detail="Educational boundary" />
        <StatusCard label="Path templates" value={loading ? "loading" : String(guide?.derivation_paths.length ?? 0)} detail="BIP44/49/84/86" />
        <StatusCard label="Descriptors" value={loading ? "loading" : String(guide?.descriptor_recipes.length ?? 0)} detail="Public examples" />
        <StatusCard label="PSBT steps" value={loading ? "loading" : String(guide?.psbt_flow.length ?? 0)} detail="Hardware-wallet flow" />
      </section>

      {guide ? <SafetyPanel guide={guide} /> : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(18rem,24rem)_1fr]">
        <div className="space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div>
            <p className="text-sm font-semibold uppercase text-forest">Descriptor composer</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">Build a public descriptor shape</h2>
          </div>
          <SelectField label="Template" value={template} onChange={setTemplate} options={[["wpkh", "Native SegWit"], ["tr", "Taproot"], ["sh-wpkh", "Nested SegWit"], ["pkh", "Legacy"]]} />
          <SelectField label="Network coin type" value={network} onChange={setNetwork} options={[["test", "Testnet/regtest"], ["mainnet", "Mainnet"]]} />
          <TextField label="Master fingerprint" value={fingerprint} onChange={setFingerprint} />
          <NumberField label="Account" value={account} onChange={setAccount} />
          <TextField label="Extended public key" value={xpub} onChange={setXpub} />
          <SelectField label="Branch" value={String(change)} onChange={(value) => setChange(Number(value))} options={[["0", "Receive"], ["1", "Change"]]} />
        </div>

        <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h2 className="text-lg font-semibold text-ink">Composed descriptor</h2>
          <Field label="Origin path" value={`m/${originPath}`} />
          <Field label="Descriptor" value={composedDescriptor} />
          <Field label="Checksum step" value="Run getdescriptorinfo before import or derivation." />
          <CommandExplanationCard
            title="Descriptor checksum"
            command={`bitcoin-cli getdescriptorinfo '${composedDescriptor}'`}
            rpcMethod="getdescriptorinfo"
            parameters={JSON.stringify([composedDescriptor], null, 2)}
            explanation="Bitcoin Core normalizes descriptors and returns a checksum. Import and derivation commands should use the checksummed descriptor."
            concepts={["Descriptor", "Checksum", "Key origin", "xpub"]}
          />
        </section>
      </section>

      {guide ? (
        <>
          <DerivationTable paths={guide.derivation_paths} />
          <DescriptorRecipes recipes={guide.descriptor_recipes} />
          <PsbtFlow steps={guide.psbt_flow} notes={guide.hardware_wallet_notes} />
          <CommandExplanationCard
            title="Watch-only workflow"
            command={guide.watch_only_commands.join("\n")}
            rpcMethod={guide.rpc_methods.join(", ")}
            parameters="public descriptors only"
            explanation={guide.explanation}
            concepts={guide.concepts}
          />
        </>
      ) : null}
    </div>
  );
}

function SafetyPanel({ guide }: { guide: KeyEducationResponse }) {
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Allowed public material</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {guide.safety_model.allowed_inputs.map((item) => (
            <span key={item} className="rounded-md bg-stone-100 px-3 py-1 text-sm font-medium text-stone-700">{item}</span>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-red-800">Never enter here</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {guide.safety_model.blocked_inputs.map((item) => (
            <span key={item} className="rounded-md bg-white px-3 py-1 text-sm font-medium text-red-700">{item}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

function DerivationTable({ paths }: { paths: DerivationPathInfo[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Derivation path map</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-[48rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-stone-500">
              <th className="py-2 pr-4 font-medium">Purpose</th>
              <th className="py-2 pr-4 font-medium">Path</th>
              <th className="py-2 pr-4 font-medium">Script</th>
              <th className="py-2 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {paths.map((path) => (
              <tr key={path.path} className="border-b border-stone-200 align-top last:border-0">
                <td className="py-3 pr-4 font-semibold text-ink">{path.purpose}</td>
                <td className="py-3 pr-4 font-mono text-xs text-stone-800">{path.path}</td>
                <td className="py-3 pr-4 text-stone-800">{path.script_type}</td>
                <td className="py-3 text-stone-700">{path.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DescriptorRecipes({ recipes }: { recipes: DescriptorRecipe[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Public descriptor recipes</h2>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {recipes.map((recipe) => (
          <article key={recipe.name} className="rounded-md border border-stone-200 bg-white p-4">
            <h3 className="font-semibold text-ink">{recipe.name}</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">{recipe.purpose}</p>
            <Field label="Receive" value={recipe.descriptor} />
            <Field label="Change" value={recipe.change_descriptor} />
          </article>
        ))}
      </div>
    </section>
  );
}

function PsbtFlow({ steps, notes }: { steps: PsbtFlowStep[]; notes: string[] }) {
  return (
    <section className="space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Hardware-wallet PSBT handoff</h2>
      <div className="grid gap-3">
        {steps.map((step) => (
          <article key={step.step} className="grid gap-3 rounded-md border border-stone-200 bg-white p-4 lg:grid-cols-[4rem_10rem_1fr]">
            <div className="font-mono text-2xl font-semibold text-forest">{step.step}</div>
            <div>
              <div className="font-semibold text-ink">{step.role}</div>
              <div className="mt-1 font-mono text-xs text-stone-500">{step.bitcoin_core_rpc}</div>
            </div>
            <div className="text-sm leading-6 text-stone-700">
              <p>{step.action}</p>
              <p className="mt-2 font-medium text-stone-800">{step.private_key_boundary}</p>
            </div>
          </article>
        ))}
      </div>
      <WarningBox title="Hardware-wallet review">
        <ul className="space-y-1">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </WarningBox>
    </section>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" />
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <input type="number" min={0} value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest" />
    </label>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-600">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest">
        {options.map(([optionValue, labelValue]) => (
          <option key={optionValue} value={optionValue}>{labelValue}</option>
        ))}
      </select>
    </label>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3 grid gap-1 border-b border-stone-200 pb-3 text-sm md:grid-cols-[6rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-xs leading-5 text-stone-800">{value}</div>
    </div>
  );
}
