import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import api from "./api";
import Setup from "./pages/Setup";
import Login from "./pages/Login";
import Shell from "./components/Shell";
import Corsi from "./pages/Corsi";
import TestCorso from "./pages/TestCorso";
import Percorsi from "./pages/Percorsi";
import Edizioni from "./pages/Edizioni";
import EdizioneDetail from "./pages/EdizioneDetail";
import Utenti from "./pages/Utenti";
import Ruoli from "./pages/Ruoli";
import Gruppi from "./pages/Gruppi";
import Organizzazioni from "./pages/Organizzazioni";
import MieCorsi from "./pages/MieCorsi";
import StoricoCorsi from "./pages/StoricoCorsi";
import MieEdizioni from "./pages/MieEdizioni";
import ImpostazioniUtente from "./pages/ImpostazioniUtente";
import Azienda from "./pages/Azienda";
import Video from "./pages/Video";

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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/setup" element={<Setup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/miei-corsi" element={<RequireAuth><Shell><MieCorsi /></Shell></RequireAuth>} />
        <Route path="/storico-corsi" element={<RequireAuth><Shell><StoricoCorsi /></Shell></RequireAuth>} />
        <Route path="/impostazioni" element={<RequireAuth><Shell><ImpostazioniUtente /></Shell></RequireAuth>} />
        <Route path="/mie-sessioni" element={<RequireAuth><Shell><MieEdizioni /></Shell></RequireAuth>} />
        <Route path="/corsi" element={<RequireAuth><Shell><Corsi /></Shell></RequireAuth>} />
        <Route path="/corsi/:corsoId/test" element={<RequireAuth><Shell><TestCorso /></Shell></RequireAuth>} />
        <Route path="/video" element={<RequireAuth><Shell><Video /></Shell></RequireAuth>} />
        <Route path="/percorsi" element={<RequireAuth><Shell><Percorsi /></Shell></RequireAuth>} />
        <Route path="/sessioni" element={<RequireAuth><Shell><Edizioni /></Shell></RequireAuth>} />
        <Route path="/sessioni/:id" element={<RequireAuth><Shell><EdizioneDetail /></Shell></RequireAuth>} />
        <Route path="/utenti" element={<RequireAuth><Shell><Utenti /></Shell></RequireAuth>} />
        <Route path="/ruoli" element={<RequireAuth><Shell><Ruoli /></Shell></RequireAuth>} />
        <Route path="/gruppi" element={<RequireAuth><Shell><Gruppi /></Shell></RequireAuth>} />
        <Route path="/societa-formazione-esterne" element={<RequireAuth><Shell><Organizzazioni /></Shell></RequireAuth>} />
        <Route path="/azienda" element={<RequireAuth><Shell><Azienda /></Shell></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
