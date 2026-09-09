import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "PiX Agent",
  description: "Autonomous software engineering runtime dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen lg:flex">
          <Sidebar />
          <main className="flex-1 overflow-hidden px-5 py-6 sm:px-8 lg:ml-64 lg:px-10">
            <div className="mx-auto max-w-7xl">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
