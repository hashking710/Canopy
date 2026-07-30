import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Room } from "../types";

export function useRooms(): Room[] {
  const [rooms, setRooms] = useState<Room[]>([]);
  useEffect(() => {
    api.getRooms().then(setRooms).catch(() => {});
  }, []);
  return rooms;
}
