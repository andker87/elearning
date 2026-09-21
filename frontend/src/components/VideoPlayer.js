import React, { useRef, useState, useEffect } from "react";
import api from "../api";

export default function VideoPlayer({ video, iscrizioneId }) {
  const videoRef = useRef(null);
  const [current, setCurrent] = useState(0);
  const [maxRaggiunto, setMaxRaggiunto] = useState(0);
  const lastHeartbeat = useRef(0);

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

  const videoUrl = video.file_path ? `/videos/${video.file_path.split("/").pop()}` : null;
  const subUrl = video.sottotitoli_path ? `/videos/${video.sottotitoli_path.split("/").pop()}` : null;

  return (
    <div className="video-layout">
      <div className="video-main">
        <video ref={videoRef} controls width="100%" style={{ borderRadius: 12, background: "#000" }}
               onTimeUpdate={onTimeUpdate} onSeeking={onSeeking}>
          <source src={videoUrl} type="video/mp4" />
          {subUrl && <track src={subUrl} kind="subtitles" srcLang="it" label="Italiano" default />}
        </video>
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
