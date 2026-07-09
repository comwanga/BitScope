"use client";

import { FormEvent, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { BlockResponse, MerkleLayer, fetchBlock } from "@/lib/api";

export function BlockExplorer() {
  const [query, setQuery] = useState("0");
  const [block, setBlock] = useState<BlockResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a block height or block hash.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      setBlock(await fetchBlock(trimmed));
    } catch (caught) {
      setBlock(null);
      setError(caught instanceof Error ? caught.message : "That block could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Block explorer</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Explore a block</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Look up a block by height or hash using your local Bitcoin Core node.
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:flex-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-3 py-2 text-ink outline-none focus:border-forest"
          placeholder="Block height or hash"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70"
        >
          {loading ? "Loading" : "Search"}
        </button>
      </form>

      {error ? (
        <WarningBox title="Block unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {block ? <BlockResult block={block} /> : <EmptyState />}
    </div>
  );
}

function BlockResult({ block }: { block: BlockResponse }) {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Height" value={formatNullableNumber(block.height)} detail="Position in the active chain" />
        <StatusCard label="Confirmations" value={formatNullableNumber(block.confirmations)} detail="Blocks built on top" />
        <StatusCard label="Transactions" value={formatNullableNumber(block.transaction_count)} detail="Transaction IDs in this block" />
        <StatusCard label="Weight" value={formatNullableNumber(block.weight)} detail="SegWit block weight units" />
        <StatusCard label="Size" value={formatBytes(block.size)} detail="Serialized block size" />
        <StatusCard label="Stripped size" value={formatBytes(block.stripped_size)} detail="Size without witness data" />
        <StatusCard label="Difficulty" value={formatDifficulty(block.difficulty)} detail="Proof-of-work target scale" />
        <StatusCard label="Nonce" value={formatNullableNumber(block.nonce)} detail="Header field varied by miners" />
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Block header</h2>
        <div className="mt-4 grid gap-3 text-sm">
          <Field label="Hash" value={block.hash} />
          <Field label="Previous block" value={block.previous_block_hash ?? "genesis block or unavailable"} />
          <Field label="Next block" value={block.next_block_hash ?? "not known by this node yet"} />
          <Field label="Merkle root" value={block.merkle_root ?? "unavailable"} />
          <Field label="Version" value={`${block.version ?? "unavailable"} (${block.version_hex ?? "no version hex"})`} />
          <Field label="Bits" value={block.bits ?? "unavailable"} />
          <Field label="Timestamp" value={formatTimestamp(block.timestamp)} />
        </div>
      </section>

      <MerkleTreeView block={block} />

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Transaction IDs</h2>
        <div className="mt-4 max-h-96 space-y-2 overflow-auto">
          {block.transaction_ids.map((txid) => (
            <a
              key={txid}
              href={`/transactions?txid=${encodeURIComponent(txid)}`}
              className="block break-all rounded-md bg-stone-100 px-3 py-2 font-mono text-xs text-ink hover:bg-stone-200"
            >
              {txid}
            </a>
          ))}
        </div>
      </section>

      <CommandExplanationCard
        title="Block lookup"
        command={block.cli_commands.join("\n")}
        rpcMethod={block.rpc_methods.join(", ")}
        parameters={block.query_type === "height" ? `[${block.query}] then ["${block.hash}"]` : `["${block.hash}"]`}
        explanation={block.explanation}
        concepts={block.concepts}
        rawJson={block.raw}
      />
    </div>
  );
}

function MerkleTreeView({ block }: { block: BlockResponse }) {
  if (!block.merkle_layers.length) {
    return (
      <WarningBox title="Merkle tree unavailable">
        <p>Bitcoin Core did not return enough transaction ids to recompute the Merkle layers for this block.</p>
      </WarningBox>
    );
  }

  const root = block.merkle_layers.at(-1)?.nodes[0]?.hash ?? "unavailable";

  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink">Merkle commitment</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Transaction ids are paired, double-SHA256 hashed, and folded upward until one root commits to the whole block.
          </p>
        </div>
        <div className={`rounded-md px-3 py-2 text-sm font-semibold ${block.merkle_verified ? "bg-forest text-white" : "bg-stone-200 text-stone-700"}`}>
          {block.merkle_verified ? "Root verified" : "Root not verified"}
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm">
        <Field label="Computed root" value={root} />
        <Field label="Header root" value={block.merkle_root ?? "unavailable"} />
      </div>

      <div className="mt-5 space-y-4 overflow-x-auto pb-2">
        {block.merkle_layers.map((layer) => (
          <MerkleLayerRow key={layer.level} layer={layer} />
        ))}
      </div>
    </section>
  );
}

function MerkleLayerRow({ layer }: { layer: MerkleLayer }) {
  const visibleNodes = layer.nodes.slice(0, 8);
  const hiddenCount = Math.max(0, layer.nodes.length - visibleNodes.length);

  return (
    <div className="min-w-[42rem] rounded-md border border-stone-200 bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">{layer.label}</div>
          <div className="text-xs text-stone-500">Level {layer.level} · {layer.nodes.length} node{layer.nodes.length === 1 ? "" : "s"}</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 xl:grid-cols-8">
        {visibleNodes.map((node, index) => (
          <div key={`${layer.level}-${node.hash}-${index}`} className="min-w-0 rounded-md bg-stone-100 p-2">
            <div className="truncate font-mono text-xs text-ink" title={node.hash}>{node.hash}</div>
            {node.duplicated ? <div className="mt-1 text-[11px] font-semibold uppercase text-forest">duplicated</div> : null}
          </div>
        ))}
        {hiddenCount ? (
          <div className="rounded-md bg-stone-100 p-2 text-xs font-medium text-stone-600">
            +{hiddenCount} more
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-stone-200 pb-3 md:grid-cols-[10rem_1fr]">
      <div className="font-medium text-stone-500">{label}</div>
      <div className="break-all font-mono text-stone-800">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <WarningBox title="Start with the genesis block">
      <p>Search for block height 0, or paste a block hash from the node dashboard once your node is running.</p>
    </WarningBox>
  );
}

function formatNullableNumber(value: number | null) {
  return value === null ? "unavailable" : new Intl.NumberFormat("en-US").format(value);
}

function formatBytes(value: number | null) {
  if (value === null) {
    return "unavailable";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let scaled = value / 1024;
  let unitIndex = 0;
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024;
    unitIndex += 1;
  }
  return `${scaled.toFixed(1)} ${units[unitIndex]}`;
}

function formatDifficulty(value: number | null) {
  return value === null ? "unavailable" : value.toLocaleString("en-US", { maximumSignificantDigits: 8 });
}

function formatTimestamp(value: number | null) {
  return value === null ? "unavailable" : new Date(value * 1000).toISOString();
}
