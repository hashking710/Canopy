import { Route, Routes } from "react-router-dom";
import { Alerts } from "./pages/Alerts";
import { Compliance } from "./pages/Compliance";
import { ThemeToggle } from "./components/ThemeToggle";
import { FacilityOverview } from "./pages/FacilityOverview";
import { License } from "./pages/License";
import { MasterSiteRooms } from "./pages/MasterSiteRooms";
import { MasterSites } from "./pages/MasterSites";
import { PlantsBatches } from "./pages/PlantsBatches";
import { PlantsHarvests } from "./pages/PlantsHarvests";
import { PlantsPackages } from "./pages/PlantsPackages";
import { RoomDetail } from "./pages/RoomDetail";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <>
      <ThemeToggle />
      <Routes>
        <Route path="/" element={<FacilityOverview />} />
        <Route path="/rooms/:roomId" element={<RoomDetail />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/plants" element={<PlantsBatches />} />
        <Route path="/plants/harvests" element={<PlantsHarvests />} />
        <Route path="/plants/packages" element={<PlantsPackages />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/master" element={<MasterSites />} />
        <Route path="/master/:siteId" element={<MasterSiteRooms />} />
        <Route path="/license" element={<License />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </>
  );
}
