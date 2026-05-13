import { Suspense } from "react";
import { Parts } from "../../pages/Parts";

export default function PartsPage() {
  return (
    <Suspense fallback={null}>
      <Parts />
    </Suspense>
  );
}
