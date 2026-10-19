"""permessi e qualifica sull'utente, gruppi = uffici, mansioni

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19 12:00:00

- il ruolo unico dell'utente diventa tre interruttori: is_admin, is_formazione, is_formatore;
- spariscono i quattro gruppi di sistema (Admin, Ufficio Formazione, Formatori, Utenti): il ruolo era
  gia' quello a decidere i permessi; chi era nel gruppo Formatori o e' docente di un'edizione
  diventa Formatore;
- i gruppi che non erano uffici diventano mansioni (con i loro membri e i percorsi assegnati a loro);
- ogni persona ha al piu' un ufficio (vincolo): chi ne aveva piu' d'uno resta nel primo, gli altri
  sono elencati nel messaggio della migrazione.

Idempotente come le altre: un database vecchio puo' arrivare qui con parte delle novita' gia' presenti.
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


def _colonne(tabella):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabella)}


def _esiste(tabella):
    return sa.inspect(op.get_bind()).has_table(tabella)


def _riferimenti_a_groups():
    """(tabella, colonna) di tutte le chiavi esterne che puntano a groups, tranne user_groups e groups stessa."""
    insp = sa.inspect(op.get_bind())
    out = []
    for t in insp.get_table_names():
        if t in ("user_groups",):
            continue
        for fk in insp.get_foreign_keys(t):
            if fk["referred_table"] == "groups":
                for c in fk["constrained_columns"]:
                    out.append((t, c))
    return out


def upgrade():
    conn = op.get_bind()

    # Nuovo valore «mansione» dell'enum di assegnazione. ADD VALUE non si puo' usare nella stessa
    # transazione (le migrazioni girano in una sola): si ricrea il tipo.
    etichette = {r[0] for r in conn.execute(sa.text(
        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'triggerassegnazione'")).fetchall()}
    if "mansione" not in etichette:
        op.execute("ALTER TYPE triggerassegnazione RENAME TO triggerassegnazione_vecchio")
        op.execute("CREATE TYPE triggerassegnazione AS ENUM ('manuale', 'ingresso_azienda', 'gruppo', 'mansione')")
        op.execute("ALTER TABLE percorsi_formativi ALTER COLUMN trigger_tipo TYPE triggerassegnazione "
                   "USING trigger_tipo::text::triggerassegnazione")
        op.execute("DROP TYPE triggerassegnazione_vecchio")

    # --- utenti: da ruolo a interruttori -------------------------------------------------------
    nuove = _colonne("users")
    for nome in ("is_admin", "is_formazione", "is_formatore"):
        if nome not in nuove:
            op.add_column("users", sa.Column(nome, sa.Boolean(), nullable=False, server_default="false"))
    if "role" in _colonne("users"):
        conn.execute(sa.text("UPDATE users SET is_admin = true WHERE role::text = 'admin_tecnico'"))
        conn.execute(sa.text("UPDATE users SET is_formazione = true WHERE role::text = 'training_admin'"))
    if "is_system" in _colonne("groups"):
        conn.execute(sa.text(
            "UPDATE users SET is_formatore = true WHERE id IN (SELECT ug.user_id FROM user_groups ug "
            "JOIN groups g ON g.id = ug.group_id WHERE g.is_system AND g.name = 'Formatori')"))
    if _esiste("edizione_docenti"):
        conn.execute(sa.text("UPDATE users SET is_formatore = true WHERE id IN (SELECT user_id FROM edizione_docenti)"))
    if "role" in _colonne("users"):
        op.drop_column("users", "role")
    op.execute("DROP TYPE IF EXISTS userrole")

    # --- mansioni ------------------------------------------------------------------------------
    if not _esiste("mansioni"):
        op.create_table(
            "mansioni",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("color", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    if not _esiste("user_mansioni"):
        op.create_table(
            "user_mansioni",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("mansione_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["mansione_id"], ["mansioni.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "mansione_id", name="uq_user_mansioni"),
        )
    if "trigger_mansione_id" not in _colonne("percorsi_formativi"):
        op.add_column("percorsi_formativi", sa.Column("trigger_mansione_id", sa.UUID(), nullable=True))
        op.create_foreign_key("percorsi_formativi_trigger_mansione_id_fkey", "percorsi_formativi", "mansioni", ["trigger_mansione_id"], ["id"])

    # --- gruppi: via i gruppi di sistema; i gruppi che non sono uffici diventano mansioni --------
    cols_g = _colonne("groups")
    if "is_system" in cols_g:
        sistema = [r[0] for r in conn.execute(sa.text("SELECT id FROM groups WHERE is_system")).fetchall()]
        for gid in sistema:
            conn.execute(sa.text("DELETE FROM user_groups WHERE group_id = :g"), {"g": gid})
        conn.execute(sa.text("UPDATE groups SET parent_id = NULL WHERE parent_id IN (SELECT id FROM groups WHERE is_system)"))
        conn.execute(sa.text("DELETE FROM groups WHERE is_system"))

    nomi_usati = {r[0].lower() for r in conn.execute(sa.text("SELECT name FROM mansioni")).fetchall()}
    non_uffici = conn.execute(sa.text("SELECT id, name, description, color, is_active FROM groups WHERE NOT is_ufficio")).fetchall()
    convertiti = []
    riferimenti = _riferimenti_a_groups()
    for gid, nome, descr, colore, attivo in non_uffici:
        usato_altrove = any(
            conn.execute(sa.text(f'SELECT 1 FROM "{t}" WHERE "{c}" = :g LIMIT 1'), {"g": gid}).first()
            for t, c in riferimenti if (t, c) not in (("groups", "parent_id"), ("percorsi_formativi", "trigger_gruppo_id")))
        if usato_altrove:
            log.warning("Il gruppo «%s» non e' un ufficio ma e' usato dal fabbisogno formativo: resta un ufficio.", nome)
            continue
        base, n = nome, 1
        while nome.lower() in nomi_usati:
            n += 1
            nome = f"{base} ({n})"
        nomi_usati.add(nome.lower())
        mid = conn.execute(sa.text("SELECT gen_random_uuid()")).scalar()
        conn.execute(sa.text("INSERT INTO mansioni (id, name, description, color, is_active) VALUES (:i, :n, :d, :c, :a)"),
                     {"i": mid, "n": nome, "d": descr, "c": colore, "a": bool(attivo) if attivo is not None else True})
        conn.execute(sa.text(
            "INSERT INTO user_mansioni (id, user_id, mansione_id) SELECT gen_random_uuid(), user_id, :m FROM user_groups WHERE group_id = :g"),
            {"m": mid, "g": gid})
        conn.execute(sa.text(
            "UPDATE percorsi_formativi SET trigger_tipo = 'mansione', trigger_mansione_id = :m, trigger_gruppo_id = NULL "
            "WHERE trigger_gruppo_id = :g"), {"m": mid, "g": gid})
        convertiti.append((gid, nome))
    ids = [g for g, _ in convertiti]
    if ids:
        figli = conn.execute(sa.text("SELECT name FROM groups WHERE parent_id = ANY(:ids) AND id <> ALL(:ids)"), {"ids": ids}).fetchall()
        if figli:
            log.warning("Uffici che stavano sotto un gruppo diventato mansione e ora sono in cima all'albero: %s",
                        ", ".join(sorted(f[0] for f in figli)))
        conn.execute(sa.text("UPDATE groups SET parent_id = NULL WHERE parent_id = ANY(:ids)"), {"ids": ids})
        conn.execute(sa.text("DELETE FROM user_groups WHERE group_id = ANY(:ids)"), {"ids": ids})
        conn.execute(sa.text("DELETE FROM groups WHERE id = ANY(:ids)"), {"ids": ids})
        log.warning("Gruppi diventati mansioni: %s. Le mansioni non hanno sottogruppi: un percorso assegnato a un gruppo "
                    "raggiungeva anche i sottogruppi, ora solo chi ha la mansione.", ", ".join(sorted(n for _, n in convertiti)))
    conn.execute(sa.text("UPDATE groups SET is_ufficio = true"))

    # --- un solo ufficio per persona ---------------------------------------------------------------
    doppi = conn.execute(sa.text(
        "SELECT user_id, count(*) FROM user_groups GROUP BY user_id HAVING count(*) > 1")).fetchall()
    if doppi:
        conn.execute(sa.text(
            "DELETE FROM user_groups WHERE id IN (SELECT id FROM ("
            "SELECT id, row_number() OVER (PARTITION BY user_id ORDER BY created_at NULLS LAST, id) AS n FROM user_groups) t WHERE n > 1)"))
        log.warning("%d persone erano in piu' uffici: restano nel primo. Controlla gli uffici di: %s", len(doppi),
                    ", ".join(str(d[0]) for d in doppi))
    insp = sa.inspect(conn)
    if "uq_user_groups_user" not in {u["name"] for u in insp.get_unique_constraints("user_groups")}:
        op.create_unique_constraint("uq_user_groups_user", "user_groups", ["user_id"])

    if "permissions" in cols_g:
        op.drop_column("groups", "permissions")
    if "is_system" in cols_g:
        op.drop_column("groups", "is_system")


def downgrade():
    raise RuntimeError("Migrazione non reversibile: ruoli, gruppi di sistema e mansioni sono stati trasformati. Ripristina una copia del database.")
