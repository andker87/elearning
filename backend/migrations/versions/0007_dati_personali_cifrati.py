"""dati personali cifrati: impronte per le ricerche esatte

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16 15:00:00

Aggiunge le impronte (email degli utenti, email e IP del registro attivita') e la chiave per calcolarle.
I dati esistenti restano in chiaro: si cifrano con `python -m app.cifratura_cli cifra` (serve CHIAVE_CIFRATURA).
"""
import secrets
import uuid

from alembic import op
import sqlalchemy as sa

from app.services import cifratura
from app.services.impronte import calcola


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

LOTTO = 5000


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def _chiave(conn) -> bytes:
    riga = conn.execute(sa.text("SELECT id, impronta_chiave FROM azienda LIMIT 1")).first()
    if riga is None:
        riga = (str(uuid.uuid4()), None)
        conn.execute(sa.text("INSERT INTO azienda (id, nazione) VALUES (:id, 'IT')"), {"id": riga[0]})
    if not riga[1]:
        conn.execute(sa.text("UPDATE azienda SET impronta_chiave = :k WHERE id = :id"),
                     {"k": cifratura.cifra_testo(secrets.token_hex(32)), "id": riga[0]})
        riga = (riga[0], conn.execute(sa.text("SELECT impronta_chiave FROM azienda WHERE id = :id"), {"id": riga[0]}).scalar())
    return bytes.fromhex(cifratura.decifra_testo(riga[1]))


def upgrade():
    conn = op.get_bind()
    if "impronta_chiave" not in _colonne("azienda"):
        op.add_column("azienda", sa.Column("impronta_chiave", sa.Text(), nullable=True))
    chiave = _chiave(conn)

    if "email_idx" not in _colonne("users"):
        op.add_column("users", sa.Column("email_idx", sa.String(), nullable=True))
    for id_, email in conn.execute(sa.text("SELECT id, email FROM users WHERE email_idx IS NULL")).fetchall():
        conn.execute(sa.text("UPDATE users SET email_idx = :i WHERE id = :id"),
                     {"i": calcola(chiave, cifratura.decifra_testo(email)), "id": id_})
    doppi = conn.execute(sa.text("SELECT count(*) FROM (SELECT email_idx FROM users GROUP BY email_idx HAVING count(*) > 1) d")).scalar()
    if doppi:
        raise RuntimeError("Ci sono utenti con la stessa email scritta con maiuscole diverse: unifica o elimina i doppioni e rilancia.")
    op.alter_column("users", "email_idx", nullable=False)
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_idx ON users (email_idx)")

    colonne = _colonne("audit_log")
    for nome in ("user_email_idx", "ip_idx"):
        if nome not in colonne:
            op.add_column("audit_log", sa.Column(nome, sa.String(), nullable=True))
    ultimo = None
    while True:   # a lotti: il registro puo' avere molte righe
        filtro = "AND id > :u" if ultimo else ""
        righe = conn.execute(sa.text(
            f"SELECT id, user_email, ip_address FROM audit_log WHERE (user_email IS NOT NULL OR ip_address IS NOT NULL) "
            f"AND user_email_idx IS NULL AND ip_idx IS NULL {filtro} ORDER BY id LIMIT {LOTTO}"), {"u": ultimo} if ultimo else {}).fetchall()
        if not righe:
            break
        conn.execute(sa.text("UPDATE audit_log SET user_email_idx = :e, ip_idx = :i WHERE id = :id"),
                     [{"e": calcola(chiave, cifratura.decifra_testo(e)), "i": calcola(chiave, cifratura.decifra_testo(i)), "id": id_}
                      for id_, e, i in righe])
        ultimo = righe[-1][0]
    # Per gli eventi sugli utenti il nome dell'entita' e' l'email: va nel dettaglio, che si cifra (entity_name resta in chiaro).
    conn.execute(sa.text("UPDATE audit_log SET detail = entity_name || COALESCE(' - ' || detail, ''), entity_name = NULL "
                         "WHERE entity_type = 'user' AND entity_name IS NOT NULL"))
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_user_email_idx ON audit_log (user_email_idx)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_ip_idx ON audit_log (ip_idx)")
    # Le colonne dei dati personali diventano TEXT (il valore cifrato e' piu' lungo dell'originale; in PostgreSQL non riscrive i dati).
    for tabella, colonna in (("users", "email"), ("users", "full_name"), ("organizzazioni", "referente"), ("organizzazioni", "email"),
                             ("organizzazioni", "telefono"), ("audit_log", "user_email"), ("audit_log", "ip_address")):
        op.alter_column(tabella, colonna, type_=sa.Text(), existing_nullable=colonna not in ("email", "full_name") or tabella != "users")


def downgrade():
    conn = op.get_bind()
    cifrati = conn.execute(sa.text(
        "SELECT (SELECT count(*) FROM users WHERE email LIKE 'enc:v1:%') + (SELECT count(*) FROM audit_log WHERE user_email LIKE 'enc:v1:%' "
        "OR ip_address LIKE 'enc:v1:%' OR detail LIKE 'enc:v1:%') + (SELECT count(*) FROM organizzazioni WHERE email LIKE 'enc:v1:%' "
        "OR referente LIKE 'enc:v1:%' OR telefono LIKE 'enc:v1:%')")).scalar()
    if cifrati:
        raise RuntimeError("Ci sono dati personali cifrati: prima esegui `python -m app.cifratura_cli decifra`.")
    op.drop_index("ix_audit_log_ip_idx", table_name="audit_log")
    op.drop_index("ix_audit_log_user_email_idx", table_name="audit_log")
    op.drop_column("audit_log", "ip_idx")
    op.drop_column("audit_log", "user_email_idx")
    op.drop_index("ix_users_email_idx", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.drop_column("users", "email_idx")
    op.drop_column("azienda", "impronta_chiave")
