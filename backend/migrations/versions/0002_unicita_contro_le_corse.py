"""vincoli di unicita' contro le richieste in parallelo

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def _gia_presente(tabella, nome):
    """Un database arrivato dal vecchio percorso (senza migrazioni) puo' avere gia' il vincolo, perche'
    le sue tabelle nuove sono create dai modelli di oggi: in quel caso non si ripete."""
    insp = sa.inspect(op.get_bind())
    esistenti = {c["name"] for c in insp.get_unique_constraints(tabella)} | {i["name"] for i in insp.get_indexes(tabella)}
    return nome in esistenti


def upgrade():
    # Prima si eliminano gli eventuali doppioni gia' presenti (si tiene il piu' vecchio), altrimenti il vincolo non si crea.
    op.execute("""
        DELETE FROM gradimenti_docenti WHERE gradimento_id IN (
            SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY iscrizione_id ORDER BY created_at, id) AS n FROM gradimenti) t WHERE n > 1)
    """)
    op.execute("""
        DELETE FROM gradimenti WHERE id IN (
            SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY iscrizione_id ORDER BY created_at, id) AS n FROM gradimenti) t WHERE n > 1)
    """)
    op.execute("""
        DELETE FROM fabbisogno_campagna_inviti WHERE id IN (
            SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY campagna_id, ufficio_id ORDER BY created_at, id) AS n FROM fabbisogno_campagna_inviti) t WHERE n > 1)
    """)
    op.execute("""
        DELETE FROM richieste_corso_persone WHERE id IN (
            SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY richiesta_id, user_id ORDER BY id) AS n FROM richieste_corso_persone) t WHERE n > 1)
    """)
    # Le iscrizioni doppie non si cancellano (hanno evidenze): le piu' recenti diventano "annullate".
    op.execute("""
        UPDATE iscrizioni SET stato = 'annullato' WHERE id IN (
            SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY edizione_id, user_id ORDER BY created_at, id) AS n
                            FROM iscrizioni WHERE stato <> 'annullato') t WHERE n > 1)
    """)
    if not _gia_presente('gradimenti', 'uq_gradimento_iscrizione'):
        op.create_unique_constraint('uq_gradimento_iscrizione', 'gradimenti', ['iscrizione_id'])
    if not _gia_presente('fabbisogno_campagna_inviti', 'uq_invito_campagna_ufficio'):
        op.create_unique_constraint('uq_invito_campagna_ufficio', 'fabbisogno_campagna_inviti', ['campagna_id', 'ufficio_id'])
    if not _gia_presente('richieste_corso_persone', 'uq_richiesta_persona'):
        op.create_unique_constraint('uq_richiesta_persona', 'richieste_corso_persone', ['richiesta_id', 'user_id'])
    if not _gia_presente('iscrizioni', 'uq_iscrizione_viva'):
        op.create_index('uq_iscrizione_viva', 'iscrizioni', ['edizione_id', 'user_id'], unique=True, postgresql_where=sa.text("stato <> 'annullato'"))


def downgrade():
    op.drop_index('uq_iscrizione_viva', table_name='iscrizioni', postgresql_where=sa.text("stato <> 'annullato'"))
    op.drop_constraint('uq_richiesta_persona', 'richieste_corso_persone', type_='unique')
    op.drop_constraint('uq_invito_campagna_ufficio', 'fabbisogno_campagna_inviti', type_='unique')
    op.drop_constraint('uq_gradimento_iscrizione', 'gradimenti', type_='unique')
