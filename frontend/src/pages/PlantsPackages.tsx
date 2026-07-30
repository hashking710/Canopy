import { useEffect, useState } from "react";
import { complianceApi } from "../api/complianceClient";
import type { Harvest, Package, StateComplianceRules } from "../api/complianceTypes";
import { Card } from "../components/Card";
import { OperatorPicker } from "../components/OperatorPicker";
import { PackagesSection } from "../components/PackagesSection";
import { PlantsSubNav } from "../components/PlantsSubNav";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useRooms } from "../hooks/useRooms";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function PlantsPackages() {
  const rooms = useRooms();
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();

  const [packages, setPackages] = useState<Package[] | null>(null);
  const [harvests, setHarvests] = useState<Harvest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stateRules, setStateRules] = useState<StateComplianceRules | null>(null);

  const refresh = () => {
    complianceApi.getPackages().then(setPackages).catch((err) => setError(errorMessage(err)));
    complianceApi.getHarvests().then(setHarvests).catch((err) => setError(errorMessage(err)));
  };

  useEffect(refresh, []);
  useEffect(() => {
    complianceApi.getStateRules().then((r) => setStateRules(r.active)).catch(() => {});
  }, []);

  if (error) return <div className="page-status">Failed to load package data: {error}</div>;

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Plants &amp; harvest</div>
      <PlantsSubNav />
      <Card>
        <p className="card-subtitle">
          Packages come from a finished harvest, or from processing another package — extraction, winterization,
          distillation, and so on.
        </p>
        <OperatorPicker
          operators={operators}
          currentOperatorId={currentOperatorId}
          onChange={changeCurrentOperator}
          onOperatorCreated={handleOperatorCreated}
          onOperatorUpdated={handleOperatorUpdated}
          onOperatorDeactivated={handleOperatorDeactivated}
        />
      </Card>

      <PackagesSection
        packages={packages ?? []}
        rooms={rooms}
        harvests={harvests ?? []}
        currentOperator={currentOperator}
        stateRules={stateRules}
        onDone={refresh}
      />
    </div>
  );
}
