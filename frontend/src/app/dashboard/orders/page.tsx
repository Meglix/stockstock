import { Suspense } from "react";
import { Orders } from "../../pages/Orders";

export default function OrdersPage() {
  return (
    <Suspense fallback={null}>
      <Orders />
    </Suspense>
  );
}
