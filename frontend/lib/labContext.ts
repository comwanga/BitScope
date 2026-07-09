"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "bitscope.labContext.v1";

export type LabContext = {
  walletName: string;
  lastAddress: string;
  multisigAddress: string;
};

const emptyContext: LabContext = {
  walletName: "",
  lastAddress: "",
  multisigAddress: ""
};

export function useLabContext() {
  const [context, setContextState] = useState<LabContext>(emptyContext);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setContextState({ ...emptyContext, ...(JSON.parse(raw) as Partial<LabContext>) });
      }
    } catch {
      setContextState(emptyContext);
    }
  }, []);

  function setContext(update: Partial<LabContext>) {
    setContextState((current) => {
      const next = { ...current, ...update };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  return { context, setContext };
}
