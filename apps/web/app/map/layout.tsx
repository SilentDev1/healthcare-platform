import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hospital map",
  description:
    "Explore mapped hospital and service locations in Carevero’s New Hampshire launch region.",
  alternates: { canonical: "/map" },
};

export default function MapLayout({ children }: { children: React.ReactNode }) {
  return children;
}
