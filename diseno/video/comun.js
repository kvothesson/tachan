// Lo que comparten video.html y corto.html. generar.py deja en window.APP los colores y textos sacados de las apps,
// así un cambio de textos o de marca entra solo al regenerar. El diseño de cada pantalla sí está a mano en cada página.
for (const [nombre, valor] of Object.entries(APP.colores)) document.documentElement.style.setProperty("--" + nombre, valor);

document.body.insertAdjacentHTML("afterbegin", `<svg width="0" height="0" style="position:absolute">
  <defs>
    <linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b3a78"/><stop offset=".55" stop-color="#ff7a59"/><stop offset="1" stop-color="#ffc56b"/></linearGradient>
    <symbol id="foto" viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice">
      <rect width="320" height="200" fill="url(#cielo)"/>
      <circle cx="205" cy="118" r="30" fill="#fff0c2"/>
      <path d="M0 140 70 96l56 40 62-52 132 74v42H0z" fill="#3a2a56"/>
      <path d="M0 172l86-34 92 28 72-24 70 26v32H0z" fill="#1c1833"/>
    </symbol>
    <symbol id="i-ok" viewBox="0 0 24 24"><path d="m5 12.500 4.500 4.500L19 7.500" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></symbol>
    <symbol id="i-copiar" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2.500"/><path d="M15 5.500A1.500 1.500 0 0 0 13.500 4h-8A1.500 1.500 0 0 0 4 5.500v8A1.500 1.500 0 0 0 5.500 15"/></g></symbol>
    <symbol id="i-carpeta" viewBox="0 0 24 24"><path d="M3.500 6H9l2 2.500h9.500V19h-17z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></symbol>
    <symbol id="i-abrir" viewBox="0 0 24 24"><path d="M9 5H5v14h14v-4M13 5h6v6M19 5l-8 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
    <symbol id="i-bajar" viewBox="0 0 24 24"><path d="M12 4v12M6.500 11 12 16.500 17.500 11M5 20h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
    <symbol id="i-pc" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4.500h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z"/><path d="M8 20h8M12 16.500V20"/></g></symbol>
    <symbol id="i-qr" viewBox="0 0 24 24"><path d="M4 9V5.500A1.500 1.500 0 0 1 5.500 4H9M15 4h3.500A1.500 1.500 0 0 1 20 5.500V9M20 15v3.500a1.500 1.500 0 0 1-1.500 1.500H15M9 20H5.500A1.500 1.500 0 0 1 4 18.500V15" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><path d="M10 9h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1z" fill="var(--accent)"/></symbol>
    <symbol id="i-envio" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2.400" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18C6 9 13 5 20 7"/><path d="M15.500 3.500 20.500 7l-3.200 5"/></g></symbol>
    <symbol id="i-compartir" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="2.500"/><circle cx="6" cy="12" r="2.500"/><circle cx="18" cy="19" r="2.500"/><path d="m8.200 10.800 7.600-4.500M8.200 13.200l7.600 4.500"/></g></symbol>
    <symbol id="icono" viewBox="0 0 108 108"><circle cx="54" cy="54" r="54" fill="var(--ground)"/><path d="M54 21 82.600 37.500v33L54 87 25.400 70.500v-33z" fill="var(--accent)"/><g transform="translate(36 36) scale(1.5)" fill="none" stroke="var(--on-accent)" stroke-width="2.600" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18C6 9 13 5 20 7"/><path d="M15.500 3.500 20.500 7l-3.200 5"/></g></symbol>
  </defs>
</svg>`);

// Junta los textos propios del video con los de las apps y los pone en cada [data-t].
function armarTextos(propios) {
  const L = { ...propios, ...APP.textos };
  L.vincular_con = APP.textos.vincular_con.replace("%1$s", propios.compu);
  L.enviado = APP.textos.enviado_a.replace("%1$s", propios.compu);
  L.vinculado = APP.textos.listo + ": " + propios.celu;
  document.querySelectorAll("[data-t]").forEach(e => e.textContent = L[e.dataset.t]);
  return L;
}

const $ = id => document.getElementById(id);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const prog = (t, a, b) => clamp((t - a) / (b - a));
const suave = x => 1 - (1 - x) * (1 - x);
const curva = x => x * x * (3 - 2 * x);
// Entra en a, sale en b, con fundido de d segundos.
const ventana = (t, a, b, d = .2) => Math.min(prog(t, a, a + d), 1 - prog(t, b, b + d));
const mostrar = (id, v) => { $(id).style.opacity = v; $(id).style.visibility = v > .001 ? "visible" : "hidden"; };
function pista(t, puntos) {
  if (t <= puntos[0][0]) return puntos[0].slice(1);
  for (let i = 1; i < puntos.length; i++) if (t < puntos[i][0]) {
    const k = curva((t - puntos[i - 1][0]) / (puntos[i][0] - puntos[i - 1][0]));
    return puntos[i].slice(1).map((v, j) => puntos[i - 1][j + 1] + (v - puntos[i - 1][j + 1]) * k);
  }
  return puntos[puntos.length - 1].slice(1);
}
