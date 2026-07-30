import type { ReactNode } from "react";

export function Card({ children }: { children: ReactNode }) {
  return (
    <div className="card">
      <div className="card-body">{children}</div>
    </div>
  );
}
