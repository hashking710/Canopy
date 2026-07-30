import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ScanInput } from "./ScanInput";

describe("ScanInput", () => {
  it("calls onScan with the entered code when Enter is pressed", async () => {
    const user = userEvent.setup();
    const onScan = vi.fn();
    render(<ScanInput onScan={onScan} />);

    const input = screen.getByPlaceholderText("Scan or type a tag…");
    await user.type(input, "HARVEST-TAG-001{Enter}");

    expect(onScan).toHaveBeenCalledWith("HARVEST-TAG-001");
  });

  it("clears itself after a scan", async () => {
    const user = userEvent.setup();
    render(<ScanInput onScan={vi.fn()} />);

    const input = screen.getByPlaceholderText("Scan or type a tag…") as HTMLInputElement;
    await user.type(input, "TAG-1{Enter}");

    expect(input.value).toBe("");
  });

  it("does not call onScan for an empty submission", async () => {
    const user = userEvent.setup();
    const onScan = vi.fn();
    render(<ScanInput onScan={onScan} />);

    await user.click(screen.getByPlaceholderText("Scan or type a tag…"));
    await user.keyboard("{Enter}");

    expect(onScan).not.toHaveBeenCalled();
  });

  // Regression test: an earlier version of this component called inputRef.current.focus()
  // unconditionally after every scan, which ran *after* the caller's onScan callback and
  // silently stole focus back — defeating a caller's attempt to move focus to the next
  // field (e.g. LogWasteForm moving focus to the weight input after a tag scan). Verified
  // against the real page with scripted keystrokes while fixing it; this locks the fix in.
  it("does not steal focus back after onScan moves focus elsewhere", async () => {
    const user = userEvent.setup();

    function Harness() {
      return (
        <div>
          <ScanInput
            onScan={() => {
              document.getElementById("next-field")?.focus();
            }}
          />
          <input id="next-field" placeholder="next field" />
        </div>
      );
    }

    render(<Harness />);
    const input = screen.getByPlaceholderText("Scan or type a tag…");
    await user.type(input, "TAG-1{Enter}");

    expect(screen.getByPlaceholderText("next field")).toHaveFocus();
  });
});
