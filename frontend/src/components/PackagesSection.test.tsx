import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PackagesSection } from "./PackagesSection";
import type { LabTest, Package, StateComplianceRules } from "../api/complianceTypes";

const { getAllLabTests, updatePackageStatus, processPackage, getPackageLineage, createLabTest, uploadLabTestCoa, downloadLabTestCoa } =
  vi.hoisted(() => ({
    getAllLabTests: vi.fn(),
    updatePackageStatus: vi.fn(),
    processPackage: vi.fn(),
    getPackageLineage: vi.fn(),
    createLabTest: vi.fn(),
    uploadLabTestCoa: vi.fn(),
    downloadLabTestCoa: vi.fn(),
  }));

vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    getAllLabTests: (...args: unknown[]) => getAllLabTests(...args),
    updatePackageStatus: (...args: unknown[]) => updatePackageStatus(...args),
    processPackage: (...args: unknown[]) => processPackage(...args),
    getPackageLineage: (...args: unknown[]) => getPackageLineage(...args),
    createLabTest: (...args: unknown[]) => createLabTest(...args),
    uploadLabTestCoa: (...args: unknown[]) => uploadLabTestCoa(...args),
    downloadLabTestCoa: (...args: unknown[]) => downloadLabTestCoa(...args),
  },
}));

const operator = { id: "op-1", name: "Alex Rivera", has_pin: false };

const trimPackage: Package = {
  id: "pkg-trim",
  harvest_id: "harvest-1",
  source_package_id: null,
  process_method: null,
  process_yield_pct: null,
  item_name: "GMO Trim",
  weight_g: 1000,
  room_id: "room-1",
  status: "active",
  created_at: "2026-07-01T00:00:00Z",
};

const crudePackage: Package = {
  id: "pkg-crude",
  harvest_id: null,
  source_package_id: "pkg-trim",
  process_method: "BHO Extraction",
  process_yield_pct: 15,
  item_name: "GMO BHO Crude",
  weight_g: 150,
  room_id: "room-1",
  status: "active",
  created_at: "2026-07-02T00:00:00Z",
};

const californiaRules = {
  state_name: "California",
  testing_required_for_solvent_extracts: true,
  testing_note: "Residual solvents required before retail sale.",
} as StateComplianceRules;

describe("PackagesSection", () => {
  it("flags a BHO-derived package with no passing residual-solvent test when the state requires it", async () => {
    getAllLabTests.mockResolvedValue([]);
    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(await screen.findByText("needs solvent testing")).toBeInTheDocument();
  });

  it("does not flag a package once it has a passing residual-solvent test", async () => {
    const passingTest: LabTest = {
      id: "labtest-1",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "pass",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-03",
      recorded_at: "2026-07-03T00:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: null,
      coa_stored_path: null,
    };
    getAllLabTests.mockResolvedValue([passingTest]);

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(screen.queryByText("needs solvent testing")).not.toBeInTheDocument();
  });

  it("shows a distinct FAILED badge (not the generic 'needs testing' one) for a package that failed its test", async () => {
    const failingTest: LabTest = {
      id: "labtest-2",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "fail",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-03",
      recorded_at: "2026-07-03T00:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: null,
      coa_stored_path: null,
    };
    getAllLabTests.mockResolvedValue([failingTest]);

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(await screen.findByText("FAILED solvent test")).toBeInTheDocument();
    expect(screen.queryByText("needs solvent testing")).not.toBeInTheDocument();
  });

  it("uses the most recent test result when a package has been retested", async () => {
    const oldFail: LabTest = {
      id: "labtest-old",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "fail",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-01",
      recorded_at: "2026-07-01T00:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: null,
      coa_stored_path: null,
    };
    const newPass: LabTest = { ...oldFail, id: "labtest-new", result: "pass", tested_at: "2026-07-05" };
    getAllLabTests.mockResolvedValue([oldFail, newPass]);

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(screen.queryByText("FAILED solvent test")).not.toBeInTheDocument();
    expect(screen.queryByText("needs solvent testing")).not.toBeInTheDocument();
  });

  it("breaks a same-day tie by recorded_at, not just tested_at", async () => {
    // Two tests logged on the SAME tested_at date (a same-day retest) — tested_at
    // alone can't order them, so recorded_at (an actual timestamp) must decide.
    const morningFail: LabTest = {
      id: "labtest-am",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "fail",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-10",
      recorded_at: "2026-07-10T09:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: null,
      coa_stored_path: null,
    };
    const afternoonPass: LabTest = {
      ...morningFail,
      id: "labtest-pm",
      result: "pass",
      recorded_at: "2026-07-10T15:00:00Z",
    };
    getAllLabTests.mockResolvedValue([morningFail, afternoonPass]);

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(screen.queryByText("FAILED solvent test")).not.toBeInTheDocument();
    expect(screen.queryByText("needs solvent testing")).not.toBeInTheDocument();
  });

  it("does not flag anything when the state's testing requirement hasn't been verified", async () => {
    getAllLabTests.mockResolvedValue([]);
    const unverifiedRules = { ...californiaRules, testing_required_for_solvent_extracts: null };

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={unverifiedRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(screen.queryByText("needs solvent testing")).not.toBeInTheDocument();
  });

  it("offers to attach a COA for a test that doesn't have one yet, and uploads it on selection", async () => {
    const user = userEvent.setup();
    const untested: LabTest = {
      id: "labtest-nocoa",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "pass",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-03",
      recorded_at: "2026-07-03T00:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: null,
      coa_stored_path: null,
    };
    getAllLabTests.mockResolvedValue([untested]);
    uploadLabTestCoa.mockResolvedValue({ ...untested, coa_filename: "report.pdf", coa_stored_path: "abc123.pdf" });

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    const fileInput = screen.getByText("attach COA").closest("label")!.querySelector("input[type=file]") as HTMLInputElement;
    const file = new File(["%PDF-1.4 fake"], "report.pdf", { type: "application/pdf" });
    await user.upload(fileInput, file);

    await waitFor(() => expect(uploadLabTestCoa).toHaveBeenCalledWith("labtest-nocoa", "op-1", file));
    // uploading re-fetches the list — resolve it with the now-attached test so the
    // control flips from "attach" to "view" without a page reload.
    getAllLabTests.mockResolvedValue([{ ...untested, coa_filename: "report.pdf", coa_stored_path: "abc123.pdf" }]);
  });

  it("shows a view control instead of an upload control once a COA is attached", async () => {
    const user = userEvent.setup();
    const withCoa: LabTest = {
      id: "labtest-hascoa",
      package_id: "pkg-crude",
      lab_name: "Test Lab",
      test_type: "residual_solvents",
      result: "pass",
      thc_pct: null,
      cbd_pct: null,
      notes: "",
      tested_at: "2026-07-03",
      recorded_at: "2026-07-03T00:00:00Z",
      recorded_by: "Alex Rivera",
      coa_filename: "report.pdf",
      coa_stored_path: "abc123.pdf",
    };
    getAllLabTests.mockResolvedValue([withCoa]);

    render(
      <PackagesSection
        packages={[trimPackage, crudePackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={vi.fn()}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    expect(screen.queryByText("attach COA")).not.toBeInTheDocument();
    await user.click(await screen.findByText("view COA"));
    expect(downloadLabTestCoa).toHaveBeenCalledWith("labtest-hascoa", "report.pdf");
  });

  it("processes a package into a new derivative with a computed yield preview", async () => {
    const user = userEvent.setup();
    getAllLabTests.mockResolvedValue([]);
    processPackage.mockResolvedValue({ ...crudePackage, id: "pkg-new" });
    const onDone = vi.fn();

    render(
      <PackagesSection
        packages={[trimPackage]}
        rooms={[{ id: "room-1", title: "Extraction Room" } as never]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={onDone}
      />,
    );

    const processForm = screen.getByText("source package").closest(".quick-form") as HTMLElement;
    await user.selectOptions(processForm.querySelector("select")!, "pkg-trim");
    await user.type(screen.getByPlaceholderText("e.g. GMO Distillate"), "GMO BHO Crude");
    const weightInput = processForm.querySelector("input[type='number']") as HTMLElement;
    await user.type(weightInput, "150");

    expect(await screen.findByText(/yield: 15\.0% of source weight/)).toBeInTheDocument();
  });

  it("records a lab test against a package", async () => {
    const user = userEvent.setup();
    getAllLabTests.mockResolvedValue([]);
    createLabTest.mockResolvedValue({});
    const onDone = vi.fn();

    render(
      <PackagesSection
        packages={[trimPackage]}
        rooms={[]}
        harvests={[]}
        currentOperator={operator}
        stateRules={californiaRules}
        onDone={onDone}
      />,
    );

    await waitFor(() => expect(getAllLabTests).toHaveBeenCalled());
    const labForm = screen.getByPlaceholderText("lab name").closest(".quick-form") as HTMLElement;
    await user.selectOptions(labForm.querySelectorAll("select")[0], "pkg-trim");
    await user.type(screen.getByPlaceholderText("lab name"), "Test Analytics");
    await user.click(screen.getByText("record test"));

    await waitFor(() =>
      expect(createLabTest).toHaveBeenCalledWith(
        "pkg-trim",
        expect.objectContaining({ lab_name: "Test Analytics", operator_id: "op-1" }),
      ),
    );
  });
});
