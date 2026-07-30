export interface AlertRule {
  id: string;
  room_id: string;
  metric: string;
  condition: "gt" | "lt";
  threshold: number;
  severity: "warning" | "critical";
  enabled: boolean;
  created_at: string;
}

export interface AlertEvent {
  id: number;
  rule_id: string;
  room_id: string;
  metric: string;
  value: number;
  threshold: number;
  condition: "gt" | "lt";
  severity: "warning" | "critical";
  triggered_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}
