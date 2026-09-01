export type StrainType = "indica" | "sativa" | "hybrid" | "unknown";

export interface Strain {
  id: string;
  name: string;
  lineage: string;
  strain_type: StrainType;
  description: string;
  thc_pct_typical: number | null;
  cbd_pct_typical: number | null;
  active: boolean;
  created_at: string;
}
