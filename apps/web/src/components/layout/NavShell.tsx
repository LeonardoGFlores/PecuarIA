import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

const TELAS = [
  { path: "/", label: "Mapa" },
  { path: "/historico", label: "Histórico ambiental" },
  { path: "/diagnostico", label: "Diagnóstico" },
  { path: "/perfil", label: "Perfil operacional" },
  { path: "/oferta", label: "Oferta regional" },
  { path: "/comparador", label: "Comparador de cenários" },
  { path: "/gargalos", label: "Gargalos" },
  { path: "/relatorio", label: "Relatório" },
];

export function NavShell(): ReactNode {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">PecuarIA</span>
        <nav className="app-nav">
          {TELAS.map((tela) => (
            <NavLink
              key={tela.path}
              to={tela.path}
              end={tela.path === "/"}
              className={({ isActive }) => (isActive ? "nav-link nav-link-active" : "nav-link")}
            >
              {tela.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
