import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Settings } from "./Settings";
import { TIMEZONE_KEY } from "../hooks/useSettings";

const { getBackupStatus, runBackupNow, getSecrets, setSecret, clearSecret, getOperators } = vi.hoisted(() => ({
  getBackupStatus: vi.fn(),
  runBackupNow: vi.fn(),
  getSecrets: vi.fn(),
  setSecret: vi.fn(),
  clearSecret: vi.fn(),
  getOperators: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    getBackupStatus: (...args: unknown[]) => getBackupStatus(...args),
    runBackupNow: (...args: unknown[]) => runBackupNow(...args),
    getSecrets: (...args: unknown[]) => getSecrets(...args),
    setSecret: (...args: unknown[]) => setSecret(...args),
    clearSecret: (...args: unknown[]) => clearSecret(...args),
  },
}));

// CredentialsCard now needs to know "who's signed in" (secrets are admin-gated —
// see routers/secrets.py) via the same useCurrentOperator hook every compliance
// page already uses.
vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    getOperators: (...args: unknown[]) => getOperators(...args),
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
    // Clears call history (not mock implementations) on every hoisted mock —
    // without this, e.g. a later test's `expect(setSecret).not.toHaveBeenCalled()`
    // would see calls left over from an earlier test in this same file, since a
    // vi.fn() created via vi.hoisted() is one shared object across the whole file.
    vi.clearAllMocks();
    getBackupStatus.mockResolvedValue({ count: 0, latest: null, backups: [] });
    getSecrets.mockResolvedValue([]);
    getOperators.mockResolvedValue([{ id: "op-1", name: "Admin Operator", role: "admin", has_pin: false }]);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("persists a chosen timezone to localStorage", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText(/Timezone for dates/), "America/Chicago");

    expect(localStorage.getItem(TIMEZONE_KEY)).toBe("America/Chicago");
  });

  it("clears the stored timezone when switching back to browser default", async () => {
    const user = userEvent.setup();
    localStorage.setItem(TIMEZONE_KEY, "America/Chicago");
    renderPage();

    await user.selectOptions(screen.getByLabelText(/Timezone for dates/), "");

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

  describe("credentials", () => {
    const goveeSecret = {
      key: "CANOPY_GOVEE_API_KEY",
      description: "API key requested in the Govee Home app",
      is_set: false,
      set_via_dashboard: false,
    };

    it("shows nothing when no installed plugin needs a credential", async () => {
      renderPage();
      await screen.findByText(/No backups yet/); // wait for the page to settle
      expect(screen.queryByText("Sensor & sync credentials")).not.toBeInTheDocument();
    });

    it("shows an unset credential as needing setup", async () => {
      getSecrets.mockResolvedValue([goveeSecret]);
      renderPage();

      expect(await screen.findByText("CANOPY_GOVEE_API_KEY")).toBeInTheDocument();
      expect(screen.getByText("needs setup")).toBeInTheDocument();
      expect(screen.queryByText("clear")).not.toBeInTheDocument(); // not set via dashboard yet
    });

    it("shows a configured credential and offers to clear it", async () => {
      getSecrets.mockResolvedValue([{ ...goveeSecret, is_set: true, set_via_dashboard: true }]);
      renderPage();

      expect(await screen.findByText("configured")).toBeInTheDocument();
      expect(screen.getByText("clear")).toBeInTheDocument();
    });

    it("saves a new value and refreshes", async () => {
      const user = userEvent.setup();
      getSecrets.mockResolvedValueOnce([goveeSecret]);
      setSecret.mockResolvedValue({ key: goveeSecret.key, is_set: true });
      renderPage();
      await screen.findByText("CANOPY_GOVEE_API_KEY");
      await screen.findByText(/Admin Operator/); // operator picker finished loading

      getSecrets.mockResolvedValue([{ ...goveeSecret, is_set: true, set_via_dashboard: true }]);
      await user.type(screen.getByPlaceholderText("not set"), "my-real-key");
      await user.click(screen.getByText("save"));

      await waitFor(() =>
        expect(setSecret).toHaveBeenCalledWith("CANOPY_GOVEE_API_KEY", "my-real-key", "op-1", undefined),
      );
      expect(await screen.findByText(/Saved — takes effect/)).toBeInTheDocument();
    });

    it("clears a configured credential", async () => {
      const user = userEvent.setup();
      getSecrets.mockResolvedValueOnce([{ ...goveeSecret, is_set: true, set_via_dashboard: true }]);
      clearSecret.mockResolvedValue({ key: goveeSecret.key, is_set: false });
      renderPage();
      await screen.findByText("clear");
      await screen.findByText(/Admin Operator/);

      getSecrets.mockResolvedValue([goveeSecret]);
      await user.click(screen.getByText("clear"));

      await waitFor(() => expect(clearSecret).toHaveBeenCalledWith("CANOPY_GOVEE_API_KEY", "op-1", undefined));
      expect(await screen.findByText("needs setup")).toBeInTheDocument();
    });

    it("shows an error instead of saving when no operator is selected", async () => {
      const user = userEvent.setup();
      getOperators.mockResolvedValue([]); // fresh facility, nobody registered yet
      getSecrets.mockResolvedValue([goveeSecret]);
      renderPage();
      await screen.findByText("CANOPY_GOVEE_API_KEY");
      // getOperators and getSecrets resolve independently — this confirms the
      // operator picker has actually settled into its empty state too, not just
      // that the secrets list has rendered, before acting on the form.
      await screen.findByText("no operators registered");

      await user.type(screen.getByPlaceholderText("not set"), "my-real-key");
      await user.click(screen.getByText("save"));

      expect(await screen.findByText(/pick who you are/)).toBeInTheDocument();
      expect(setSecret).not.toHaveBeenCalled();
    });
  });
});
