import { createContext, useContext, type ReactNode } from "react";

import type { Client } from "./client";

export const ClientContext = createContext<Client | null>(null);

export function ClientProvider({ client, children }: { client: Client; children: ReactNode }) {
  return <ClientContext.Provider value={client}>{children}</ClientContext.Provider>;
}

/** 页面拿 client：测试传 prop，生产走 Context。useContext 必须无条件调用。 */
export function useClient(fallback?: Client): Client {
  const fromContext = useContext(ClientContext);
  const client = fallback ?? fromContext;
  if (!client) {
    throw new Error("缺少 Client：请在 main.tsx 用 <ClientProvider> 包裹");
  }
  return client;
}
