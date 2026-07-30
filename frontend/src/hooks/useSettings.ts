import { useState } from "react";

export type TempUnit = "F" | "C";

// "" means "use the browser's own timezone" — Intl.DateTimeFormat treats an
// undefined timeZone option as "use the runtime default", so this is passed
// straight through rather than needing its own explicit "browser" sentinel.
export const TIMEZONE_KEY = "canopy_timezone";
const TEMP_UNIT_KEY = "canopy_temp_unit_default";

export function useSettings() {
  const [timezone, setTimezoneState] = useState<string>(() => localStorage.getItem(TIMEZONE_KEY) ?? "");
  const [tempUnitDefault, setTempUnitState] = useState<TempUnit>(
    () => (localStorage.getItem(TEMP_UNIT_KEY) as TempUnit | null) ?? "F",
  );

  const setTimezone = (value: string) => {
    setTimezoneState(value);
    if (value) localStorage.setItem(TIMEZONE_KEY, value);
    else localStorage.removeItem(TIMEZONE_KEY);
  };

  const setTempUnitDefault = (value: TempUnit) => {
    setTempUnitState(value);
    localStorage.setItem(TEMP_UNIT_KEY, value);
  };

  return { timezone, setTimezone, tempUnitDefault, setTempUnitDefault };
}
