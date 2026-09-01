import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("simulated render crash");
}

describe("ErrorBoundary", () => {
  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeInTheDocument();
  });

  it("shows a friendly fallback instead of a blank page when a child throws", () => {
    // React logs the error to the console too (its own dev-mode behavior, not
    // this component) — silence that noise for this test, it isn't what's
    // being asserted here.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong on this page.")).toBeInTheDocument();
    expect(screen.getByText("simulated render crash")).toBeInTheDocument();
    expect(screen.getByText("Back to facility overview")).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it("logs the crash via console.error so it's at least inspectable", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(consoleError).toHaveBeenCalledWith(
      "Canopy dashboard crashed rendering this page:",
      expect.any(Error),
      expect.anything(),
    );

    consoleError.mockRestore();
  });
});
