"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type NavigationItem = {
  href: string;
  label: string;
};

type NavigationGroup = {
  id: string;
  label: string;
  items: NavigationItem[];
};

const START_ITEMS: NavigationItem[] = [
  { href: "/", label: "Dashboard" },
  { href: "/demo", label: "Demo" },
  { href: "/curriculum", label: "Learning Path" },
  { href: "/learn", label: "Concept Library" }
];

const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    id: "core-basics",
    label: "Bitcoin Core Basics",
    items: [
      { href: "/live", label: "Node & Live Status" },
      { href: "/peers", label: "Peers" },
      { href: "/blocks", label: "Blocks" },
      { href: "/mempool", label: "Mempool" },
      { href: "/fees", label: "Fees" }
    ]
  },
  {
    id: "wallets-funding",
    label: "Wallets & Funding",
    items: [
      { href: "/regtest", label: "Regtest" },
      { href: "/wallet", label: "Wallet" },
      { href: "/address", label: "Addresses" },
      { href: "/keys", label: "Keys" },
      { href: "/descriptors", label: "Descriptors" }
    ]
  },
  {
    id: "transactions",
    label: "Transactions",
    items: [
      { href: "/transactions", label: "Transaction Explorer" },
      { href: "/tx-control", label: "Fee Bumping" },
      { href: "/multisig", label: "Multisig" },
      { href: "/psbt", label: "PSBT" },
      { href: "/timelocks", label: "Timelocks" },
      { href: "/data-tx", label: "OP_RETURN Data" }
    ]
  },
  {
    id: "script",
    label: "Bitcoin Script",
    items: [
      { href: "/script", label: "Script Explorer" },
      { href: "/script-lab", label: "Script Lab" },
      { href: "/taproot", label: "Taproot" }
    ]
  },
  {
    id: "practice-proof",
    label: "Practice & Proof",
    items: [{ href: "/scenarios", label: "Verified Scenarios" }]
  },
  {
    id: "advanced-tools",
    label: "Advanced Tools",
    items: [
      { href: "/rpc", label: "RPC Explorer" },
      { href: "/integrations", label: "Integrations" },
      { href: "/indexer", label: "Local Indexer" }
    ]
  }
];

export function SidebarNavigation() {
  const pathname = usePathname();
  const currentGroupId = groupForPath(pathname)?.id ?? null;
  const [openGroups, setOpenGroups] = useState<Set<string>>(
    () => new Set(["core-basics", ...(currentGroupId ? [currentGroupId] : [])])
  );

  useEffect(() => {
    if (!currentGroupId) return;
    setOpenGroups((current) => {
      if (current.has(currentGroupId)) return current;
      const next = new Set(current);
      next.add(currentGroupId);
      return next;
    });
  }, [currentGroupId]);

  function toggleGroup(groupId: string) {
    setOpenGroups((current) => {
      if (groupId === currentGroupId && current.has(groupId)) return current;
      const next = new Set(current);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  return (
    <nav aria-label="Primary learning navigation" className="px-3 pb-4 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:pb-5">
      <section aria-labelledby="start-navigation-title" className="shrink-0 border-b border-white/10 pb-3">
        <h2 id="start-navigation-title" className="px-3 pb-2 text-[0.68rem] font-bold uppercase tracking-[0.16em] text-stone-400">
          Start Here
        </h2>
        <div className="flex gap-1 overflow-x-auto pb-1 [scrollbar-width:thin] lg:grid lg:overflow-visible lg:pb-0">
          {START_ITEMS.map((item) => (
            <NavigationLink key={item.href} item={item} active={isActivePath(pathname, item.href)} />
          ))}
        </div>
      </section>

      <div className="mt-3 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:thin] lg:min-h-0 lg:flex-1 lg:block lg:space-y-1 lg:overflow-y-auto lg:overflow-x-hidden lg:pb-2">
        {NAVIGATION_GROUPS.map((group) => {
          const expanded = openGroups.has(group.id);
          const containsActivePage = group.id === currentGroupId;
          const panelId = `sidebar-group-${group.id}`;
          return (
            <section key={group.id} className="min-w-56 rounded-md border border-white/10 bg-white/[0.025] lg:min-w-0 lg:border-0 lg:bg-transparent">
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => toggleGroup(group.id)}
                className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-[0.68rem] font-bold uppercase tracking-[0.13em] transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-forest ${containsActivePage ? "bg-white/10 text-white" : "text-stone-400 hover:bg-white/5 hover:text-stone-200"}`}
              >
                <span>{group.label}</span>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  fill="none"
                  className={`h-4 w-4 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
                >
                  <path d="m7.5 4.5 5 5.5-5 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <div id={panelId} hidden={!expanded} className="space-y-1 px-1 pb-1">
                {group.items.map((item) => (
                  <NavigationLink key={item.href} item={item} active={isActivePath(pathname, item.href)} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </nav>
  );
}

function NavigationLink({ item, active }: { item: NavigationItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={`group flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-forest lg:w-full ${
        active
          ? "bg-forest text-white shadow-sm ring-1 ring-white/25"
          : "text-stone-200 hover:bg-white/10 hover:text-white"
      }`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-white" : "bg-stone-600 group-hover:bg-stone-300"}`} />
      <span>{item.label}</span>
      {active ? <span className="sr-only">, current page</span> : null}
    </Link>
  );
}

function isActivePath(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function groupForPath(pathname: string): NavigationGroup | undefined {
  return NAVIGATION_GROUPS.find((group) => group.items.some((item) => isActivePath(pathname, item.href)));
}
