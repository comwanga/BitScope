"use client";

import { useState } from "react";

type CommandExplanationCardProps = {
  title: string;
  command: string;
  rpcMethod: string;
  explanation: string;
  parameters?: string;
  concepts?: string[];
  bipReferences?: string[];
  rawJson?: unknown;
};

export function CommandExplanationCard({
  title,
  command,
  rpcMethod,
  explanation,
  parameters = "[]",
  concepts = [],
  bipReferences = [],
  rawJson
}: CommandExplanationCardProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copyCommand() {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">{explanation}</p>
        </div>
        <div className="max-w-full break-words rounded-md bg-forest px-3 py-1 text-sm font-medium text-white">{rpcMethod}</div>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <pre className="min-w-0 flex-1 overflow-x-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100 sm:p-4 sm:text-sm">
          <code>{command}</code>
        </pre>
        <button
          type="button"
          onClick={copyCommand}
          className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="min-w-0">
          <div className="text-sm font-medium text-stone-500">RPC parameters</div>
          <code className="mt-1 block overflow-x-auto rounded-md bg-stone-100 px-3 py-2 text-sm text-stone-700">{parameters}</code>
        </div>
        {concepts.length ? (
          <div className="min-w-0">
            <div className="text-sm font-medium text-stone-500">Related concepts</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {concepts.map((concept) => (
                <span key={concept} className="rounded-md bg-stone-100 px-2 py-1 text-xs font-medium text-stone-700">
                  {concept}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
      {bipReferences.length ? (
        <div className="mt-4 text-sm text-stone-600">BIP references: {bipReferences.join(", ")}</div>
      ) : null}
      {rawJson === undefined ? null : (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowRaw((current) => !current)}
            className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50"
          >
            {showRaw ? "Hide raw JSON" : "Show raw JSON"}
          </button>
          {showRaw ? (
            <pre className="mt-3 max-h-[32rem] overflow-auto rounded-md bg-ink p-4 text-xs leading-5 text-stone-100">
              <code>{JSON.stringify(rawJson, null, 2)}</code>
            </pre>
          ) : null}
        </div>
      )}
    </section>
  );
}
