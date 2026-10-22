import React, { useEffect, useState, useRef } from "react";
import CambioPasswordObbligatorio from "./CambioPasswordObbligatorio";
import Icona from "./Icona";
import { SPAZI, spaziDi, spazioDelPercorso, ultimoSpazio, ultimaPagina, ricordaPagina } from "../spazi";
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
  if (uffici.length === 1) return { label: "Fabbisogno del mio ufficio", tip: uffici[0].name };
  return { label: `Fabbisogno dei miei ${uffici.length} uffici`, tip: uffici.map((u) => u.name).join(", ") };
}

// Il menu di ogni spazio di lavoro. `conta` = cose che aspettano una decisione (dai contatori del server).
function sezioniDi(spazio, user, haSottoposti, uffici, contatori) {
  if (spazio === "gestione") return [
    { label: null, links: [{ to: "/da-gestire", label: "Da gestire", icon: "inbox", conta: contatori.gestione }] },
    { label: "Erogazione", links: [
      { to: "/sessioni", label: "Sessioni", icon: "cal" },
      { to: "/percorsi", label: "Percorsi formativi", icon: "route" },
      { to: "/richieste-iscrizione", label: "Richieste di iscrizione", icon: "list" },
    ]},
    { label: "Contenuti", links: [
      { to: "/corsi", label: "Corsi", icon: "book" },
      { to: "/video", label: "Video", icon: "play" },
      { to: "/questionari", label: "Questionari di gradimento", icon: "clip" },
      { to: "/template-attestati", label: "Modelli di attestato", icon: "file" },
      { to: "/etichette", label: "Etichette dei corsi", icon: "tag" },
    ]},
    { label: "Pianificazione", links: [
      { to: "/fabbisogno-admin", label: "Fabbisogno formativo", icon: "compass" },
      { to: "/richieste-corso-admin", label: "Richieste di corsi", icon: "list" },
    ]},
    { label: "Analisi", links: [
      { to: "/dashboard-formazione", label: "Panoramica", icon: "chart" },
      { to: "/dashboard-kpi", label: "Indicatori", icon: "pulse" },
      { to: "/matrice-formativa", label: "Matrice formativa", icon: "grid" },
      { to: "/registro-formazione", label: "Registro formazione", icon: "list" },
    ]},
  ];
  if (spazio === "admin") return [
    { label: null, links: [{ to: "/amministrazione", label: "Riepilogo", icon: "home" }] },
    { label: "Persone", links: [
      { to: "/utenti", label: "Utenti", icon: "user" },
      { to: "/gruppi", label: "Uffici", icon: "building" },
      { to: "/mansioni", label: "Mansioni", icon: "tag" },
      { to: "/societa-formazione-esterne", label: "Società di formazione", icon: "users" },
    ]},
    { label: "Accessi", links: [
      { to: "/reset-password-richieste", label: "Richieste di nuova password", icon: "key", conta: contatori.amministrazione },
      { to: "/sincronizzazione-utenti", label: "Sincronizzazione utenti", icon: "sync" },
    ]},
    { label: "Impostazioni", links: [
      { to: "/azienda", label: "Azienda", icon: "building" },
      { to: "/piattaforma", label: "Piattaforma", icon: "sliders" },
      { to: "/configurazione", label: "Configurazione", icon: "file" },
      { to: "/informativa-privacy", label: "Informativa privacy", icon: "shield" },
    ]},
    { label: "Controllo", links: [
      { to: "/stato-piattaforma", label: "Stato della piattaforma", icon: "pulse" },
      { to: "/audit-log", label: "Registro attività", icon: "list" },
    ]},
  ];
  const sections = [{ label: null, links: [
    { to: "/miei-corsi", label: "Home", icon: "home" },
    { to: "/catalogo", label: "Catalogo", icon: "book" },
    { to: "/storico-corsi", label: "Storico e attestati", icon: "award" },
  ]}];
  if (user?.is_docente) sections.push({ label: "Docenza", links: [{ to: "/mie-sessioni", label: "Le mie sessioni da docente", icon: "board" }] });
  const ufficio = [];
  if (haSottoposti) ufficio.push({ to: "/risorse", label: "Il mio team", icon: "users", conta: contatori.team });
  if (uffici.length > 0) {
    // La Formazione non chiede corsi a se stessa, ma se guida un ufficio riceve gli inviti di fabbisogno come tutti i responsabili.
    const { label, tip } = etichettaRichieste(uffici);
    ufficio.push({ to: "/fabbisogno", label, tip, icon: "compass" });
    if (!user?.poteri_formazione) ufficio.push({ to: "/richiesta-corso", label: "Richiedi un corso", icon: "list" });
  }
  if (ufficio.length) sections.push({ label: "Il mio ufficio", links: ufficio });
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
  const navigate = useNavigate();
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
        <Icona nome="bell" titolo="Notifiche" />{unread > 0 && <span className="notif-dot" />}
      </button>
      {open && (
        <div className="notif-panel fixed" style={{ left: pannelloLeft, top: 12 }}>
          {items.length === 0 && <div className="notif-item">Nessuna notifica</div>}
          {items.map((n) => (
            <button type="button" key={n.id} className={`notif-item ${n.letta ? "" : "unread"}`}
              onClick={() => { if (!n.letta) markRead(n.id); if (n.link) { setOpen(false); navigate(n.link); } }}
              style={{ cursor: n.letta && !n.link ? "default" : "pointer" }}>
              {n.testo}{n.link && <span className="notif-vai"> Apri →</span>}
            </button>
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
      className={`nav-link ${location.pathname === l.to || location.pathname.startsWith(l.to + "/") ? "active" : ""}`}
      style={collapsed ? { justifyContent: "center" } : undefined}
    >
      <Icona nome={l.icon} />{!collapsed && <span className="nav-testo">{l.label}</span>}
      {l.conta > 0 && <span className={collapsed ? "nav-conta piccolo" : "nav-conta"} aria-label={`${l.conta} da fare`}>{l.conta}</span>}
    </Link>
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
  const spazi = spaziDi(user);
  const spazioPagina = spazioDelPercorso(location.pathname, location.search, spazi);
  const [spazio, setSpazio] = useState(() => spazioPagina || (spazi.includes(ultimoSpazio(user?.id)) ? ultimoSpazio(user?.id) : spazi[0]));
  const [avvisoSpazio, setAvvisoSpazio] = useState(null);
  const sceltaDalSelettore = useRef(false);
  useEffect(() => {
    const dalSelettore = sceltaDalSelettore.current;      // letta e azzerata subito: non deve restare accesa per un collegamento successivo
    sceltaDalSelettore.current = false;
    if (!spazioPagina) return undefined;
    ricordaPagina(user?.id, spazioPagina, location.pathname + location.search);
    if (spazioPagina === spazio) return undefined;
    setSpazio(spazioPagina);
    if (dalSelettore || spazi.length < 2) return undefined;
    // si e' arrivati qui da un collegamento (notifica, email, pagina): lo si dice, cosi' il menu che cambia non sorprende
    setAvvisoSpazio(SPAZI[spazioPagina].nome);
    const t = setTimeout(() => setAvvisoSpazio(null), 2800);
    return () => { clearTimeout(t); setAvvisoSpazio(null); };
  }, [location.pathname, location.search]); // eslint-disable-line
  function vaiAlloSpazio(s) {
    sceltaDalSelettore.current = true;
    setSpazio(s);
    navigate(ultimaPagina(user?.id, s) || SPAZI[s].inizio);
  }
  const [contatori, setContatori] = useState({});
  useEffect(() => {
    const leggi = () => api.get("/contatori").then((r) => setContatori(r.data)).catch(() => {});
    leggi();
    const t = setInterval(leggi, 60000);
    return () => clearInterval(t);
  }, [location.pathname]);
  const contaSpazio = { mia: contatori.team, gestione: contatori.gestione, admin: contatori.amministrazione };
  const sections = sezioniDi(spazio, user, haSottoposti, uffici, contatori);
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
              <Icona nome={tema === "dark" ? "sun" : "moon"} />
            </button>
          )}
          <button
            type="button"
            className="sidebar-collapse-btn"
            style={collapsed ? { marginLeft: 0 } : undefined}
            onClick={toggleCollapsed}
            title={collapsed ? "Espandi sidebar" : "Comprimi sidebar"}
          >
            <Icona nome={collapsed ? "chevron-right" : "chevron-left"} size={16} />
          </button>
        </div>
        {spazi.length > 1 && (
          <div className={`spazi ${collapsed ? "compatti" : ""}`} role="group" aria-label="Spazio di lavoro">
            {spazi.map((s) => (
              <button type="button" key={s} aria-pressed={s === spazio} title={collapsed ? SPAZI[s].nome : undefined} onClick={() => vaiAlloSpazio(s)}>
                <Icona nome={SPAZI[s].icona} />{!collapsed && <span>{SPAZI[s].nome}</span>}
                {contaSpazio[s] > 0 && <span className={collapsed ? "nav-conta piccolo" : "nav-conta"}>{contaSpazio[s]}</span>}
              </button>
            ))}
          </div>
        )}
        <nav aria-label={SPAZI[spazio].nome}>
          {sections.map((s, n) => (
            <div key={s.label || n}>
              {!collapsed && s.label && <div className="sidebar-section-label">{s.label}</div>}
              <div className="sidebar-section">
                {s.links.map((l) => <VoceMenu key={l.to} l={l} location={location} collapsed={collapsed} />)}
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
              <Icona nome={tema === "dark" ? "sun" : "moon"} />
            </a>
          )}
          <Link to="/impostazioni" title="Impostazioni utente" className="footer-link"><Icona nome="gear" titolo="Impostazioni utente" /></Link>
          <Link to="/informazioni" title="Informazioni sulla piattaforma" className="footer-link"><Icona nome="info" titolo="Informazioni sulla piattaforma" /></Link>
          <a href="#esci" onClick={(e) => { e.preventDefault(); logout(); }} title="Esci" className="footer-link"><Icona nome="logout" titolo="Esci" /></a>
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
          <button type="button" className="sidebar-tool" onClick={() => setMobileAperta(true)} title="Apri il menu"><Icona nome="menu" size={22} titolo="Apri il menu" /></button>
          <div className="grow">{spazi.length > 1 ? SPAZI[spazio].nome : branding.nome_piattaforma}</div>
          <NotificationBell className="only-mobile" pannelloLeft={8} />
        </div>
        <InstallPwaBanner />
        <NotificationPermissionBanner />
        {children}
        {spazio === "mia" && (
          <nav className="barra-basso only-mobile" aria-label="Navigazione rapida">
            {[["/miei-corsi", "Home", "home"], ["/catalogo", "Catalogo", "book"], ["/storico-corsi", "Attestati", "award"]].map(([to, nome, icona]) => (
              <Link key={to} to={to} aria-current={location.pathname === to ? "page" : undefined}><Icona nome={icona} size={20} />{nome}</Link>
            ))}
            <button type="button" onClick={() => setMobileAperta(true)}><Icona nome="menu" size={20} />Menu</button>
          </nav>
        )}
        {avvisoSpazio && <div className="avviso-spazio" role="status">Sei passato a «{avvisoSpazio}»</div>}
      </div>
    </div>
  );
}

export default function Shell({ children }) {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (user?.password_da_cambiare) return <CambioPasswordObbligatorio />;
  return <ShellInterno>{children}</ShellInterno>;
}
