import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { LocalAddress, PeerInfo, PeerNetwork, fetchPeers } from "@/lib/api";

export async function PeerDashboard() {
  try {
    const summary = await fetchPeers();

    return (
      <div className="space-y-6 sm:space-y-8">
        <header className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-forest">Peer and privacy dashboard</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect Bitcoin Core peers</h1>
          <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
            See connected peers, network transports, Tor/I2P visibility, service flags, relay behavior, and reachability warnings from your own node.
          </p>
        </header>

        {summary.warnings.length ? (
          <WarningBox title="Privacy and reachability notes">
            <ul className="space-y-1">
              {summary.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </WarningBox>
        ) : null}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatusCard label="Peers" value={String(summary.peer_count)} detail={`${summary.inbound_count} inbound, ${summary.outbound_count} outbound`} />
          <StatusCard label="Tor peers" value={String(summary.tor_peer_count)} detail="Connected onion peers" />
          <StatusCard label="I2P peers" value={String(summary.i2p_peer_count)} detail="Connected I2P peers" />
          <StatusCard label="Local addresses" value={String(summary.local_address_count)} detail="Advertised addresses" />
          <StatusCard label="Network active" value={summary.network_active === false ? "no" : "yes"} detail="Bitcoin Core network toggle" />
          <StatusCard label="Reachable" value={summary.reachable_networks.filter(Boolean).join(", ") || "none"} detail="Reported address networks" />
          <StatusCard label="Relay peers" value={String(summary.peers.filter((peer) => peer.relay_transactions).length)} detail="Peers relaying transactions" />
          <StatusCard label="Privacy transports" value={summary.tor_peer_count || summary.i2p_peer_count ? "visible" : "not visible"} detail="Tor/I2P from RPC data" />
        </section>

        <NetworkTable networks={summary.networks} />
        <LocalAddressList addresses={summary.local_addresses} />
        <PeerTable peers={summary.peers} />

        <CommandExplanationCard
          title="Peer network RPC calls"
          command={summary.cli_commands.join("\n")}
          rpcMethod={summary.rpc_methods.join(", ")}
          parameters="[]"
          explanation={summary.explanation}
          concepts={summary.concepts}
          rawJson={summary.raw}
        />
      </div>
    );
  } catch (caught) {
    return (
      <div className="space-y-6">
        <header className="max-w-3xl">
          <p className="text-sm font-semibold uppercase text-forest">Peer and privacy dashboard</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Inspect Bitcoin Core peers</h1>
        </header>
        <WarningBox title="Peer data unavailable">
          <p>{caught instanceof Error ? caught.message : "Peer and network data could not be loaded."}</p>
        </WarningBox>
      </div>
    );
  }
}

function NetworkTable({ networks }: { networks: PeerNetwork[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <h2 className="text-lg font-semibold text-ink">Address networks</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-xs uppercase text-stone-500">
              <th className="py-2 pr-4 font-semibold">Network</th>
              <th className="py-2 pr-4 font-semibold">Reachable</th>
              <th className="py-2 pr-4 font-semibold">Limited</th>
              <th className="py-2 pr-4 font-semibold">Proxy</th>
              <th className="py-2 font-semibold">Randomized creds</th>
            </tr>
          </thead>
          <tbody>
            {networks.map((network, index) => (
              <tr key={`${network.name}-${index}`} className="border-b border-stone-100 last:border-0">
                <td className="py-3 pr-4 font-mono text-ink">{network.name ?? "unknown"}</td>
                <td className="py-3 pr-4">{formatBool(network.reachable)}</td>
                <td className="py-3 pr-4">{formatBool(network.limited)}</td>
                <td className="py-3 pr-4 font-mono text-xs">{network.proxy || "none"}</td>
                <td className="py-3">{formatBool(network.proxy_randomize_credentials)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LocalAddressList({ addresses }: { addresses: LocalAddress[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-lg font-semibold text-ink">Local advertised addresses</h2>
        <span className="text-sm text-stone-500">{addresses.length} address(es)</span>
      </div>
      {addresses.length ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {addresses.map((address, index) => (
            <article key={`${address.address}-${index}`} className="rounded-lg border border-stone-200 bg-white p-4">
              <div className="break-all font-mono text-sm font-semibold text-ink">{address.address ?? "unknown"}</div>
              <div className="mt-2 text-sm text-stone-600">
                {address.network ?? "unknown"} · port {address.port ?? "?"} · score {address.score ?? "?"}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-stone-600">Bitcoin Core is not advertising local addresses through RPC.</p>
      )}
    </section>
  );
}

function PeerTable({ peers }: { peers: PeerInfo[] }) {
  return (
    <section className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-lg font-semibold text-ink">Connected peers</h2>
        <span className="text-sm text-stone-500">{peers.length} peer(s)</span>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[64rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-xs uppercase text-stone-500">
              <th className="py-2 pr-4 font-semibold">Peer</th>
              <th className="py-2 pr-4 font-semibold">Network</th>
              <th className="py-2 pr-4 font-semibold">Direction</th>
              <th className="py-2 pr-4 font-semibold">Services</th>
              <th className="py-2 pr-4 font-semibold">Connection</th>
              <th className="py-2 pr-4 font-semibold">Sync</th>
              <th className="py-2 font-semibold">Ping</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer, index) => (
              <tr key={`${peer.id}-${peer.addr}-${index}`} className="border-b border-stone-100 align-top last:border-0">
                <td className="max-w-xs break-all py-3 pr-4 font-mono text-xs text-ink">{peer.addr ?? "unknown"}</td>
                <td className="py-3 pr-4">{peer.network ?? "unknown"}</td>
                <td className="py-3 pr-4">{peer.inbound ? "inbound" : peer.inbound === false ? "outbound" : "unknown"}</td>
                <td className="py-3 pr-4">{peer.services_names.length ? peer.services_names.join(", ") : peer.services ?? "unknown"}</td>
                <td className="py-3 pr-4">{peer.connection_type ?? "unknown"}</td>
                <td className="py-3 pr-4 font-mono text-xs">
                  headers {peer.synced_headers ?? "?"}, blocks {peer.synced_blocks ?? "?"}
                </td>
                <td className="py-3">{peer.ping_time === null ? "unknown" : `${(peer.ping_time * 1000).toFixed(1)} ms`}</td>
              </tr>
            ))}
            {!peers.length ? (
              <tr>
                <td colSpan={7} className="py-6 text-center text-stone-500">
                  No connected peers reported by Bitcoin Core.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatBool(value: boolean | null): string {
  if (value === null) {
    return "unknown";
  }
  return value ? "yes" : "no";
}
