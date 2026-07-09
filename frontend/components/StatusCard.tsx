type StatusCardProps = {
  label: string;
  value: string;
  detail?: string;
};

export function StatusCard({ label, value, detail }: StatusCardProps) {
  return (
    <section className="min-w-0 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm">
      <div className="text-sm font-medium text-stone-500">{label}</div>
      <div className="mt-2 [overflow-wrap:anywhere] text-xl font-semibold text-ink sm:text-2xl">{value}</div>
      {detail ? <p className="mt-2 text-sm leading-6 text-stone-600">{detail}</p> : null}
    </section>
  );
}
