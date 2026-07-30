import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PlantsSubNav } from "./PlantsSubNav";

describe("PlantsSubNav", () => {
  it("marks 'Batches & plants' active only on the exact /plants route, not sub-routes", () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsSubNav />
      </MemoryRouter>,
    );
    expect(screen.getByText("Batches & plants")).toHaveClass("active");
    unmount();

    render(
      <MemoryRouter initialEntries={["/plants/harvests"]}>
        <PlantsSubNav />
      </MemoryRouter>,
    );
    expect(screen.getByText("Batches & plants")).not.toHaveClass("active");
    expect(screen.getByText("Harvests")).toHaveClass("active");
  });
});
