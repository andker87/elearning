import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import api from "./api";
import Setup from "./pages/Setup";
import Login from "./pages/Login";
import PasswordDimenticata from "./pages/PasswordDimenticata";
import ReimpostaPassword from "./pages/ReimpostaPassword";
import RichiesteResetPassword from "./pages/RichiesteResetPassword";
import Shell from "./components/Shell";
import Corsi from "./pages/Corsi";
import Catalogo from "./pages/Catalogo";
import TestCorso from "./pages/TestCorso";
import Percorsi from "./pages/Percorsi";
import Edizioni from "./pages/Edizioni";
import EdizioneDetail from "./pages/EdizioneDetail";
import Utenti from "./pages/Utenti";
import Mansioni from "./pages/Mansioni";
import Gruppi from "./pages/Gruppi";
import Organizzazioni from "./pages/Organizzazioni";
import MieCorsi from "./pages/MieCorsi";
import StoricoCorsi from "./pages/StoricoCorsi";
import MieEdizioni from "./pages/MieEdizioni";
import IlMioTeam from "./pages/IlMioTeam";
import RichiesteIscrizione from "./pages/RichiesteIscrizione";
import RichiestaCorso from "./pages/RichiestaCorso";
import RichiesteCorsoAdmin from "./pages/RichiesteCorsoAdmin";
import Fabbisogno from "./pages/Fabbisogno";
import FabbisognoAdmin from "./pages/FabbisognoAdmin";
import ImpostazioniUtente from "./pages/ImpostazioniUtente";
import Azienda from "./pages/Azienda";
import Video from "./pages/Video";
import RegistroFormazione from "./pages/RegistroFormazione";
import MatriceFormativa from "./pages/MatriceFormativa";
import DashboardFormazione from "./pages/DashboardFormazione";
import DashboardKpi from "./pages/DashboardKpi";
import TemplateAttestati from "./pages/TemplateAttestati";
import StatoPiattaforma from "./pages/StatoPiattaforma";
import AuditLog from "./pages/AuditLog";
import Informazioni from "./pages/Informazioni";
import Piattaforma from "./pages/Piattaforma";
import InformativaPrivacy from "./pages/InformativaPrivacy";
import SincronizzazioneUtenti from "./pages/SincronizzazioneUtenti";
import Configurazione from "./pages/Configurazione";
import Etichette from "./pages/Etichette";

function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function Root() {
  const [status, setStatus] = useState(null);
  const navigate = useNavigate();
  useEffect(() => {
    api.get("/setup/status").then((r) => {
      setStatus(r.data.configured);
      if (!r.data.configured) navigate("/setup");
      else navigate(localStorage.getItem("token") ? "/miei-corsi" : "/login");
    });
  }, [navigate]);
  return null;
}

function ProteggiPagina({ children }) {
  const l = useLocation();
  return <ErrorBoundary chiave={l.pathname}>{children}</ErrorBoundary>;
}

export default function App() {
  return (
    <BrowserRouter>
      <ProteggiPagina>
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/setup" element={<Setup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/password-dimenticata" element={<PasswordDimenticata />} />
        <Route path="/reimposta-password" element={<ReimpostaPassword />} />
        <Route path="/miei-corsi" element={<RequireAuth><Shell><MieCorsi /></Shell></RequireAuth>} />
        <Route path="/catalogo" element={<RequireAuth><Shell><Catalogo /></Shell></RequireAuth>} />
        <Route path="/storico-corsi" element={<RequireAuth><Shell><StoricoCorsi /></Shell></RequireAuth>} />
        <Route path="/impostazioni" element={<RequireAuth><Shell><ImpostazioniUtente /></Shell></RequireAuth>} />
        <Route path="/mie-sessioni" element={<RequireAuth><Shell><MieEdizioni /></Shell></RequireAuth>} />
        <Route path="/risorse" element={<RequireAuth><Shell><IlMioTeam /></Shell></RequireAuth>} />
        <Route path="/richieste-iscrizione" element={<RequireAuth><Shell><RichiesteIscrizione /></Shell></RequireAuth>} />
        <Route path="/richiesta-corso" element={<RequireAuth><Shell><RichiestaCorso /></Shell></RequireAuth>} />
        <Route path="/richieste-corso-admin" element={<RequireAuth><Shell><RichiesteCorsoAdmin /></Shell></RequireAuth>} />
        <Route path="/fabbisogno" element={<RequireAuth><Shell><Fabbisogno /></Shell></RequireAuth>} />
        <Route path="/fabbisogno-admin" element={<RequireAuth><Shell><FabbisognoAdmin /></Shell></RequireAuth>} />
        <Route path="/registro-formazione" element={<RequireAuth><Shell><RegistroFormazione /></Shell></RequireAuth>} />
        <Route path="/dashboard-formazione" element={<RequireAuth><Shell><DashboardFormazione /></Shell></RequireAuth>} />
        <Route path="/dashboard-kpi" element={<RequireAuth><Shell><DashboardKpi /></Shell></RequireAuth>} />
        <Route path="/template-attestati" element={<RequireAuth><Shell><TemplateAttestati /></Shell></RequireAuth>} />
        <Route path="/corsi" element={<RequireAuth><Shell><Corsi /></Shell></RequireAuth>} />
        <Route path="/corsi/:corsoId/test" element={<RequireAuth><Shell><TestCorso /></Shell></RequireAuth>} />
        <Route path="/video" element={<RequireAuth><Shell><Video /></Shell></RequireAuth>} />
        <Route path="/percorsi" element={<RequireAuth><Shell><Percorsi /></Shell></RequireAuth>} />
        <Route path="/sessioni" element={<RequireAuth><Shell><Edizioni /></Shell></RequireAuth>} />
        <Route path="/sessioni/:id" element={<RequireAuth><Shell><EdizioneDetail /></Shell></RequireAuth>} />
        <Route path="/utenti" element={<RequireAuth><Shell><Utenti /></Shell></RequireAuth>} />
        <Route path="/mansioni" element={<RequireAuth><Shell><Mansioni /></Shell></RequireAuth>} />
        <Route path="/gruppi" element={<RequireAuth><Shell><Gruppi /></Shell></RequireAuth>} />
        <Route path="/societa-formazione-esterne" element={<RequireAuth><Shell><Organizzazioni /></Shell></RequireAuth>} />
        <Route path="/stato-piattaforma" element={<RequireAuth><Shell><StatoPiattaforma /></Shell></RequireAuth>} />
        <Route path="/audit-log" element={<RequireAuth><Shell><AuditLog /></Shell></RequireAuth>} />
        <Route path="/informazioni" element={<RequireAuth><Shell><Informazioni /></Shell></RequireAuth>} />
        <Route path="/piattaforma" element={<RequireAuth><Shell><Piattaforma /></Shell></RequireAuth>} />
        <Route path="/informativa-privacy" element={<RequireAuth><Shell><InformativaPrivacy /></Shell></RequireAuth>} />
        <Route path="/reset-password-richieste" element={<RequireAuth><Shell><RichiesteResetPassword /></Shell></RequireAuth>} />
        <Route path="/matrice-formativa" element={<RequireAuth><Shell><MatriceFormativa /></Shell></RequireAuth>} />
        <Route path="/sincronizzazione-utenti" element={<RequireAuth><Shell><SincronizzazioneUtenti /></Shell></RequireAuth>} />
        <Route path="/configurazione" element={<RequireAuth><Shell><Configurazione /></Shell></RequireAuth>} />
        <Route path="/etichette" element={<RequireAuth><Shell><Etichette /></Shell></RequireAuth>} />
        <Route path="/azienda" element={<RequireAuth><Shell><Azienda /></Shell></RequireAuth>} />
      </Routes>
      </ProteggiPagina>
    </BrowserRouter>
  );
}
