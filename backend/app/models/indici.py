"""Indici sulle colonne usate per cercare le righe di una persona, di una sessione o di un corso.

PostgreSQL crea l'indice per le chiavi primarie e per gli unici, ma non per le chiavi esterne: senza questi indici
«Le mie iscrizioni», il Catalogo o le notifiche leggerebbero tutta la tabella a ogni richiesta (non si vede con pochi
dati, si sente con migliaia di iscrizioni). Stanno qui, in un posto solo, e li crea la migrazione 0017."""
from sqlalchemy import Index

from .autoiscrizione import AutoIscrizioneRichiesta
from .certificato import Certificato
from .comunicazione_edizione import ComunicazioneEdizione
from .edizione import Edizione, EdizioneDocente
from .evidenza import Evidenza
from .group import Group, UserGroup
from .iscrizione import Iscrizione
from .mansione import UserMansione
from .notification import Notification
from .percorso import PercorsoAssegnazione, PercorsoStep
from .push_subscription import PushSubscription
from .richiesta_iscrizione import RichiestaIscrizione
from .test import TentativoTest, Test
from .video import VideoCapitolo

INDICI = [
    Index("ix_iscrizioni_user_id", Iscrizione.user_id),
    Index("ix_evidenze_iscrizione_id", Evidenza.iscrizione_id),
    Index("ix_certificati_iscrizione_id", Certificato.iscrizione_id),
    Index("ix_notifications_user_id", Notification.user_id),
    Index("ix_percorso_assegnazioni_user_id", PercorsoAssegnazione.user_id),
    Index("ix_percorso_assegnazioni_percorso_id", PercorsoAssegnazione.percorso_id),
    Index("ix_percorso_steps_percorso_id", PercorsoStep.percorso_id),
    Index("ix_percorso_steps_corso_id", PercorsoStep.corso_id),
    Index("ix_edizioni_corso_id", Edizione.corso_id),
    Index("ix_edizione_docenti_edizione_id", EdizioneDocente.edizione_id),
    Index("ix_edizione_docenti_user_id", EdizioneDocente.user_id),
    Index("ix_tentativi_test_iscrizione_id", TentativoTest.iscrizione_id),
    Index("ix_test_corso_id", Test.corso_id),
    Index("ix_richieste_iscrizione_user_id", RichiestaIscrizione.user_id),
    Index("ix_autoiscrizione_richieste_edizione_id", AutoIscrizioneRichiesta.edizione_id),
    Index("ix_autoiscrizione_richieste_user_id", AutoIscrizioneRichiesta.user_id),
    Index("ix_user_groups_group_id", UserGroup.group_id),
    Index("ix_user_mansioni_mansione_id", UserMansione.mansione_id),
    Index("ix_comunicazioni_edizione_edizione_id", ComunicazioneEdizione.edizione_id),
    Index("ix_groups_parent_id", Group.parent_id),
    Index("ix_push_subscriptions_user_id", PushSubscription.user_id),
    Index("ix_video_capitoli_video_id", VideoCapitolo.video_id),
]
