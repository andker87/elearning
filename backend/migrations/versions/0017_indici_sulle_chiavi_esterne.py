"""indici sulle chiavi esterne

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-22 18:00:00

- indici sulle colonne con cui si cercano le righe di una persona, di una sessione o di un corso (iscrizioni, evidenze,
  attestati, notifiche, percorsi, docenti, richieste...). Nessun dato cambia; la migrazione e' ripetibile.
"""
from alembic import op
import sqlalchemy as sa


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

INDICI = [
    ("ix_iscrizioni_user_id", "iscrizioni", "user_id"),
    ("ix_evidenze_iscrizione_id", "evidenze", "iscrizione_id"),
    ("ix_certificati_iscrizione_id", "certificati", "iscrizione_id"),
    ("ix_notifications_user_id", "notifications", "user_id"),
    ("ix_percorso_assegnazioni_user_id", "percorso_assegnazioni", "user_id"),
    ("ix_percorso_assegnazioni_percorso_id", "percorso_assegnazioni", "percorso_id"),
    ("ix_percorso_steps_percorso_id", "percorso_steps", "percorso_id"),
    ("ix_percorso_steps_corso_id", "percorso_steps", "corso_id"),
    ("ix_edizioni_corso_id", "edizioni", "corso_id"),
    ("ix_edizione_docenti_edizione_id", "edizione_docenti", "edizione_id"),
    ("ix_edizione_docenti_user_id", "edizione_docenti", "user_id"),
    ("ix_tentativi_test_iscrizione_id", "tentativi_test", "iscrizione_id"),
    ("ix_test_corso_id", "test", "corso_id"),
    ("ix_richieste_iscrizione_user_id", "richieste_iscrizione", "user_id"),
    ("ix_autoiscrizione_richieste_edizione_id", "autoiscrizione_richieste", "edizione_id"),
    ("ix_autoiscrizione_richieste_user_id", "autoiscrizione_richieste", "user_id"),
    ("ix_user_groups_group_id", "user_groups", "group_id"),
    ("ix_user_mansioni_mansione_id", "user_mansioni", "mansione_id"),
    ("ix_comunicazioni_edizione_edizione_id", "comunicazioni_edizione", "edizione_id"),
    ("ix_groups_parent_id", "groups", "parent_id"),
    ("ix_push_subscriptions_user_id", "push_subscriptions", "user_id"),
    ("ix_video_capitoli_video_id", "video_capitoli", "video_id"),
]


def upgrade():
    esistenti = {i["name"] for t in {t for _, t, _ in INDICI} for i in sa.inspect(op.get_bind()).get_indexes(t)}
    for nome, tabella, colonna in INDICI:
        if nome not in esistenti:
            op.create_index(nome, tabella, [colonna])


def downgrade():
    esistenti = {i["name"] for t in {t for _, t, _ in INDICI} for i in sa.inspect(op.get_bind()).get_indexes(t)}
    for nome, tabella, _ in INDICI:
        if nome in esistenti:
            op.drop_index(nome, table_name=tabella)
