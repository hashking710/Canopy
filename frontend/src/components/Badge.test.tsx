import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders the given text", () => {
    render(<Badge text="Flower · Day 12" />);
    expect(screen.getByText("Flower · Day 12")).toBeInTheDocument();
  });

  it("renders nothing for empty text", () => {
    const { container } = render(<Badge text="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("applies the default variant class for the default variant", () => {
    render(<Badge text="reconciled" />);
    const badge = screen.getByText("reconciled");
    expect(badge.className).toBe("badge ");
  });

  it.each([
    ["ok", "badge-ok"],
    ["warn", "badge-warn"],
    ["danger", "badge-danger"],
  ] as const)("applies %s variant class", (variant, expectedClass) => {
    render(<Badge text="status" variant={variant} />);
    expect(screen.getByText("status")).toHaveClass(expectedClass);
  });
});
