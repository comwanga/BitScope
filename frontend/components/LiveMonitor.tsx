"use client";

import { useEffect, useRef, useState } from "react";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { LiveNodeEvent, liveNodeEventsUrl } from "@/lib/api";

const MAX_EVENTS = 20;

export function LiveMonitor() {
  const [intervalSeconds, setIntervalSeconds] = useState(3);
  const [connected, setConnected] = useState(false);
  const [latest, setLatest] = useState<LiveNodeEvent | null>(null);
  const [events, setEvents] = useState<LiveNodeEvent[]>([]);
  const [error, setError] = useState("");
  const sourceRef = useRef<EventSource | null>(null);

  function stopStream() {
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnected(false);
  }

  function startStream() {
    stopStream();
    setError("");

    const source = new EventSource(liveNodeEventsUrl(intervalSeconds));
    sourceRef.current = source;

    source.addEventListener("open", () => {
      setConnected(true);
      setError("");
    });

    source.addEventListener("node", (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as LiveNodeEvent;
      setLatest(payload);
      setEvents((current) => [payload, ...current].slice(0, MAX_EVENTS));
      setConnected(true);
      setError("");
    });

    source.addEventListener("node-error", (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as { message?: string };
      setConnected(false);
      setError(payload.message ?? "Live node status is unavailable.");
    });

    source.addEventListener("error", () => {
      setConnected(false);
      setError("The live stream disconnected. The backend may be restarting or Bitcoin Core may be unavailable.");
    });
  }

  useEffect(() => {
    startStream();

    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const syncLabel = formatSync(latest);
  const networkLabel = latest?.network_active === true ? "Active" : latest?.network_active === false ? "Inactive" : "Unknown";

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Live node monitor</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Watch Bitcoin Core state update</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Stream chain height, peer connectivity, sync progress, and mempool pressure from your local node while you mine, broadcast, or inspect regtest activity.
        </p>
      </header>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid gap-2">
            <div className="text-sm font-medium text-stone-500">Stream status</div>
            <div className="flex items-center gap-3">
              <span className={`h-3 w-3 rounded-full ${connected ? "bg-forest" : "bg-rust"}`} aria-hidden="true" />
              <span className="text-xl font-semibold text-ink">{connected ? "Connected" : "Disconnected"}</span>
            </div>
            <p className="text-sm leading-6 text-stone-600">Last sample: {latest ? formatTime(latest.timestamp) : "Waiting for first event"}</p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="grid gap-2 text-sm font-medium text-stone-600">
              Interval
              <select
                value={intervalSeconds}
                onChange={(event) => setIntervalSeconds(Number(event.target.value))}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-forest"
              >
                <option value={1}>1 second</option>
                <option value={3}>3 seconds</option>
                <option value={5}>5 seconds</option>
                <option value={10}>10 seconds</option>
              </select>
            </label>
            <button type="button" onClick={startStream} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink">
              Restart
            </button>
            <button type="button" onClick={stopStream} className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-ink">
              Stop
            </button>
          </div>
        </div>
      </section>

      {error ? (
        <WarningBox title="Live stream unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {latest?.warnings.length ? (
        <WarningBox title="Node warning">
          <ul className="space-y-1">
            {latest.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </WarningBox>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Chain" value={latest?.chain ?? "Unknown"} detail={`Height ${latest?.blocks ?? "?"} of ${latest?.headers ?? "?"}`} />
        <StatusCard label="Sync" value={syncLabel} detail={latest?.initial_block_download ? "Initial block download is active." : "Node reports normal validation state."} />
        <StatusCard label="Peers" value={formatNumber(latest?.peer_count)} detail={`Network ${networkLabel.toLowerCase()}.`} />
        <StatusCard label="Mempool" value={`${formatNumber(latest?.mempool_tx_count)} tx`} detail={`${formatBytes(latest?.mempool_usage)} in memory.`} />
      </section>

      <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="text-xl font-semibold text-ink">Recent samples</h2>
          <p className="text-sm text-stone-500">{events.length ? `${events.length} retained` : "No samples yet"}</p>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-stone-300 text-stone-500">
                <th className="py-2 pr-4 font-medium">Time</th>
                <th className="py-2 pr-4 font-medium">Chain</th>
                <th className="py-2 pr-4 font-medium">Height</th>
                <th className="py-2 pr-4 font-medium">Peers</th>
                <th className="py-2 pr-4 font-medium">Mempool</th>
                <th className="py-2 font-medium">Sync</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={`${event.timestamp}-${event.blocks}-${event.mempool_tx_count}`} className="border-b border-stone-200 last:border-0">
                  <td className="py-3 pr-4 font-mono text-xs text-stone-600">{formatTime(event.timestamp)}</td>
                  <td className="py-3 pr-4 text-ink">{event.chain ?? "Unknown"}</td>
                  <td className="py-3 pr-4 font-mono text-ink">{event.blocks ?? "?"}</td>
                  <td className="py-3 pr-4 font-mono text-ink">{formatNumber(event.peer_count)}</td>
                  <td className="py-3 pr-4 font-mono text-ink">{formatNumber(event.mempool_tx_count)}</td>
                  <td className="py-3 text-stone-700">{formatSync(event)}</td>
                </tr>
              ))}
              {!events.length ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-stone-500">
                    Waiting for the backend stream.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function formatSync(event: LiveNodeEvent | null): string {
  if (!event || event.verification_progress === null) {
    return "Unknown";
  }

  return `${(event.verification_progress * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString() : "0";
}

function formatBytes(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "0 B";
  }

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KiB`;
  }

  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function formatTime(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }

  return parsed.toLocaleTimeString();
}
