import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { TopNav } from "./TopNav";

describe("TopNav", () => {
  it("marks the current page's link active and leaves the others inactive", () => {
    render(
      <MemoryRouter initialEntries={["/compliance"]}>
        <TopNav />
      </MemoryRouter>,
    );

    expect(screen.getByText("Compliance")).toHaveClass("active");
    expect(screen.getByText("Alerts")).not.toHaveClass("active");
  });

  it("keeps 'Plants & harvest' active for a plants sub-route", () => {
    render(
      <MemoryRouter initialEntries={["/plants/packages"]}>
        <TopNav />
      </MemoryRouter>,
    );

    expect(screen.getByText("Plants & harvest")).toHaveClass("active");
  });
});
