import type { Metadata } from "next";
import "./styles.css";
import "./memory.css";

export const metadata: Metadata = {
  title: "Liproser · Profile Lab",
  description: "Private, evidence-preserving LinkedIn profile optimization",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
