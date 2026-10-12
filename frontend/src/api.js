import axios from "axios";

// Gli array diventano parametri ripetuti (?etichette=a&etichette=b), come si aspetta il backend.
const api = axios.create({ baseURL: "/api", paramsSerializer: { indexes: null } });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Le rotte di export (CSV/PDF) richiedono il Bearer token: un <a href> puro
// non lo manda, quindi si scarica come blob autenticato invece di navigare.
export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

export default api;
