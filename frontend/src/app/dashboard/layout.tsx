import type { ReactNode } from "react";
import { AppShell } from "../components/AppShell";
import { DemoStoreProvider } from "../context/DemoStoreContext";

export default function DashboardLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <DemoStoreProvider>
      <AppShell>{children}</AppShell>
    </DemoStoreProvider>
  );
}
