import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { fetchNodeStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let nodeStatus: Awaited<ReturnType<typeof fetchNodeStatus>> | null = null;
  let errorMessage = "";

  try {
    nodeStatus = await fetchNodeStatus();
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : "Bitcoin Core node status is not available.";
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Node status dashboard</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Your Bitcoin Core node</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Live chain, network, and mempool state from Bitcoin Core RPC.
        </p>
      </header>

      {nodeStatus ? (
        <>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md bg-forest px-3 py-1 text-sm font-medium text-white">
              {nodeStatus.chain ?? "unknown chain"}
            </span>
            <span className="rounded-md bg-stone-200 px-3 py-1 text-sm font-medium text-stone-700">
              {nodeStatus.initial_block_download ? "syncing" : "ready"}
            </span>
            <span className="rounded-md bg-stone-200 px-3 py-1 text-sm font-medium text-stone-700">
              {nodeStatus.pruned ? "pruned" : "full blocks available"}
            </span>
          </div>

          {nodeStatus.warnings.length ? (
            <WarningBox title="Node warning">
              {nodeStatus.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </WarningBox>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatusCard label="Block height" value={formatNumber(nodeStatus.blocks)} detail="Current validated block count" />
            <StatusCard label="Headers" value={formatNumber(nodeStatus.headers)} detail="Best known header count" />
            <StatusCard
              label="Sync progress"
              value={formatPercent(nodeStatus.verification_progress)}
              detail="Bitcoin Core verification progress"
            />
            <StatusCard label="Peers" value={formatNumber(nodeStatus.peer_count)} detail="Connected peer count" />
            <StatusCard label="Mempool txs" value={formatNumber(nodeStatus.mempool_tx_count)} detail="Unconfirmed transactions" />
            <StatusCard label="Mempool usage" value={formatBytes(nodeStatus.mempool_usage)} detail="Approximate memory usage" />
            <StatusCard label="Relay fee" value={formatBtcPerKvb(nodeStatus.relay_fee)} detail="Minimum relay policy" />
            <StatusCard label="Chain size" value={formatBytes(nodeStatus.size_on_disk)} detail="Local chain data on disk" />
          </div>

          <StatusCard
            label="Best block hash"
            value={nodeStatus.best_block_hash ?? "unavailable"}
            detail="The hash of the current chain tip"
          />

          <CommandExplanationCard
            title="Node status RPC calls"
            command={nodeStatus.cli_commands.join("\n")}
            rpcMethod={nodeStatus.rpc_methods.join(", ")}
            parameters="[]"
            explanation={nodeStatus.explanation}
            concepts={nodeStatus.concepts}
            rawJson={nodeStatus.raw}
          />
        </>
      ) : (
        <WarningBox title="Backend unavailable">
          <p>{errorMessage}</p>
          <p className="mt-2">Start the FastAPI server and Bitcoin Core, then refresh this page.</p>
        </WarningBox>
      )}

      <WarningBox title="Local node policy">
        BitScope will use Bitcoin Core RPC only. Hosted blockchain APIs and remote indexers are intentionally outside the project.
      </WarningBox>
    </div>
  );
}

function formatNumber(value: number | null) {
  return value === null ? "unavailable" : new Intl.NumberFormat("en-US").format(value);
}

function formatPercent(value: number | null) {
  return value === null ? "unavailable" : `${(value * 100).toFixed(2)}%`;
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

function formatBtcPerKvb(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC/kvB`;
}
