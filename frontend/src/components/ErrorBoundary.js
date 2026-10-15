import React from "react";

// Se una pagina va in errore mostra un messaggio invece dello schermo bianco.
export default class ErrorBoundary extends React.Component {
  state = { errore: null };
  static getDerivedStateFromError(errore) { return { errore }; }
  componentDidCatch(errore, info) { console.error("Errore di interfaccia:", errore, info?.componentStack); }
  componentDidUpdate(prev) { if (this.state.errore && prev.chiave !== this.props.chiave) this.setState({ errore: null }); }
  render() {
    if (!this.state.errore) return this.props.children;
    return (
      <div className="card" style={{ margin: "2rem auto", maxWidth: 520 }}>
        <h3>Qualcosa non ha funzionato</h3>
        <p className="text-muted" style={{ fontSize: 14 }}>La pagina ha avuto un problema imprevisto. Puoi riprovare; se si ripete, segnalalo all'amministratore.</p>
        <button type="button" onClick={() => window.location.reload()}>Ricarica la pagina</button>
      </div>
    );
  }
}
