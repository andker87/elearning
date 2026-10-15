from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # docker-compose passa una variabile vuota quando manca nel .env: si tratta come non impostata
    # (altrimenti SMTP_PORT="" farebbe fallire l'avvio).
    model_config = SettingsConfigDict(env_ignore_empty=True)

    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    # Siti ammessi dal browser per chiamare le API da un altro indirizzo (elenco separato da virgole).
    # Vuoto = nessuno: la piattaforma funziona sullo stesso indirizzo ovunque sia installata.
    CORS_ORIGINS: Optional[str] = None

    @property
    def cors_origins_lista(self):
        return [o.strip() for o in (self.CORS_ORIGINS or "").split(",") if o.strip() and o.strip() != "*"]

    # Microsoft Graph (Teams attendance) - opzionale, fallback manuale se assenti
    GRAPH_TENANT_ID: Optional[str] = None
    GRAPH_CLIENT_ID: Optional[str] = None
    GRAPH_CLIENT_SECRET: Optional[str] = None

    @property
    def graph_enabled(self) -> bool:
        return bool(self.GRAPH_TENANT_ID and self.GRAPH_CLIENT_ID and self.GRAPH_CLIENT_SECRET)

    # SMTP per l'invio di notifiche via email - configurazione solo da ambiente
    # (chi amministra il container), mai dal DB/UI applicativa. La piattaforma
    # mostra solo lo stato (configurato/host/mittente), mai le credenziali.
    # Stesso principio da seguire per una futura SSO aziendale.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_MITTENTE: Optional[str] = None
    SMTP_TLS: bool = True

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_MITTENTE)

    # Single sign-on aziendale (OpenID Connect, authorization code + PKCE) -
    # solo da ambiente, come SMTP (vedi ROADMAP sez. D2/R). Per Microsoft
    # Entra: SSO_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
    # (endpoint del tenant, non /common: serve un issuer concreto).
    SSO_ISSUER: Optional[str] = None
    SSO_CLIENT_ID: Optional[str] = None
    SSO_CLIENT_SECRET: Optional[str] = None
    SSO_PUBLIC_URL: Optional[str] = None  # base pubblica della piattaforma, es. https://formazione.azienda.it
    SSO_LABEL: str = "Accedi con l'account aziendale"
    SSO_PROVISIONA_UTENTI: bool = False

    @property
    def sso_enabled(self) -> bool:
        return bool(self.SSO_ISSUER and self.SSO_CLIENT_ID and self.SSO_CLIENT_SECRET and self.SSO_PUBLIC_URL)

    # Sincronizzazione utenti da Microsoft Entra ID (offboarding/onboarding) - solo
    # da ambiente. Riusa l'app registration Graph (permessi applicativi
    # User.Read.All e GroupMember.Read.All con consenso admin). Il gruppo Entra
    # indicato definisce chi fa parte della piattaforma: chi esce dal gruppo o ha
    # l'account disabilitato viene disattivato. ENTRA_SYNC_AUTO=true esegue il
    # giro ogni notte da solo (con un freno se le modifiche sono troppe).
    ENTRA_SYNC_GRUPPO_ID: Optional[str] = None
    ENTRA_SYNC_AUTO: bool = False

    @property
    def entra_sync_enabled(self) -> bool:
        return bool(self.graph_enabled and self.ENTRA_SYNC_GRUPPO_ID)

    # Reti dei proxy/bilanciatori davanti alla piattaforma (separate da virgola, es.
    # "10.0.0.0/8,192.168.1.5"). Solo da queste la piattaforma crede agli header che
    # dicono chi e' il client (X-Forwarded-For, CF-Connecting-IP): serve all'IP
    # nell'audit e ai limiti di tentativi. Vuoto (default) = nessun proxy fidato: si usa
    # l'indirizzo di chi si connette davvero, che non si puo' falsificare ma dietro un
    # proxy aziendale sarebbe sempre quello del proxy.
    PROXY_FIDUCIARI: str = ""
    # true solo se davanti c'e' Cloudflare (tunnel o proxy): allora l'IP del client si legge da
    # CF-Connecting-IP. Altrimenti quell'header si ignora anche se arriva da un proxy fidato,
    # perche' un proxy aziendale qualsiasi lo lascerebbe passare cosi' come lo manda il client.
    PROXY_CLOUDFLARE: bool = False

    @property
    def reti_fiduciarie(self):
        import ipaddress
        reti = []
        for voce in (self.PROXY_FIDUCIARI or "").split(","):
            voce = voce.strip()
            if voce:
                try:
                    reti.append(ipaddress.ip_network(voce, strict=False))
                except ValueError:
                    print(f"[config] PROXY_FIDUCIARI: «{voce}» non e' un indirizzo o una rete valida, ignorato")
        return reti

settings = Settings()
