import React, { useRef, useState, useEffect } from "react";
import api, { erroreDi } from "../api";

const CHIAVE_QUALITA = "qualita_video";

function etichettaQualita(altezza) {
  if (!altezza) return "Originale";
  return altezza >= 2160 ? "4K (2160p)" : `${altezza}p`;
}

// "Auto": la qualita' piu' alta che lo schermo puo' mostrare e la rete sembra reggere. Se il browser non dice
// nulla sulla rete si resta prudenti (fino a 720p): chi lavora da remoto non deve caricare piu' del necessario.
export function qualitaAutomatica(versioni, schermoAltezza, bandaMbps) {
  if (!versioni.length) return null;
  const budgetKbps = bandaMbps ? bandaMbps * 1000 * 0.7 : null;
  const adatte = versioni.filter((v) => {
    if (!v.altezza) return true;
    if (v.altezza > Math.max(schermoAltezza, versioni[0].altezza)) return false;
    return budgetKbps != null ? (v.bitrate_kbps || 0) <= budgetKbps : v.altezza <= 720;
  });
  return adatte.length ? adatte[adatte.length - 1] : versioni[0];
}

// Senza `iscrizioneId` e' un'anteprima (per chi gestisce la sessione): non registra l'avanzamento e non blocca i salti.
export default function VideoPlayer({ video, iscrizioneId }) {
  const videoRef = useRef(null);
  const [current, setCurrent] = useState(0);
  const [maxRaggiunto, setMaxRaggiunto] = useState(0);
  const lastHeartbeat = useRef(0);
  const [accesso, setAccesso] = useState(null);   // indirizzi a tempo del video
  const [erroreVideo, setErroreVideo] = useState(null);
  const [scelta, setScelta] = useState(() => {   // "auto" oppure l'altezza scelta (preferenza di questo browser)
    try { const s = localStorage.getItem(CHIAVE_QUALITA); return s && s !== "auto" ? Number(s) : "auto"; } catch { return "auto"; }
  });
  const [altezzaAuto, setAltezzaAuto] = useState(null);   // qualita' scelta dalla modalita' automatica
  const ripresa = useRef(null);   // punto e stato da ripristinare dopo un cambio di qualita' o di indirizzo

  const generazione = useRef(0);   // le risposte di una richiesta superata (altro video, nuovo tentativo) si scartano
  const richiediAccesso = React.useCallback(() => {
    const mia = ++generazione.current;
    setErroreVideo(null);
    api.get(`/video/${video.id}/accesso`).then((r) => { if (mia === generazione.current) setAccesso(r.data); })
      .catch((err) => { if (mia === generazione.current) setErroreVideo(erroreDi(err, "Impossibile aprire il video")); });
  }, [video.id]);
  useEffect(() => { setAccesso(null); richiediAccesso(); }, [richiediAccesso]);

  // Gli indirizzi scadono dopo un po': se il video smette di caricarsi se ne chiedono di nuovi,
  // riprendendo dal punto in cui si era.
  const tentativi = useRef(0);
  function onErroreVideo() {
    if (++tentativi.current > 3) { setErroreVideo("Il video non si carica. Riprova più tardi."); return; }   // niente cicli infiniti
    memorizzaPunto();
    const mia = ++generazione.current;
    api.get(`/video/${video.id}/accesso`).then((r) => {
      if (mia !== generazione.current) return;
      setAccesso(r.data);
    }).catch((err) => { if (mia === generazione.current) setErroreVideo(erroreDi(err, "Impossibile aprire il video")); });
  }
  function riprova() { tentativi.current = 0; richiediAccesso(); }
  function onVideoPronto() { tentativi.current = 0; }

  function memorizzaPunto() {
    const el = videoRef.current;
    if (el) ripresa.current = { tempo: el.currentTime, inRiproduzione: !el.paused && !el.ended };
  }
  function onMetadati() {   // dopo il cambio di qualita' si riparte dal punto in cui si era
    const el = videoRef.current;
    if (el && ripresa.current) {
      el.currentTime = ripresa.current.tempo;
      if (ripresa.current.inRiproduzione) el.play().catch(() => {});
      ripresa.current = null;
    }
  }
  function cambiaQualita(valore) {
    memorizzaPunto();
    const nuova = valore === "auto" ? "auto" : Number(valore);
    setScelta(nuova);
    try { localStorage.setItem(CHIAVE_QUALITA, String(nuova)); } catch { /* preferenza non salvabile: vale solo ora */ }
  }

  useEffect(() => {
    if (!iscrizioneId) return;
    api.get(`/iscrizioni/${iscrizioneId}/progresso`).then((r) => {
      setMaxRaggiunto(r.data.secondo_massimo_raggiunto);
      if (videoRef.current) videoRef.current.currentTime = 0; // riparte dall'inizio, ma lo skip resta sbloccato fino al max raggiunto
    });
  }, [iscrizioneId]);

  function onTimeUpdate() {
    const t = Math.floor(videoRef.current.currentTime);
    setCurrent(t);
    if (iscrizioneId && video.blocca_skip_avanti && t > maxRaggiunto + 2) {
      videoRef.current.currentTime = maxRaggiunto; // impedisce il salto in avanti lato client
      return;
    }
    if (iscrizioneId && t - lastHeartbeat.current >= 4) {
      lastHeartbeat.current = t;
      api.post(`/iscrizioni/${iscrizioneId}/progresso`, { secondo_corrente: t }).then((r) => {
        setMaxRaggiunto(r.data.secondo_massimo_raggiunto);
      });
    }
  }

  function onSeeking() {
    if (iscrizioneId && video.blocca_skip_avanti && videoRef.current.currentTime > maxRaggiunto + 2) {
      videoRef.current.currentTime = maxRaggiunto;
    }
  }

  function vaiACapitolo(sec) {
    if (iscrizioneId && video.blocca_skip_avanti && sec > maxRaggiunto + 2) return; // capitolo non ancora sbloccato
    videoRef.current.currentTime = sec;
  }

  const versioni = accesso?.versioni || [];
  // La qualita' automatica si decide una volta quando le qualita' sono note e poi resta ferma: se cambiasse a ogni
  // variazione della rete rilevata dal browser, il video si ricaricherebbe a meta' visione.
  useEffect(() => {
    if (!versioni.length) { setAltezzaAuto(null); return; }
    setAltezzaAuto((precedente) => (precedente != null && versioni.some((v) => v.altezza === precedente)) ? precedente
      : qualitaAutomatica(versioni, (window.screen?.height || 720) * (window.devicePixelRatio || 1), navigator.connection?.downlink).altezza);
  }, [accesso]);
  const automatica = versioni.find((v) => v.altezza === altezzaAuto) || versioni[0] || null;
  const attuale = (scelta !== "auto" && versioni.find((v) => v.altezza === scelta)) || automatica;
  const videoUrl = attuale?.url || accesso?.video || null;
  const subUrl = accesso?.sottotitoli || null;

  return (
    <div className="video-layout">
      <div className="video-main">
        {erroreVideo && <div className="error-msg">{erroreVideo} <button type="button" className="secondary btn-sm" onClick={riprova}>Riprova</button></div>}
        {videoUrl && (
          <video ref={videoRef} controls style={{ borderRadius: 12 }}
                 src={videoUrl} onError={onErroreVideo} onCanPlay={onVideoPronto} onLoadedMetadata={onMetadati} onTimeUpdate={onTimeUpdate} onSeeking={onSeeking}>
            {subUrl && <track src={subUrl} kind="subtitles" srcLang="it" label="Italiano" default />}
          </video>
        )}
        {versioni.length > 1 && (
          <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <label htmlFor="qualita-video" style={{ margin: 0 }}>Qualità</label>
            <select id="qualita-video" style={{ width: "auto" }} value={scelta === "auto" || !versioni.some((v) => v.altezza === scelta) ? "auto" : scelta}
                    onChange={(e) => cambiaQualita(e.target.value)}>
              <option value="auto">Automatica ({etichettaQualita(automatica?.altezza)})</option>
              {[...versioni].reverse().map((v) => <option key={v.altezza} value={v.altezza}>{etichettaQualita(v.altezza)}</option>)}
            </select>
            <span className="text-muted">Una qualità più bassa usa meno rete.</span>
          </div>
        )}
      </div>
      {video.capitoli?.length > 0 && (
        <div className="video-chapters">
          <h4>Capitoli</h4>
          <ul>
            {video.capitoli.map((c) => (
              <li key={c.id} className={current >= c.inizio_secondi ? "current" : ""} onClick={() => vaiACapitolo(c.inizio_secondi)}>
                {Math.floor(c.inizio_secondi / 60)}:{String(c.inizio_secondi % 60).padStart(2, "0")} — {c.titolo}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
