import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Settings } from "./Settings";
import { TIMEZONE_KEY } from "../hooks/useSettings";

const { getBackupStatus, runBackupNow } = vi.hoisted(() => ({
  getBackupStatus: vi.fn(),
  runBackupNow: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    getBackupStatus: (...args: unknown[]) => getBackupStatus(...args),
    runBackupNow: (...args: unknown[]) => runBackupNow(...args),
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  );
}

describe("Settings", () => {
  beforeEach(() => {
    getBackupStatus.mockResolvedValue({ count: 0, latest: null, backups: [] });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("persists a chosen timezone to localStorage", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByRole("combobox"), "America/Chicago");

    expect(localStorage.getItem(TIMEZONE_KEY)).toBe("America/Chicago");
  });

  it("clears the stored timezone when switching back to browser default", async () => {
    const user = userEvent.setup();
    localStorage.setItem(TIMEZONE_KEY, "America/Chicago");
    renderPage();

    await user.selectOptions(screen.getByRole("combobox"), "");

    expect(localStorage.getItem(TIMEZONE_KEY)).toBeNull();
  });

  it("persists the default temperature unit toggle", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText("°C"));

    expect(localStorage.getItem("canopy_temp_unit_default")).toBe("C");
  });

  it("shows when no backup has run yet", async () => {
    renderPage();
    expect(await screen.findByText(/No backups yet/)).toBeInTheDocument();
  });

  it("shows the latest backup's time, size, and retained count once one exists", async () => {
    getBackupStatus.mockResolvedValue({
      count: 3,
      latest: { filename: "canopy-backup-20260729T090000Z.tar.gz", size_bytes: 2_500_000, created_at: "2026-07-29T09:00:00Z" },
      backups: [],
    });
    renderPage();
    expect(await screen.findByText(/2\.4 MB/)).toBeInTheDocument();
    expect(screen.getByText(/3 kept/)).toBeInTheDocument();
  });

  it("triggers a backup and refreshes the status on click", async () => {
    const user = userEvent.setup();
    runBackupNow.mockResolvedValue({ filename: "canopy-backup-new.tar.gz", size_bytes: 100, created_at: "2026-07-29T10:00:00Z" });
    renderPage();
    await screen.findByText(/No backups yet/);

    getBackupStatus.mockResolvedValue({
      count: 1,
      latest: { filename: "canopy-backup-new.tar.gz", size_bytes: 100, created_at: "2026-07-29T10:00:00Z" },
      backups: [],
    });
    await user.click(screen.getByText("back up now"));

    await waitFor(() => expect(runBackupNow).toHaveBeenCalled());
    expect(await screen.findByText(/1 kept/)).toBeInTheDocument();
  });
});
