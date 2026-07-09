"use client";

import { useEffect, useState } from "react";
import { CommandExplanationCard } from "@/components/CommandExplanationCard";
import { StatusCard } from "@/components/StatusCard";
import { WarningBox } from "@/components/WarningBox";
import { FeeEstimate, FeeEstimateResponse, fetchFees } from "@/lib/api";

export function FeeEstimator() {
  const [fees, setFees] = useState<FeeEstimateResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void loadFees();
  }, []);

  async function loadFees() {
    setLoading(true);
    setError("");
    try {
      setFees(await fetchFees());
    } catch (caught) {
      setFees(null);
      setError(caught instanceof Error ? caught.message : "Fee estimates could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <p className="text-sm font-semibold uppercase text-forest">Fee estimator</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Estimate confirmation fees</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Ask Bitcoin Core for smart fee estimates and translate BTC/kvB into sats/vB.
        </p>
      </header>

      {loading ? (
        <WarningBox title="Loading fees">
          <p>Asking Bitcoin Core for 1, 3, 6, and 12 block confirmation targets.</p>
        </WarningBox>
      ) : null}

      {error ? (
        <WarningBox title="Fees unavailable">
          <p>{error}</p>
        </WarningBox>
      ) : null}

      {fees ? <FeeResults fees={fees} onRefresh={loadFees} /> : null}
    </div>
  );
}

function FeeResults({ fees, onRefresh }: { fees: FeeEstimateResponse; onRefresh: () => void }) {
  const unavailableCount = fees.estimates.filter((estimate) => !estimate.available).length;

  return (
    <div className="space-y-8">
      {unavailableCount ? (
        <WarningBox title="Some estimates are unavailable">
          <p>
            This is common on regtest and quiet nodes. Bitcoin Core needs enough recent fee data before
            `estimatesmartfee` can produce useful numbers.
          </p>
        </WarningBox>
      ) : null}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-ink hover:bg-stone-50"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {fees.estimates.map((estimate) => (
          <FeeCard key={estimate.target_blocks} estimate={estimate} />
        ))}
      </div>

      <section className="rounded-lg border border-stone-300 bg-panel p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink">Conversion</h2>
        <p className="mt-2 text-sm leading-6 text-stone-700">
          Bitcoin Core returns fee estimates as BTC per 1,000 virtual bytes. BitScope converts that to
          sats/vB with: BTC/kvB * 100,000.
        </p>
      </section>

      <CommandExplanationCard
        title="Smart fee estimates"
        command={fees.cli_commands.join("\n")}
        rpcMethod={fees.rpc_methods.join(", ")}
        parameters="[1], [3], [6], [12]"
        explanation={fees.explanation}
        concepts={fees.concepts}
        rawJson={fees.raw}
      />
    </div>
  );
}

function FeeCard({ estimate }: { estimate: FeeEstimate }) {
  const detail = estimate.available
    ? `${formatBtcPerKvb(estimate.btc_per_kvb)} from Bitcoin Core`
    : estimate.errors[0] ?? "Bitcoin Core did not return a feerate.";

  return (
    <StatusCard
      label={`${estimate.target_blocks} block${estimate.target_blocks === 1 ? "" : "s"}`}
      value={estimate.available ? formatSatsPerVbyte(estimate.sats_per_vbyte) : "unavailable"}
      detail={detail}
    />
  );
}

function formatSatsPerVbyte(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(2)} sats/vB`;
}

function formatBtcPerKvb(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(8)} BTC/kvB`;
}
