type WarningBoxProps = {
  title: string;
  children: React.ReactNode;
};

export function WarningBox({ title, children }: WarningBoxProps) {
  return (
    <section className="min-w-0 rounded-lg border border-rust/40 bg-white p-4">
      <h2 className="text-base font-semibold text-rust">{title}</h2>
      <div className="mt-2 text-sm leading-6 text-stone-700">{children}</div>
    </section>
  );
}
