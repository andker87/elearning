import React, { useRef, useState, useEffect } from "react";
import api, { erroreDi } from "../api";

export default function VideoPlayer({ video, iscrizioneId }) {
  const videoRef = useRef(null);
  const [current, setCurrent] = useState(0);
  const [maxRaggiunto, setMaxRaggiunto] = useState(0);
  const lastHeartbeat = useRef(0);
  const [accesso, setAccesso] = useState(null);   // indirizzi a tempo del video
  const [erroreVideo, setErroreVideo] = useState(null);

  const richiediAccesso = React.useCallback(() => {
    setErroreVideo(null);
    api.get(`/video/${video.id}/accesso`).then((r) => setAccesso(r.data))
      .catch((err) => setErroreVideo(erroreDi(err, "Impossibile aprire il video")));
  }, [video.id]);
  useEffect(() => { richiediAccesso(); }, [richiediAccesso]);

  // Gli indirizzi scadono dopo un po': se il video smette di caricarsi se ne chiedono di nuovi,
  // riprendendo dal punto in cui si era.
  const tentativi = useRef(0);
  function onErroreVideo() {
    if (++tentativi.current > 3) { setErroreVideo("Il video non si carica. Riprova più tardi."); return; }   // niente cicli infiniti
    const el = videoRef.current;
    const ripresa = el ? el.currentTime : 0;
    api.get(`/video/${video.id}/accesso`).then((r) => {
      setAccesso(r.data);
      setTimeout(() => { if (videoRef.current) videoRef.current.currentTime = ripresa; }, 300);
    }).catch((err) => setErroreVideo(erroreDi(err, "Impossibile aprire il video")));
  }

  useEffect(() => {
    api.get(`/iscrizioni/${iscrizioneId}/progresso`).then((r) => {
      setMaxRaggiunto(r.data.secondo_massimo_raggiunto);
      if (videoRef.current) videoRef.current.currentTime = 0; // riparte dall'inizio, ma lo skip resta sbloccato fino al max raggiunto
    });
  }, [iscrizioneId]);

  function onTimeUpdate() {
    const t = Math.floor(videoRef.current.currentTime);
    setCurrent(t);
    if (video.blocca_skip_avanti && t > maxRaggiunto + 2) {
      videoRef.current.currentTime = maxRaggiunto; // impedisce il salto in avanti lato client
      return;
    }
    if (t - lastHeartbeat.current >= 4) {
      lastHeartbeat.current = t;
      api.post(`/iscrizioni/${iscrizioneId}/progresso`, { secondo_corrente: t }).then((r) => {
        setMaxRaggiunto(r.data.secondo_massimo_raggiunto);
      });
    }
  }

  function onSeeking() {
    if (video.blocca_skip_avanti && videoRef.current.currentTime > maxRaggiunto + 2) {
      videoRef.current.currentTime = maxRaggiunto;
    }
  }

  function vaiACapitolo(sec) {
    if (video.blocca_skip_avanti && sec > maxRaggiunto + 2) return; // capitolo non ancora sbloccato
    videoRef.current.currentTime = sec;
  }

  const videoUrl = accesso?.video || null;
  const subUrl = accesso?.sottotitoli || null;

  return (
    <div className="video-layout">
      <div className="video-main">
        {erroreVideo && <div className="error-msg">{erroreVideo} <button type="button" className="secondary btn-sm" onClick={richiediAccesso}>Riprova</button></div>}
        {videoUrl && (
          <video key={videoUrl} ref={videoRef} controls width="100%" style={{ borderRadius: 12, background: "#000" }}
                 src={videoUrl} onError={onErroreVideo} onTimeUpdate={onTimeUpdate} onSeeking={onSeeking}>
            {subUrl && <track src={subUrl} kind="subtitles" srcLang="it" label="Italiano" default />}
          </video>
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
