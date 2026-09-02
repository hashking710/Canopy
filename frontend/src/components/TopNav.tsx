import { Link, NavLink } from "react-router-dom";

export function TopNav() {
  return (
    <div className="app-header">
      <Link to="/" className="app-brand">
        <img src="/canopy.svg" alt="" className="app-brand-logo" />
        <span className="app-brand-text">Canopy</span>
      </Link>
      <nav className="top-nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Facility
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => (isActive ? "active" : "")}>
          Alerts
        </NavLink>
        <NavLink to="/plants" className={({ isActive }) => (isActive ? "active" : "")}>
          Plants &amp; harvest
        </NavLink>
        <NavLink to="/compliance" className={({ isActive }) => (isActive ? "active" : "")}>
          Compliance
        </NavLink>
        <NavLink to="/master" className={({ isActive }) => (isActive ? "active" : "")}>
          Master control panel
        </NavLink>
        <NavLink to="/license" className={({ isActive }) => (isActive ? "active" : "")}>
          License
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
          Settings
        </NavLink>
      </nav>
    </div>
  );
}
