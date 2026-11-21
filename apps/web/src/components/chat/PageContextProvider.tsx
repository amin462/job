"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { PageContextPayload } from "@/types/marts";
import { truncatePageContext } from "@/lib/chat-grounded";

interface PageContextStoreValue {
  pageContext: PageContextPayload | null;
  setPageContext: (ctx: PageContextPayload) => void;
}

const PageContextReactContext = createContext<PageContextStoreValue | null>(null);

export function PageContextProvider({ children }: { children: React.ReactNode }) {
  const [pageContext, setPageContextState] = useState<PageContextPayload | null>(null);

  const setPageContext = useCallback((ctx: PageContextPayload) => {
    setPageContextState(truncatePageContext(ctx));
  }, []);

  return (
    <PageContextReactContext.Provider value={{ pageContext, setPageContext }}>
      {children}
    </PageContextReactContext.Provider>
  );
}

export function usePageContext() {
  const ctx = useContext(PageContextReactContext);
  if (!ctx) {
    return {
      pageContext: null,
      setPageContext: () => {},
    };
  }
  return ctx;
}

export function useRegisterPageContext(payload: PageContextPayload) {
  const { setPageContext } = usePageContext();
  const serialized = JSON.stringify(payload);

  useEffect(() => {
    setPageContext(JSON.parse(serialized) as PageContextPayload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serialized, setPageContext]);
}
