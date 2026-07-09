"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { LearningConcept, RpcMethodInfo, fetchLearningConcepts, fetchLearningRpcMethods } from "@/lib/api";

type LibraryState = {
  concepts: LearningConcept[];
  categories: string[];
  rpcMethods: RpcMethodInfo[];
  explanation: string;
};

export function LearningLibrary() {
  const [library, setLibrary] = useState<LibraryState>({
    concepts: [],
    categories: [],
    rpcMethods: [],
    explanation: ""
  });
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function loadLearningLibrary() {
      try {
        const [conceptResponse, rpcResponse] = await Promise.all([fetchLearningConcepts(), fetchLearningRpcMethods()]);
        if (!active) return;
        setLibrary({
          concepts: conceptResponse.concepts,
          categories: conceptResponse.categories,
          rpcMethods: rpcResponse.methods,
          explanation: conceptResponse.explanation
        });
        setSelectedId(conceptResponse.concepts[0]?.id ?? "");
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Learning library could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadLearningLibrary();
    return () => {
      active = false;
    };
  }, []);

  const filteredConcepts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return library.concepts.filter((concept) => {
      const matchesCategory = selectedCategory === "All" || concept.category === selectedCategory;
      const searchable = [
        concept.title,
        concept.category,
        concept.summary,
        concept.details,
        concept.related_rpc_methods.join(" "),
        concept.related_pages.join(" ")
      ]
        .join(" ")
        .toLowerCase();
      return matchesCategory && (!normalizedQuery || searchable.includes(normalizedQuery));
    });
  }, [library.concepts, query, selectedCategory]);

  const selectedConcept = useMemo(() => {
    return filteredConcepts.find((concept) => concept.id === selectedId) ?? filteredConcepts[0] ?? library.concepts[0] ?? null;
  }, [filteredConcepts, library.concepts, selectedId]);

  const relatedRpcMethods = useMemo(() => {
    if (!selectedConcept) return [];
    const names = new Set(selectedConcept.related_rpc_methods);
    return library.rpcMethods.filter((method) => names.has(method.name));
  }, [library.rpcMethods, selectedConcept]);

  function chooseCategory(category: string) {
    setSelectedCategory(category);
    setSelectedId("");
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Learning library</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Connect concepts to Bitcoin Core</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Study the ideas behind each BitScope page, then jump to the matching RPC methods and command-line examples.
        </p>
      </header>

      {error ? (
        <WarningBox title="Learning library unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard label="Concepts" value={loading ? "Loading" : String(library.concepts.length)} detail="Protocol and Bitcoin Core topics" />
        <StatusCard label="Categories" value={loading ? "Loading" : String(library.categories.length)} detail="Grouped learning areas" />
        <StatusCard label="RPC links" value={loading ? "Loading" : String(library.rpcMethods.length)} detail="Safe method reference entries" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <label className="grid gap-2 text-sm font-medium text-stone-600">
            Search concepts
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
              placeholder="Try UTXO, mempool, PSBT, pruning"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {["All", ...library.categories].map((category) => (
              <button
                type="button"
                key={category}
                onClick={() => chooseCategory(category)}
                className={`rounded-md border px-3 py-2 text-sm font-medium ${
                  category === selectedCategory ? "border-forest bg-forest text-white" : "border-stone-300 bg-white text-ink hover:bg-stone-50"
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
        {library.explanation ? <p className="mt-4 text-sm leading-6 text-stone-600">{library.explanation}</p> : null}
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(16rem,22rem)_1fr]">
        <aside className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">Concepts</h2>
            <span className="text-sm text-stone-500">{filteredConcepts.length}</span>
          </div>
          <div className="mt-4 max-h-[38rem] space-y-2 overflow-y-auto pr-1">
            {filteredConcepts.map((concept) => (
              <button
                type="button"
                key={concept.id}
                onClick={() => setSelectedId(concept.id)}
                className={`w-full rounded-md border px-3 py-3 text-left transition ${
                  concept.id === selectedConcept?.id ? "border-forest bg-forest text-white" : "border-stone-300 bg-white text-ink hover:bg-stone-50"
                }`}
              >
                <span className="block text-sm font-semibold">{concept.title}</span>
                <span className={`mt-1 block text-xs ${concept.id === selectedConcept?.id ? "text-stone-100" : "text-stone-500"}`}>
                  {concept.category}
                </span>
                <span className={`mt-2 block text-xs leading-5 ${concept.id === selectedConcept?.id ? "text-stone-100" : "text-stone-600"}`}>
                  {concept.summary}
                </span>
              </button>
            ))}
            {!filteredConcepts.length && !loading ? <p className="text-sm text-stone-600">No concepts match that filter.</p> : null}
          </div>
        </aside>

        <main className="min-w-0 space-y-5">
          {selectedConcept ? <ConceptDetail concept={selectedConcept} rpcMethods={relatedRpcMethods} /> : <EmptyState />}
        </main>
      </div>
    </div>
  );
}

function ConceptDetail({ concept, rpcMethods }: { concept: LearningConcept; rpcMethods: RpcMethodInfo[] }) {
  return (
    <div className="min-w-0 space-y-5">
      <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase text-forest">{concept.category}</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">{concept.title}</h2>
            <p className="mt-3 text-base leading-7 text-stone-700">{concept.summary}</p>
          </div>
          <div className="shrink-0 rounded-md bg-stone-100 px-3 py-2 text-sm font-medium text-stone-700">{concept.related_rpc_methods.length} RPC links</div>
        </div>
        <p className="mt-5 text-sm leading-7 text-stone-700">{concept.details}</p>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h3 className="text-lg font-semibold text-ink">CLI examples</h3>
          <div className="mt-3 space-y-3">
            {concept.cli_examples.map((example) => (
              <pre key={example} className="overflow-x-auto rounded-md bg-ink p-3 text-xs leading-5 text-stone-100">
                <code>{example}</code>
              </pre>
            ))}
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
          <h3 className="text-lg font-semibold text-ink">Related pages</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {concept.related_pages.map((page) => (
              <Link key={page} href={page} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50">
                {page === "/" ? "Dashboard" : page}
              </Link>
            ))}
          </div>
        </section>
      </div>

      {concept.cautions.length ? (
        <WarningBox title="Watch this edge">
          <ul className="list-disc space-y-1 pl-5">
            {concept.cautions.map((caution) => (
              <li key={caution}>{caution}</li>
            ))}
          </ul>
        </WarningBox>
      ) : null}

      <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <h3 className="text-lg font-semibold text-ink">Related RPC methods</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {concept.related_rpc_methods.map((methodName) => {
            const method = rpcMethods.find((item) => item.name === methodName);
            return (
              <div key={methodName} className="min-w-0 rounded-md border border-stone-200 bg-white p-3">
                <div className="break-all font-mono text-sm font-semibold text-ink">{methodName}</div>
                <p className="mt-2 text-sm leading-6 text-stone-600">
                  {method?.description ?? "Used by Bitcoin Core for this concept; it may be shown on another BitScope page but is not runnable from the safe RPC explorer."}
                </p>
                {method ? (
                  <pre className="mt-3 overflow-x-auto rounded-md bg-stone-100 p-2 text-xs leading-5 text-stone-700">
                    <code>{JSON.stringify(method.example_params, null, 2)}</code>
                  </pre>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Learning library loading">
      <p>The concept catalog is loading from the BitScope backend.</p>
    </WarningBox>
  );
}
