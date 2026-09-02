import { NavLink } from "react-router-dom";

export function PlantsSubNav() {
  return (
    <nav className="sub-nav">
      <NavLink to="/plants" end className={({ isActive }) => (isActive ? "active" : "")}>
        Batches &amp; plants
      </NavLink>
      <NavLink to="/plants/harvests" className={({ isActive }) => (isActive ? "active" : "")}>
        Harvests
      </NavLink>
      <NavLink to="/plants/packages" className={({ isActive }) => (isActive ? "active" : "")}>
        Packages &amp; testing
      </NavLink>
      <NavLink to="/plants/genetics" className={({ isActive }) => (isActive ? "active" : "")}>
        Genetics
      </NavLink>
    </nav>
  );
}
