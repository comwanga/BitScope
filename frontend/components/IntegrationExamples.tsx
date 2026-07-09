"use client";

import { useEffect, useMemo, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { RpcExamplesResponse, RpcLanguageExample, ZmqStatusResponse, fetchRpcExamples, fetchZmqStatus } from "@/lib/api";

export function IntegrationExamples() {
  const [zmq, setZmq] = useState<ZmqStatusResponse | null>(null);
  const [examples, setExamples] = useState<RpcExamplesResponse | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [zmqStatus, rpcExamples] = await Promise.all([fetchZmqStatus(), fetchRpcExamples()]);
        if (!active) return;
        setZmq(zmqStatus);
        setExamples(rpcExamples);
        setSelectedLanguage(rpcExamples.examples[0]?.language ?? "");
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Integration examples could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  const selectedExample = useMemo(() => {
    return examples?.examples.find((example) => example.language === selectedLanguage) ?? examples?.examples[0] ?? null;
  }, [examples, selectedLanguage]);

  async function copyExample(example: RpcLanguageExample) {
    await navigator.clipboard.writeText(example.code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Node integrations</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Connect software to Bitcoin Core</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Compare JSON-RPC clients, wallet RPC paths, polling-backed live updates, and optional ZMQ event streams.
        </p>
      </header>

      <WarningBox title="Keep RPC credentials server-side">
        <p>
          These examples use placeholders. Do not ship Bitcoin Core RPC usernames or passwords to browser code, mobile apps, public repos, or logs.
        </p>
      </WarningBox>

      {error ? (
        <WarningBox title="Integration data unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Examples" value={loading ? "loading" : String(examples?.examples.length ?? 0)} detail="Language snippets" />
        <StatusCard label="RPC URL" value={examples?.rpc_url ?? "unavailable"} detail="Backend-side Bitcoin Core URL" />
        <StatusCard label="ZMQ config" value={zmq?.configured ? "configured" : "not set"} detail="Optional rawblock/rawtx endpoints" />
        <StatusCard label="Live stream" value={zmq?.sse_endpoint ?? "/api/live/node"} detail="Polling-backed SSE endpoint" />
      </section>

      {zmq ? <ZmqPanel zmq={zmq} /> : null}

      {examples && selectedExample ? (
        <section className="grid gap-5 xl:grid-cols-[minmax(14rem,18rem)_1fr]">
          <aside className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
            <h2 className="text-lg font-semibold text-ink">Languages</h2>
            <div className="mt-4 grid gap-2">
              {examples.examples.map((example) => (
                <button
                  type="button"
                  key={example.language}
                  onClick={() => setSelectedLanguage(example.language)}
                  className={`rounded-md border px-3 py-2 text-left text-sm ${
                    example.language === selectedExample.language
                      ? "border-forest bg-forest text-white"
                      : "border-stone-300 bg-white text-ink hover:bg-stone-50"
                  }`}
                >
                  <span className="font-semibold">{example.language}</span>
                  <span className={`mt-1 block text-xs ${example.language === selectedExample.language ? "text-stone-100" : "text-stone-600"}`}>
                    {example.title}
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <main className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase text-forest">{selectedExample.language}</p>
                <h2 className="mt-2 text-xl font-semibold text-ink">{selectedExample.title}</h2>
                <p className="mt-2 text-sm leading-6 text-stone-600">{selectedExample.description}</p>
              </div>
              <button
                type="button"
                onClick={() => void copyExample(selectedExample)}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-ink hover:bg-stone-50"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="mt-4 max-h-[34rem] overflow-auto rounded-md bg-ink p-4 text-xs leading-5 text-stone-100">
              <code>{selectedExample.code}</code>
            </pre>
          </main>
        </section>
      ) : null}

      {examples ? (
        <CommandExplanationCard
          title="Integration model"
          command={examples.cli_commands.join("\n")}
          rpcMethod={examples.rpc_methods.join(", ")}
          parameters={examples.wallet_rpc_path}
          explanation={examples.explanation}
          concepts={examples.concepts}
        />
      ) : null}
    </div>
  );
}

function ZmqPanel({ zmq }: { zmq: ZmqStatusResponse }) {
  return (
    <section className="space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard label="Raw blocks" value={zmq.rawblock_endpoint ?? "not configured"} detail="BITCOIN_ZMQ_RAWBLOCK" />
        <StatusCard label="Raw txs" value={zmq.rawtx_endpoint ?? "not configured"} detail="BITCOIN_ZMQ_RAWTX" />
        <StatusCard label="Listener" value={zmq.zmq_listener_available ? "available" : "planned"} detail="Current live page uses SSE polling" />
      </div>

      {zmq.warnings.length ? (
        <WarningBox title="ZMQ setup needed">
          <ul className="space-y-1">
            {zmq.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </WarningBox>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">bitcoin.conf</h2>
          <pre className="mt-3 overflow-x-auto rounded-md bg-ink p-4 text-xs leading-5 text-stone-100">
            <code>{zmq.recommended_bitcoin_conf.join("\n")}</code>
          </pre>
        </div>
        <CommandExplanationCard
          title="ZMQ status"
          command={zmq.cli_commands.join("\n")}
          rpcMethod={zmq.rpc_methods.join(", ")}
          parameters={zmq.sse_endpoint}
          explanation={zmq.explanation}
          concepts={zmq.concepts}
          rawJson={zmq.raw}
        />
      </div>
    </section>
  );
}
