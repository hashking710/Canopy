import { useEffect, useState } from "react";
import { complianceApi } from "../api/complianceClient";
import type { Operator } from "../api/complianceTypes";

const CURRENT_OPERATOR_KEY = "canopy_current_operator_id";

export function useCurrentOperator() {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [currentOperatorId, setCurrentOperatorId] = useState<string>(
    () => localStorage.getItem(CURRENT_OPERATOR_KEY) ?? "",
  );

  useEffect(() => {
    complianceApi.getOperators().then((list) => {
      setOperators(list);
      setCurrentOperatorId((prev) => prev || list[0]?.id || "");
    });
  }, []);

  const changeCurrentOperator = (id: string) => {
    setCurrentOperatorId(id);
    localStorage.setItem(CURRENT_OPERATOR_KEY, id);
  };

  const handleOperatorCreated = (operator: Operator) => {
    setOperators((prev) => [...prev, operator]);
    changeCurrentOperator(operator.id);
  };

  const handleOperatorUpdated = (operator: Operator) => {
    setOperators((prev) => prev.map((o) => (o.id === operator.id ? operator : o)));
  };

  const handleOperatorDeactivated = (operatorId: string) => {
    setOperators((prev) => {
      const remaining = prev.filter((o) => o.id !== operatorId);
      if (currentOperatorId === operatorId) {
        changeCurrentOperator(remaining[0]?.id ?? "");
      }
      return remaining;
    });
  };

  const currentOperator = operators.find((o) => o.id === currentOperatorId) ?? null;

  return {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  };
}
