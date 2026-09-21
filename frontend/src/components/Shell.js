import React, { useEffect, useState, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../api";

function buildSections(user) {
  const isTrainingAdmin = user?.role === "training_admin" || user?.role === "admin_tecnico";
  const isAdminTecnico = user?.role === "admin_tecnico";
  const sections = [
    { label: "Utente", links: [
      { to: "/miei-corsi", label: "I miei corsi", icon: "🎓" },
      { to: "/storico-corsi", label: "Storico corsi", icon: "📜" },
    ]},
  ];
  if (user?.is_docente) {
    sections.push({ label: "Formatore", links: [
      { to: "/mie-sessioni", label: "Le mie sessioni", icon: "🧑‍🏫" },
    ]});
  }
  if (isTrainingAdmin) {
    sections.push({ label: "Ufficio Training", links: [
      { to: "/sessioni", label: "Sessioni", icon: "📅" },
      { to: "/corsi", label: "Corsi", icon: "📚" },
      { to: "/video", label: "Video", icon: "🎬" },
      { to: "/percorsi", label: "Percorsi formativi", icon: "🧭" },
    ]});
  }
  if (isAdminTecnico) {
    sections.push({ label: "Amministrazione", links: [
      { to: "/utenti", label: "Utenti", icon: "👤" },
      { to: "/ruoli", label: "Ruoli", icon: "🏷️" },
      { to: "/gruppi", label: "Gruppi", icon: "🗂️" },
      { to: "/societa-formazione-esterne", label: "Società di formazione", icon: "🏢" },
      { to: "/azienda", label: "Azienda", icon: "⚙️" },
    ]});
  }
  return sections;
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const ref = useRef(null);

  function load() { api.get("/notifications").then((r) => setItems(r.data)); }
  useEffect(() => {
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);
  useEffect(() => {
    function onClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const unread = items.filter((i) => !i.letta).length;

  async function markRead(id) {
    await api.post(`/notifications/${id}/letta`);
    load();
  }

  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className="notif-bell" onClick={() => setOpen(!open)}>
        🔔{unread > 0 && <span className="notif-dot" />}
      </button>
      {open && (
        <div className="notif-panel">
          {items.length === 0 && <div className="notif-item">Nessuna notifica</div>}
          {items.map((n) => (
            <div key={n.id} className={`notif-item ${n.letta ? "" : "unread"}`} onClick={() => !n.letta && markRead(n.id)} style={{ cursor: n.letta ? "default" : "pointer" }}>
              {n.testo}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Shell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const sections = buildSections(user);

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">EL</div>
          <div className="sidebar-brand-name">E-Learning</div>
        </div>
        <nav>
          {sections.map((s) => (
            <div key={s.label}>
              <div className="sidebar-section-label">{s.label}</div>
              <div className="sidebar-section">
                {s.links.map((l) => (
                  <Link key={l.to} to={l.to} className={`nav-link ${location.pathname.startsWith(l.to) ? "active" : ""}`}>
                    <span>{l.icon}</span><span>{l.label}</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-footer-avatar">{initials(user?.full_name)}</div>
          <div className="sidebar-footer-name">{user?.full_name}</div>
          <Link to="/impostazioni" title="Impostazioni utente">⚙</Link>
          <a href="#" onClick={(e) => { e.preventDefault(); logout(); }} title="Esci">⏻</a>
        </div>
      </div>
      <div className="main">
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.5rem" }}>
          <NotificationBell />
        </div>
        {children}
      </div>
    </div>
  );
}
