import { Route, Routes } from "react-router-dom";
import { NavShell } from "./components/layout/NavShell";
import { ComparadorPage } from "./pages/ComparadorPage";
import { DiagnosticoPage } from "./pages/DiagnosticoPage";
import { GargalosPage } from "./pages/GargalosPage";
import { HistoricoPage } from "./pages/HistoricoPage";
import { MapaPage } from "./pages/MapaPage";
import { OfertaPage } from "./pages/OfertaPage";
import { PerfilPage } from "./pages/PerfilPage";
import { RelatorioPage } from "./pages/RelatorioPage";

function App() {
  return (
    <Routes>
      <Route element={<NavShell />}>
        <Route index element={<MapaPage />} />
        <Route path="historico" element={<HistoricoPage />} />
        <Route path="diagnostico" element={<DiagnosticoPage />} />
        <Route path="perfil" element={<PerfilPage />} />
        <Route path="oferta" element={<OfertaPage />} />
        <Route path="comparador" element={<ComparadorPage />} />
        <Route path="gargalos" element={<GargalosPage />} />
        <Route path="relatorio" element={<RelatorioPage />} />
      </Route>
    </Routes>
  );
}

export default App;
