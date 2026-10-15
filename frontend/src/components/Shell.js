import React, { useEffect, useState, useRef } from "react";
import CambioPasswordObbligatorio from "./CambioPasswordObbligatorio";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../api";
import InstallPwaBanner from "./InstallPwaBanner";
import NotificationPermissionBanner from "./NotificationPermissionBanner";
import { useBranding } from "../branding";
import { useTema } from "../theme";

const SIDEBAR_COLLAPSED_KEY = "sidebar_collapsed";
const SIDEBAR_WIDTH_KEY = "sidebar_width";
const SIDEBAR_DEFAULT_WIDTH = 256;
const SIDEBAR_MIN_WIDTH = 180;
const SIDEBAR_MAX_WIDTH = 360;
const SIDEBAR_COLLAPSED_WIDTH = 64;
const SUB_IMPOSTAZIONI_KEY = "sidebar_sub_impostazioni";

function leggiLarghezzaSidebar() {
  try {
    const v = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
    return v >= SIDEBAR_MIN_WIDTH && v <= SIDEBAR_MAX_WIDTH ? v : SIDEBAR_DEFAULT_WIDTH;
  } catch {
    return SIDEBAR_DEFAULT_WIDTH;
  }
}
function leggiCollapsedSidebar() {
  try { return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1"; } catch { return false; }
}

function etichettaRichieste(uffici) {
  // Il nome dell'ufficio chiarisce a che titolo si vede la voce; con piu' uffici li elenca il tooltip.
  if (uffici.length === 1) return { label: `Richieste ufficio ${uffici[0].name}`, tip: undefined };
  return { label: `Richieste dei miei ${uffici.length} uffici`, tip: uffici.map((u) => u.name).join(", ") };
}

function buildSections(user, haSottoposti, uffici) {
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
  if (haSottoposti) {
    sections.push({ label: "Il mio team", links: [{ to: "/risorse", label: "Le mie risorse", icon: "🧑‍🤝‍🧑" }] });
  }
  if (uffici.length > 0) {
    // L'Ufficio Formazione non chiede corsi a se stesso, ma se guida un ufficio
    // riceve comunque gli inviti di fabbisogno come tutti i responsabili.
    const { label, tip } = etichettaRichieste(uffici);
    const links = [{ to: "/fabbisogno", label, tip, icon: "🧭" }];
    if (!isTrainingAdmin) links.push({ to: "/richiesta-corso", label: "Richiedi un corso", icon: "📝" });
    sections.push({ label: "Fabbisogno formativo", links });
  }
  if (isTrainingAdmin) {
    sections.push({ label: "Ufficio Training", links: [
      { to: "/dashboard-formazione", label: "Dashboard", icon: "📊" },
      { to: "/dashboard-kpi", label: "Dashboard KPI", icon: "📈" },
      { to: "/sessioni", label: "Sessioni", icon: "📅" },
      { to: "/corsi", label: "Corsi", icon: "📚" },
      { to: "/video", label: "Video", icon: "🎬" },
      { to: "/percorsi", label: "Percorsi formativi", icon: "🧭" },
      { to: "/richieste-corso-admin", label: "Richieste corso", icon: "📝" },
      { to: "/fabbisogno-admin", label: "Fabbisogno formativo", icon: "🧭" },
      { to: "/matrice-formativa", label: "Matrice formativa", icon: "🟩" },
      { to: "/registro-formazione", label: "Registro formazione", icon: "📋" },
      { to: "/template-attestati", label: "Template attestati", icon: "🎨" },
      { to: "/etichette", label: "Etichette dei corsi", icon: "🏷️" },
    ]});
  }
  if (isAdminTecnico) {
    sections.push({ label: "Amministrazione", links: [
      { to: "/utenti", label: "Utenti", icon: "👤" },
      { to: "/ruoli", label: "Ruoli", icon: "🏷️" },
      { to: "/reset-password-richieste", label: "Reset password", icon: "🔑" },
      { to: "/gruppi", label: "Gruppi", icon: "🗂️" },
      { to: "/sincronizzazione-utenti", label: "Sincronizzazione utenti", icon: "🔄" },
      { to: "/societa-formazione-esterne", label: "Società di formazione", icon: "🏢" },
    ], sub: { label: "Impostazioni", icon: "⚙️", chiave: SUB_IMPOSTAZIONI_KEY, links: [
      { to: "/azienda", label: "Azienda", icon: "🏛️" },
      { to: "/piattaforma", label: "Piattaforma", icon: "🧩" },
      { to: "/configurazione", label: "Configurazione", icon: "📦" },
      { to: "/stato-piattaforma", label: "Stato piattaforma", icon: "🩺" },
      { to: "/audit-log", label: "Audit log", icon: "🔎" },
      { to: "/informativa-privacy", label: "Informativa privacy", icon: "🛡️" },
    ]}});
  }
  return sections;
}

function sigla(nome) {
  const parole = (nome || "").split(/[^A-Za-z0-9À-ÿ]+/).filter(Boolean);
  if (parole.length === 0) return "EL";
  if (parole.length === 1) return parole[0].slice(0, 2).toUpperCase();
  return (parole[0][0] + parole[1][0]).toUpperCase();
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
}

function NotificationBell({ pannelloLeft, className }) {
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
    <div style={{ position: "relative" }} className={className} ref={ref}>
      <button className="notif-bell" onClick={() => setOpen(!open)}>
        🔔{unread > 0 && <span className="notif-dot" />}
      </button>
      {open && (
        <div className="notif-panel fixed" style={{ left: pannelloLeft, top: 12 }}>
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

function VoceMenu({ l, location, collapsed }) {
  return (
    <Link
      to={l.to}
      title={collapsed ? l.label : (l.tip || l.label)}
      className={`nav-link ${location.pathname.startsWith(l.to) ? "active" : ""}`}
      style={collapsed ? { justifyContent: "center" } : undefined}
    >
      <span>{l.icon}</span>{!collapsed && <span className="nav-testo">{l.label}</span>}
    </Link>
  );
}

function SottoMenu({ sub, location, collapsed }) {
  const contieneAttiva = sub.links.some((l) => location.pathname.startsWith(l.to));
  const [aperto, setAperto] = useState(() => {
    try { return localStorage.getItem(sub.chiave) === "1"; } catch { return false; }
  });
  if (collapsed) return sub.links.map((l) => <VoceMenu key={l.to} l={l} location={location} collapsed />);
  const visibile = aperto || contieneAttiva;
  function alterna() {
    const nuovo = !aperto;
    setAperto(nuovo);
    try { localStorage.setItem(sub.chiave, nuovo ? "1" : "0"); } catch { /* ignore */ }
  }
  return (
    <>
      <button type="button" className="nav-link sidebar-sub-toggle" onClick={alterna} aria-expanded={visibile}>
        <span>{sub.icon}</span><span>{sub.label}</span><span className="chevron">{visibile ? "▾" : "▸"}</span>
      </button>
      {visibile && (
        <div className="sidebar-sub">
          {sub.links.map((l) => <VoceMenu key={l.to} l={l} location={location} collapsed={false} />)}
        </div>
      )}
    </>
  );
}

function ShellInterno({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const [haSottoposti, setHaSottoposti] = useState(false);
  const [uffici, setUffici] = useState([]);
  useEffect(() => {
    if (user?.id) {
      api.get(`/auth/users/${user.id}/sottoposti`).then((r) => setHaSottoposti(r.data.length > 0));
      api.get(`/auth/users/${user.id}/uffici-guidati`).then((r) => setUffici(r.data));
    }
  }, [user?.id]);
  const sections = buildSections(user, haSottoposti, uffici);
  const branding = useBranding();
  const [tema, alternaTema] = useTema();
  const [mobileAperta, setMobileAperta] = useState(false);
  useEffect(() => { setMobileAperta(false); }, [location.pathname]);

  const [collapsed, setCollapsed] = useState(leggiCollapsedSidebar);
  const [width, setWidth] = useState(leggiLarghezzaSidebar);
  const [resizing, setResizing] = useState(false);

  function toggleCollapsed() {
    setCollapsed((c) => {
      try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, !c ? "1" : "0"); } catch { /* ignore */ }
      return !c;
    });
  }

  // Trascinamento della maniglia sul bordo destro della sidebar: larghezza
  // salvata in localStorage, è una preferenza personale del browser.
  useEffect(() => {
    if (!resizing) return;
    function onMove(e) {
      setWidth(Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, e.clientX)));
    }
    function onUp() {
      setResizing(false);
      document.body.style.userSelect = "";
      setWidth((w) => {
        try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w)); } catch { /* ignore */ }
        return w;
      });
    }
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [resizing]);

  function ripristinaLarghezza() {
    setWidth(SIDEBAR_DEFAULT_WIDTH);
    try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(SIDEBAR_DEFAULT_WIDTH)); } catch { /* ignore */ }
  }

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : width;

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  }

  return (
    <div className="app-shell" style={{ userSelect: resizing ? "none" : "auto" }}>
      <div className={`sidebar-overlay ${mobileAperta ? "open" : ""}`} onClick={() => setMobileAperta(false)} />
      <div className={`sidebar ${mobileAperta ? "open" : ""}`} style={{ width: sidebarWidth, minWidth: sidebarWidth }}>
        <div className="sidebar-brand" style={{ justifyContent: collapsed ? "center" : "flex-start", gap: ".4rem" }}>
          <div className="sidebar-brand-icon">{sigla(branding.nome_piattaforma)}</div>
          {!collapsed && (
            <div className="sidebar-brand-name" style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                 title={branding.nome_piattaforma}>{branding.nome_piattaforma}</div>
          )}
          {!collapsed && <NotificationBell className="only-desktop" pannelloLeft={sidebarWidth + 8} />}
          {!collapsed && (
            <button type="button" className="sidebar-tool" onClick={alternaTema} title={tema === "dark" ? "Tema chiaro" : "Tema scuro"}>
              {tema === "dark" ? "☀️" : "🌙"}
            </button>
          )}
          <button
            type="button"
            className="sidebar-collapse-btn"
            style={collapsed ? { marginLeft: 0 } : undefined}
            onClick={toggleCollapsed}
            title={collapsed ? "Espandi sidebar" : "Comprimi sidebar"}
          >
            {collapsed ? "▶" : "◀"}
          </button>
        </div>
        <nav>
          {sections.map((s) => (
            <div key={s.label}>
              {!collapsed && <div className="sidebar-section-label">{s.label}</div>}
              <div className="sidebar-section">
                {s.links.map((l) => <VoceMenu key={l.to} l={l} location={location} collapsed={collapsed} />)}
                {s.sub && <SottoMenu sub={s.sub} location={location} collapsed={collapsed} />}
              </div>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer" style={collapsed ? { justifyContent: "center", flexWrap: "wrap", padding: ".9rem .4rem" } : undefined}>
          <div className="sidebar-footer-avatar">{initials(user?.full_name)}</div>
          {!collapsed && <div className="sidebar-footer-name">{user?.full_name}</div>}
          {collapsed && <NotificationBell className="only-desktop" pannelloLeft={sidebarWidth + 8} />}
          {collapsed && (
            <a href="#tema" className="footer-link" onClick={(e) => { e.preventDefault(); alternaTema(); }} title={tema === "dark" ? "Tema chiaro" : "Tema scuro"}>
              {tema === "dark" ? "☀️" : "🌙"}
            </a>
          )}
          <Link to="/impostazioni" title="Impostazioni utente">⚙</Link>
          <Link to="/informazioni" title="Informazioni sulla piattaforma">ⓘ</Link>
          <a href="#esci" onClick={(e) => { e.preventDefault(); logout(); }} title="Esci">⏻</a>
        </div>
      </div>
      {!collapsed && (
        <div
          className={`sidebar-resize-handle ${resizing ? "active" : ""}`}
          style={{ left: sidebarWidth - 3 }}
          onMouseDown={() => setResizing(true)}
          onDoubleClick={ripristinaLarghezza}
          title="Trascina per ridimensionare, doppio click per ripristinare"
        />
      )}
      <div className="main">
        <div className="mobile-topbar">
          <button type="button" className="sidebar-tool" style={{ fontSize: "1.3rem" }} onClick={() => setMobileAperta(true)} title="Apri il menu">☰</button>
          <div className="grow">{branding.nome_piattaforma}</div>
          <NotificationBell className="only-mobile" pannelloLeft={8} />
        </div>
        <InstallPwaBanner />
        <NotificationPermissionBanner />
        {children}
      </div>
    </div>
  );
}

export default function Shell({ children }) {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (user?.password_da_cambiare) return <CambioPasswordObbligatorio />;
  return <ShellInterno>{children}</ShellInterno>;
}
