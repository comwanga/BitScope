import type { Metadata } from "next";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "BitScope",
  description: "An interactive Bitcoin Core laboratory powered entirely by your own node."
};

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/live", label: "Live" },
  { href: "/integrations", label: "Integrations" },
  { href: "/peers", label: "Peers" },
  { href: "/wallet", label: "Wallet" },
  { href: "/regtest", label: "Regtest" },
  { href: "/blocks", label: "Blocks" },
  { href: "/transactions", label: "Transactions" },
  { href: "/tx-control", label: "Tx Control" },
  { href: "/mempool", label: "Mempool" },
  { href: "/fees", label: "Fees" },
  { href: "/address", label: "Address" },
  { href: "/keys", label: "Keys" },
  { href: "/multisig", label: "Multisig" },
  { href: "/psbt", label: "PSBT" },
  { href: "/timelocks", label: "Timelocks" },
  { href: "/descriptors", label: "Descriptors" },
  { href: "/taproot", label: "Taproot" },
  { href: "/indexer", label: "Indexer" },
  { href: "/script", label: "Script" },
  { href: "/script-lab", label: "Script Lab" },
  { href: "/data-tx", label: "Data Tx" },
  { href: "/rpc", label: "RPC" },
  { href: "/learn", label: "Learn" }
];

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var theme = window.localStorage.getItem("bitscope-theme") || "dark";
                document.documentElement.classList.toggle("dark", theme !== "light");
                document.documentElement.dataset.theme = theme === "light" ? "light" : "dark";
              } catch (_) {
                document.documentElement.classList.add("dark");
                document.documentElement.dataset.theme = "dark";
              }
            `
          }}
        />
        <div className="min-h-screen min-w-0 lg:flex">
          <aside className="app-sidebar z-20 border-b border-stone-300 bg-ink text-white lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-64 lg:flex-col lg:border-b-0 lg:border-r lg:border-stone-800">
            <div className="flex shrink-0 items-start justify-between gap-3 px-4 py-4 sm:px-5 sm:py-5 lg:block">
              <Link href="/" className="block">
                <div className="text-xl font-semibold tracking-normal">BitScope</div>
                <div className="mt-1 text-sm text-stone-300">Bitcoin Core lab</div>
              </Link>
              <div className="shrink-0 lg:mt-4">
                <ThemeToggle />
              </div>
            </div>
            <nav className="flex gap-1 overflow-x-auto px-3 pb-4 [scrollbar-width:thin] lg:min-h-0 lg:flex-1 lg:flex-col lg:gap-1 lg:overflow-y-auto lg:overflow-x-hidden lg:pb-5">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="block shrink-0 whitespace-nowrap rounded-md px-3 py-2 text-sm text-stone-200 hover:bg-white/10 hover:text-white lg:w-full"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="min-w-0 w-full lg:pl-64">
            <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-5 sm:py-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
