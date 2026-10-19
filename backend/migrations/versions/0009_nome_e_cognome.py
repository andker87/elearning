"""nome e cognome separati

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19 15:00:00

Il nome intero dell'utente diventa due campi, `nome` e `cognome`. I dati esistenti si dividono cosi': la prima parola
e' il nome, il resto il cognome (non c'e' una regola esatta: «Maria Grazia Rossi», «Mario De Luca»; la persona si
corregge dalla sua scheda). Se la cifratura e' attiva i nuovi valori si scrivono cifrati.
"""
from alembic import op
import sqlalchemy as sa

from app.services import cifratura


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def _dividi(testo):
    # Copia della regola di services/persone.dividi_nome: una migrazione non deve cambiare se il codice cambia.
    parole = (testo or "").split()
    if not parole:
        return "", ""
    return parole[0], " ".join(parole[1:])


def upgrade():
    conn = op.get_bind()
    for nome in ("nome", "cognome"):
        if nome not in _colonne("users"):
            op.add_column("users", sa.Column(nome, sa.Text(), nullable=True))
    if "full_name" in _colonne("users"):
        for id_, intero in conn.execute(sa.text("SELECT id, full_name FROM users WHERE nome IS NULL OR cognome IS NULL")).fetchall():
            nome, cognome = _dividi(cifratura.decifra_testo(intero))
            conn.execute(sa.text("UPDATE users SET nome = :n, cognome = :c WHERE id = :id"),
                         {"n": cifratura.cifra_testo(nome), "c": cifratura.cifra_testo(cognome), "id": id_})
        op.drop_column("users", "full_name")
    op.alter_column("users", "nome", nullable=False)
    op.alter_column("users", "cognome", nullable=False)


def downgrade():
    raise RuntimeError("Migrazione non reversibile: nome e cognome sono stati uniti o divisi. Ripristina una copia del database.")
