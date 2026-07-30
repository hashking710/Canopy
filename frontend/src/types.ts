export interface Metric {
  key: string;
  label: string;
  unit: string;
  value: number;
  decimals: number;
}

export interface Room {
  id: string;
  room_type: string;
  path: string;
  subtitle: string;
  title: string;
  badge: string;
  footnote: string;
  section: string | null;
  tag_count: number;
  stats: Metric[];
  last_poll_at: string | null;
  last_poll_error: string | null;
}

export interface ReadingPoint {
  ts: string;
  value: number;
}

export interface ReadingUpdateMessage {
  type: "reading_update";
  room_id: string;
  stats: Metric[];
}
