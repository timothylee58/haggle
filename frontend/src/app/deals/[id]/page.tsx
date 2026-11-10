import { Suspense } from "react";
import { Spectator } from "@/components/Spectator";

async function Deal({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Spectator key={id} dealId={id} />;
}

export default function DealPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense>
      <Deal params={params} />
    </Suspense>
  );
}
