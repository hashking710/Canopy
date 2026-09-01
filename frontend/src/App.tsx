import { Route, Routes, useLocation } from "react-router-dom";
import { Alerts } from "./pages/Alerts";
import { Compliance } from "./pages/Compliance";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ThemeToggle } from "./components/ThemeToggle";
import { FacilityOverview } from "./pages/FacilityOverview";
import { Genetics } from "./pages/Genetics";
import { License } from "./pages/License";
import { MasterSiteRooms } from "./pages/MasterSiteRooms";
import { MasterSites } from "./pages/MasterSites";
import { PlantsBatches } from "./pages/PlantsBatches";
import { PlantsHarvests } from "./pages/PlantsHarvests";
import { PlantsPackages } from "./pages/PlantsPackages";
import { RoomDetail } from "./pages/RoomDetail";
import { Settings } from "./pages/Settings";

export default function App() {
  // Keyed by pathname so navigating away from a crashed page mounts a fresh
  // boundary (a new key means React discards the old, tripped instance) rather
  // than the fallback UI sticking around until a hard reload.
  const location = useLocation();

  return (
    <>
      <ThemeToggle />
      <ErrorBoundary key={location.pathname}>
        <Routes>
          <Route path="/" element={<FacilityOverview />} />
          <Route path="/rooms/:roomId" element={<RoomDetail />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/plants" element={<PlantsBatches />} />
          <Route path="/plants/harvests" element={<PlantsHarvests />} />
          <Route path="/plants/packages" element={<PlantsPackages />} />
          <Route path="/genetics" element={<Genetics />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/master" element={<MasterSites />} />
          <Route path="/master/:siteId" element={<MasterSiteRooms />} />
          <Route path="/license" element={<License />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </ErrorBoundary>
    </>
  );
}
