import type { Metadata } from "next";
import Link from "next/link";
import { SidebarNavigation } from "@/components/SidebarNavigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "BitScope",
  description: "An interactive Bitcoin Core laboratory powered entirely by your own node."
};

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
              <Link href="/" className="flex items-center gap-3" aria-label="BitScope dashboard">
                <img src="/icon.svg" alt="" width="44" height="44" className="h-11 w-11 shrink-0" aria-hidden="true" />
                <div>
                  <div className="text-xl font-semibold tracking-normal">BitScope</div>
                  <div className="mt-0.5 text-sm text-stone-300">Bitcoin Core lab</div>
                </div>
              </Link>
              <div className="shrink-0 lg:mt-4">
                <ThemeToggle />
              </div>
            </div>
            <SidebarNavigation />
          </aside>
          <main className="min-w-0 w-full lg:pl-64">
            <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-5 sm:py-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
