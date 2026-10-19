"""Chi puo' fare cosa: ruoli fissi, nessun accesso senza token."""
import pytest

# (metodo, percorso, ruoli ammessi)
ADMIN = {"admin"}
FORMAZIONE = {"admin", "formazione"}
TUTTI = {"admin", "formazione", "utente"}

ENDPOINT = [
    ("GET", "/api/admin/audit", ADMIN),
    ("GET", "/api/admin/salute", ADMIN),
    ("GET", "/api/azienda", ADMIN),
    ("GET", "/api/auth/password-reset-richieste", ADMIN),
    ("GET", "/api/registro", FORMAZIONE),
    ("GET", "/api/registro/matrice", FORMAZIONE),
    ("GET", "/api/registro/pacchetto-ispezione", FORMAZIONE),
    ("GET", "/api/privacy/informativa", TUTTI),
    ("GET", "/api/privacy/export", TUTTI),
    ("GET", "/api/about", TUTTI),
    ("GET", "/api/auth/me", TUTTI),
]


@pytest.mark.parametrize("metodo,percorso,ammessi", ENDPOINT)
def test_permessi_per_ruolo(client, admin, formazione, utente, auth, metodo, percorso, ammessi):
    persone = {"admin": admin, "formazione": formazione, "utente": utente}
    for nome, persona in persone.items():
        r = client.request(metodo, percorso, headers=auth(persona))
        if nome in ammessi:
            assert r.status_code == 200, f"{nome} dovrebbe poter fare {metodo} {percorso}: {r.status_code}"
        else:
            assert r.status_code == 403, f"{nome} non dovrebbe poter fare {metodo} {percorso}: {r.status_code}"


@pytest.mark.parametrize("metodo,percorso,ammessi", ENDPOINT)
def test_senza_token_nessun_accesso(client, metodo, percorso, ammessi):
    assert client.request(metodo, percorso).status_code in (401, 403)


def test_utente_disattivato_non_entra_con_un_token_vecchio(client, db, utente, auth):
    intestazioni = auth(utente)
    utente.is_active = False
    db.commit()
    assert client.get("/api/auth/me", headers=intestazioni).status_code == 401


def test_solo_admin_crea_utenti_e_modifica_ruoli(client, formazione, utente, auth):
    corpo = {"email": "n@test.it", "full_name": "N", "password": "Password!Valida123"}
    assert client.post("/api/auth/users", headers=auth(formazione), json=corpo).status_code == 403
    assert client.put(f"/api/auth/users/{utente.id}", headers=auth(utente), json={"is_admin": True}).status_code == 403
