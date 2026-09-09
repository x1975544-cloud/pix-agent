import { CodingDemoDashboard } from "@/components/CodingDemoDashboard";
import { api, type CodingDemoSnapshot } from "@/lib/api";

export default async function AutonomousCodingPage() {
  let initial: CodingDemoSnapshot | null = null;
  try {
    initial = await api.codingDemo();
  } catch {
    initial = null;
  }

  return <CodingDemoDashboard initial={initial} />;
}
