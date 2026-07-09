"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { RpcExecuteResponse, RpcMethodInfo, executeRpc, fetchRpcMethods } from "@/lib/api";

export function RpcExplorer() {
  const [methods, setMethods] = useState<RpcMethodInfo[]>([]);
  const [selectedName, setSelectedName] = useState("");
  const [paramsText, setParamsText] = useState("[]");
  const [result, setResult] = useState<RpcExecuteResponse | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [executeError, setExecuteError] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadCatalog() {
      try {
        const catalog = await fetchRpcMethods();
        if (!active) return;
        setMethods(catalog.methods);
        const first = catalog.methods[0];
        if (first) {
          setSelectedName(first.name);
          setParamsText(JSON.stringify(first.example_params, null, 2));
        }
      } catch (caught) {
        if (active) setCatalogError(caught instanceof Error ? caught.message : "RPC method catalog could not be loaded.");
      } finally {
        if (active) setLoadingCatalog(false);
      }
    }

    loadCatalog();
    return () => {
      active = false;
    };
  }, []);

  const selectedMethod = useMemo(
    () => methods.find((method) => method.name === selectedName) ?? null,
    [methods, selectedName]
  );

  const groupedMethods = useMemo(() => {
    return methods.reduce<Record<string, RpcMethodInfo[]>>((groups, method) => {
      groups[method.category] = [...(groups[method.category] ?? []), method];
      return groups;
    }, {});
  }, [methods]);

  function chooseMethod(method: RpcMethodInfo) {
    setSelectedName(method.name);
    setParamsText(JSON.stringify(method.example_params, null, 2));
    setExecuteError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMethod) {
      setExecuteError("Choose an RPC method.");
      return;
    }

    let parsedParams: unknown;
    try {
      parsedParams = JSON.parse(paramsText || "[]");
    } catch {
      setExecuteError("RPC params must be valid JSON. Use an array for positional params or an object for named params.");
      return;
    }

    if (!Array.isArray(parsedParams) && !isPlainObject(parsedParams)) {
      setExecuteError("RPC params must be a JSON array or object.");
      return;
    }

    setExecuting(true);
    setExecuteError("");
    try {
      setResult(await executeRpc(selectedMethod.name, parsedParams));
    } catch (caught) {
      setResult(null);
      setExecuteError(caught instanceof Error ? caught.message : "RPC method could not be executed.");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">RPC explorer</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Run read-only Bitcoin Core RPC</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Choose a safe method, edit the JSON parameters, and compare the response with the exact `bitcoin-cli` command.
        </p>
      </header>

      <WarningBox title="Read-only guardrail">
        <p>
          This screen only runs cataloged read-only RPC calls. Spending, signing, broadcasting, node shutdown, and wallet mutation methods are rejected by the backend.
        </p>
      </WarningBox>

      {catalogError ? (
        <WarningBox title="RPC catalog unavailable">
          <p>{catalogError}</p>
        </WarningBox>
      ) : null}

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(16rem,22rem)_1fr]">
        <aside className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">Methods</h2>
            <span className="text-sm text-stone-500">{loadingCatalog ? "Loading" : `${methods.length} available`}</span>
          </div>
          <div className="mt-4 max-h-[34rem] space-y-5 overflow-y-auto pr-1">
            {Object.entries(groupedMethods).map(([category, categoryMethods]) => (
              <section key={category}>
                <h3 className="text-xs font-semibold uppercase text-stone-500">{category}</h3>
                <div className="mt-2 grid gap-2">
                  {categoryMethods.map((method) => (
                    <button
                      type="button"
                      key={method.name}
                      onClick={() => chooseMethod(method)}
                      className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                        method.name === selectedName
                          ? "border-forest bg-forest text-white"
                          : "border-stone-300 bg-white text-ink hover:bg-stone-50"
                      }`}
                    >
                      <span className="block break-all font-mono text-xs font-semibold">{method.name}</span>
                      <span className={`mt-1 block text-xs ${method.name === selectedName ? "text-stone-100" : "text-stone-600"}`}>
                        {method.description}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </aside>

        <main className="min-w-0 space-y-5">
          <form onSubmit={submit} className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
            <div className="grid gap-4 lg:grid-cols-[1fr_minmax(14rem,18rem)]">
              <div className="min-w-0">
                <h2 className="break-all font-mono text-xl font-semibold text-ink">{selectedMethod?.name ?? "Choose a method"}</h2>
                <p className="mt-2 text-sm leading-6 text-stone-600">{selectedMethod?.description ?? "Load the method catalog to begin."}</p>
              </div>
              <div className="min-w-0 rounded-md bg-stone-100 p-3 text-sm text-stone-700">
                <div className="font-semibold text-stone-500">Example params</div>
                <pre className="mt-2 overflow-x-auto text-xs leading-5">
                  <code>{JSON.stringify(selectedMethod?.example_params ?? [], null, 2)}</code>
                </pre>
              </div>
            </div>

            <label className="mt-4 grid gap-2 text-sm font-medium text-stone-600">
              JSON params
              <textarea
                value={paramsText}
                onChange={(event) => setParamsText(event.target.value)}
                className="min-h-44 resize-y rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest"
                spellCheck={false}
              />
            </label>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-stone-600">Use `[]` for no parameters. Positional RPC params use arrays; named params use objects.</p>
              <button
                type="submit"
                disabled={executing || !selectedMethod}
                className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
              >
                {executing ? "Running" : "Run RPC"}
              </button>
            </div>
          </form>

          {executeError ? (
            <WarningBox title="RPC call unavailable">
              <p>{executeError}</p>
            </WarningBox>
          ) : null}

          {result ? <RpcResult result={result} /> : <EmptyState />}
        </main>
      </div>
    </div>
  );
}

function RpcResult({ result }: { result: RpcExecuteResponse }) {
  return (
    <div className="min-w-0 space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard label="Method" value={result.method} detail="Bitcoin Core RPC name" />
        <StatusCard label="Category" value={result.category} detail="Learning area" />
        <StatusCard label="Params" value={Array.isArray(result.params) ? String(result.params.length) : "named"} detail="JSON-RPC parameter shape" />
      </div>

      <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold text-ink">Result</h2>
        <pre className="mt-4 max-h-[38rem] overflow-auto rounded-md bg-ink p-4 text-xs leading-5 text-stone-100">
          <code>{JSON.stringify(result.result, null, 2)}</code>
        </pre>
      </section>

      <CommandExplanationCard
        title="RPC execution"
        command={result.cli_command}
        rpcMethod={result.rpc_methods.join(", ")}
        parameters={JSON.stringify(result.params, null, 2)}
        explanation={result.explanation}
        concepts={result.concepts}
        rawJson={result.raw}
      />
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Pick a method">
      <p>Select a read-only RPC method, check the example params, then run it against your configured Bitcoin Core node.</p>
    </WarningBox>
  );
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
