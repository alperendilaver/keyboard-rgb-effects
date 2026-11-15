"use strict";

/* Dalga arayuzu. Python tarafi (arayuz_web.py) window.pywebview.api ile
   cagrilir; her kare window.dalgaKare({kare, galeri?, durum?}) ile gelir. */

const $ = (s) => document.querySelector(s);

// TKL duzeni, tus genisligi cinsinden. Negatif sayi = bosluk. (dalga.py ile ayni)
const DUZEN = [
  [1, -1, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.25, 1, 1, 1],
  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, -0.25, 1, 1, 1],
  [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, -0.25, 1, 1, 1],
  [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25],
  [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.75, -1.25, 1],
  [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25, -0.25, 1, 1, 1],
];
const GENISLIK = 18.25;
const BOLGE = 8;

const RENKLER = ["#ff3b30", "#ff9500", "#ffd60a", "#30d158", "#00c7be",
  "#0a84ff", "#5e5ce6", "#bf5af2", "#ff2d55", "#ffffff"];

let api = null;
let ayar = {};
let efektler = [];
let modlar = [];
let calisiyor = false;

/* ---------------- Klavye ---------------- */
const klavye = $("#klavye");
const glow = $("#glow");
let birim = 30;

function klavyeCiz() {
  const stage = $("#stage");
  const yer = stage.clientWidth - 64 - 24;
  birim = Math.max(20, Math.min(40, Math.floor(yer / GENISLIK)));
  const bosluk = Math.max(2, Math.round(birim * 0.09));
  klavye.innerHTML = '<div class="kb-body"></div>';
  klavye.style.width = GENISLIK * birim + "px";
  klavye.style.height = 6.5 * birim + "px";
  DUZEN.forEach((satir, si) => {
    let x = 0;
    const y = si * birim + (si > 0 ? 0.5 * birim : 0);
    for (const g of satir) {
      if (g < 0) { x -= g; continue; }
      const k = document.createElement("div");
      const z = Math.min(BOLGE - 1, Math.floor(((x + g / 2) / GENISLIK) * BOLGE));
      k.className = "key";
      k.style.cssText =
        `left:${x * birim + bosluk / 2}px;top:${y + bosluk / 2}px;` +
        `width:${g * birim - bosluk}px;height:${birim - bosluk}px;` +
        `--c:var(--c${z});--k:var(--k${z})`;
      klavye.appendChild(k);
      x += g;
    }
  });
  if (!glow.children.length) {
    for (let i = 0; i < BOLGE; i++) glow.appendChild(document.createElement("i"));
  }
}

function bolgeRengi([r, g, b]) {
  // parlakligi ayir: renk tonunu tam parlaklikta, gucu ayrica ver
  const m = Math.max(r, g, b);
  if (m <= 0) return { c: "#000", k: 0, glow: "transparent" };
  const k = m / 255;
  const ton = `rgb(${Math.round(r / k)},${Math.round(g / k)},${Math.round(b / k)})`;
  return { c: ton, k: Math.min(1, 0.12 + k * 0.95), glow: `rgba(${r},${g},${b},${Math.min(1, k * 1.2)})` };
}

let sonKare = "";
function kareGoster(kare) {
  const anahtar = kare.join("|");
  if (anahtar === sonKare) return;
  sonKare = anahtar;
  const st = klavye.style;
  kare.forEach((rgb, i) => {
    const b = bolgeRengi(rgb);
    st.setProperty(`--c${i}`, b.c);
    st.setProperty(`--k${i}`, b.k.toFixed(3));
    glow.children[i] && (glow.children[i].style.background = b.glow);
  });
}

/* ---------------- Efekt listesi ---------------- */
const liste = $("#efektListesi");
const seritler = {};

function listeCiz() {
  liste.innerHTML = "";
  for (const e of efektler) {
    const b = document.createElement("button");
    b.className = "effect";
    b.setAttribute("role", "option");
    b.dataset.id = e.id;
    b.title = e.aciklama;
    b.innerHTML =
      `<span class="effect-text"><div class="effect-name"></div><div class="effect-desc"></div></span>` +
      `<span class="strip">${"<i></i>".repeat(BOLGE)}</span>`;
    b.querySelector(".effect-name").textContent = e.ad;
    b.querySelector(".effect-desc").textContent = e.aciklama;
    b.addEventListener("click", () => efektSec(e.id));
    liste.appendChild(b);
    seritler[e.id] = [...b.querySelectorAll(".strip i")];
  }
  $("#efektSayisi").textContent = efektler.length;
}

function galeriGoster(galeri) {
  for (const id in galeri) {
    const s = seritler[id];
    if (!s) continue;
    galeri[id].forEach(([r, g, b], i) => {
      s[i].style.background = (r | g | b) ? `rgb(${r},${g},${b})` : "";
    });
  }
}

function efektSec(id) {
  ayarGonder({ efekt: id });
}

document.addEventListener("keydown", (ev) => {
  if (ev.target.tagName === "INPUT") return;
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault();
    const i = efektler.findIndex((e) => e.id === ayar.efekt);
    const j = (i + (ev.key === "ArrowDown" ? 1 : -1) + efektler.length) % efektler.length;
    efektSec(efektler[j].id);
    liste.querySelector(`[data-id="${efektler[j].id}"]`)?.scrollIntoView({ block: "nearest" });
  } else if (ev.code === "Space") {
    ev.preventDefault();
    baslatDurdur();
  }
});

/* ---------------- Kontroller ---------------- */
const BICIM = {
  hiz: (v) => (+v).toFixed(1),
  kalinlik: (v) => (+v).toFixed(1),
  parlaklik: (v) => `${Math.round(v)}%`,
  bekleme_hiz: (v) => `${(+v).toFixed(1)}×`,
  bekleme_parlaklik: (v) => `${Math.round(v)}%`,
};

function kaydiriciBagla(id) {
  const el = document.getElementById(id);
  const out = document.querySelector(`output[for="${id}"]`);
  const boya = () => {
    const p = ((el.value - el.min) / (el.max - el.min)) * 100;
    el.style.setProperty("--p", p + "%");
    out.textContent = BICIM[id](el.value);
  };
  el.addEventListener("input", () => { boya(); ayarGonder({ [id]: +el.value }, false); });
  el._boya = boya;
}

function segmentBagla(kap, anahtar) {
  kap.addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-v]");
    if (b) ayarGonder({ [anahtar]: b.dataset.v });
  });
}

function anahtarBagla(el, anahtar) {
  el.addEventListener("click", () => ayarGonder({ [anahtar]: !ayar[anahtar] }));
}

const secici = $("#renkSecici");
let seciciHedef = null;
secici.addEventListener("input", () => seciciHedef && ayarGonder({ [seciciHedef]: secici.value }, false));

function renkleriCiz(kap) {
  const anahtar = kap.dataset.ayar;
  kap.innerHTML = "";
  for (const r of RENKLER) {
    const b = document.createElement("button");
    b.className = "swatch";
    b.setAttribute("role", "radio");
    b.style.setProperty("--s", r);
    b.dataset.v = r;
    b.title = r;
    b.addEventListener("click", () => ayarGonder({ [anahtar]: r }));
    kap.appendChild(b);
  }
  const ozel = document.createElement("button");
  ozel.className = "swatch swatch-custom";
  ozel.title = "Özel renk";
  ozel.addEventListener("click", () => {
    seciciHedef = anahtar;
    secici.value = ayar[anahtar];
    secici.click();
  });
  kap.appendChild(ozel);
}

function modlariCiz() {
  const kap = $("#bekModlari");
  kap.innerHTML = "";
  for (const m of modlar) {
    const b = document.createElement("button");
    b.className = "mode";
    b.setAttribute("role", "radio");
    b.dataset.v = m.id;
    b.innerHTML = `<span class="mode-preview ${m.id}"></span><span></span>`;
    b.lastChild.textContent = m.ad;
    kap.appendChild(b);
  }
  segmentBagla(kap, "bekleme_mod");
}

/* ---------------- Ayarlari ekrana yansit ---------------- */
function isaretle(kap, deger) {
  kap.querySelectorAll("[data-v]").forEach((b) =>
    b.setAttribute("aria-checked", String(b.dataset.v.toLowerCase() === String(deger).toLowerCase())));
}

function goster() {
  const e = efektler.find((x) => x.id === ayar.efekt) || efektler[0];
  if (e) {
    $("#efektAdi").textContent = e.ad;
    $("#efektAciklama").textContent = e.aciklama;
  }
  liste.querySelectorAll(".effect").forEach((b) =>
    b.setAttribute("aria-selected", String(b.dataset.id === ayar.efekt)));

  for (const id of Object.keys(BICIM)) {
    const el = document.getElementById(id);
    if (document.activeElement !== el) el.value = ayar[id];
    el._boya();
  }

  isaretle($("#renkModu"), ayar.mod);
  const renkler = $("#renkler");
  isaretle(renkler, ayar.renk);
  renkler.style.opacity = ayar.mod === "sabit" ? "1" : ".35";
  renkler.style.pointerEvents = ayar.mod === "sabit" ? "" : "none";
  $("#renkNotu").textContent = ayar.mod === "sabit"
    ? "Her basış seçili renkte yanar"
    : "Her basışta renk gökkuşağı boyunca kayar";
  ozelRenk(renkler, ayar.renk);

  $("#bekAcik").setAttribute("aria-checked", String(!!ayar.bekleme_acik));
  $("#bekGovde").classList.toggle("off", !ayar.bekleme_acik);
  isaretle($("#bekModlari"), ayar.bekleme_mod);
  document.querySelectorAll(".mode-preview.sabit, .mode-preview.nefes")
    .forEach((p) => p.style.setProperty("--s", ayar.bekleme_renk));
  const nefes = ayar.bekleme_mod === "nefes";
  $("#nefesBolum").classList.toggle("hidden", !nefes);
  isaretle($("#nefesRenk"), ayar.nefes_renk);
  const renkli = ayar.bekleme_mod === "sabit" || (nefes && ayar.nefes_renk === "sabit");
  $("#bekRenkBolum").classList.toggle("hidden", !renkli);
  const bekRenkler = $("#bekRenkler");
  isaretle(bekRenkler, ayar.bekleme_renk);
  ozelRenk(bekRenkler, ayar.bekleme_renk);
  $("#bekHizAlan").classList.toggle("disabled", ayar.bekleme_mod === "sabit");

  $("#ggGeri").setAttribute("aria-checked", String(!!ayar.gg_geri));
}

function ozelRenk(kap, renk) {
  const hazir = RENKLER.includes(String(renk).toLowerCase());
  const ozel = kap.querySelector(".swatch-custom");
  ozel.setAttribute("aria-checked", String(!hazir));
  ozel.style.setProperty("--s", hazir ? "var(--panel)" : renk);
}

let gonderZamani = null;
let bekleyen = {};
function ayarGonder(degisen, yenidenCiz = true) {
  Object.assign(ayar, degisen);
  if (yenidenCiz) goster();
  Object.assign(bekleyen, degisen);
  if (gonderZamani) return;
  gonderZamani = setTimeout(async () => {
    const paket = bekleyen;
    bekleyen = {};
    gonderZamani = null;
    if (!api) return;
    const yeni = await api.ayar(paket);
    // Python degerleri sinirladiysa onu esas al (surukleme sirasinda degil)
    if (yeni && !Object.keys(bekleyen).length) { ayar = yeni; goster(); }
  }, 30);
}

/* ---------------- Baslat / durdur ---------------- */
const btn = $("#btnBaslat");
async function baslatDurdur() {
  if (!api || btn.classList.contains("busy")) return;
  btn.classList.add("busy");
  $("#btnBaslatYazi").textContent = calisiyor ? "Durduruluyor" : "Bağlanıyor";
  try {
    durumGoster(calisiyor ? await api.durdur() : await api.baslat());
  } finally {
    btn.classList.remove("busy");
  }
}
btn.addEventListener("click", baslatDurdur);

function durumGoster(d) {
  if (!d) return;
  calisiyor = d.calisiyor;
  btn.classList.toggle("running", calisiyor);
  $("#btnBaslatYazi").textContent = calisiyor ? "Durdur" : "Başlat";
  const s = $("#status");
  s.classList.toggle("on", calisiyor && !d.hata);
  s.classList.toggle("err", !!d.hata);
  $("#statusText").textContent = d.mesaj;
  $("#stage").classList.toggle("live", calisiyor);
  $("#ipucuYazi").textContent = calisiyor
    ? "Canlı — klavyende yazdıkça burada da görünür"
    : "Denemek için klavyeye tıkla";
}

$("#stage").addEventListener("pointerdown", (ev) => {
  if (calisiyor || !api) return;
  const r = klavye.getBoundingClientRect();
  api.deneme(((ev.clientX - r.left) / r.width) * BOLGE);
});

/* ---------------- Python'dan gelen kareler ---------------- */
window.dalgaKare = (p) => {
  kareGoster(p.kare);
  if (p.galeri) galeriGoster(p.galeri);
  if (p.durum) durumGoster(p.durum);
};

/* ---------------- Baslangic ---------------- */
async function basla(apiNesnesi) {
  api = apiNesnesi;
  const v = await api.baslangic();
  ayar = v.ayar;
  efektler = v.efektler;
  modlar = v.bekleme_modlari;
  $("#surum").textContent = v.surum;
  listeCiz();
  modlariCiz();
  goster();
}

["hiz", "kalinlik", "parlaklik", "bekleme_hiz", "bekleme_parlaklik"].forEach(kaydiriciBagla);
segmentBagla($("#renkModu"), "mod");
segmentBagla($("#nefesRenk"), "nefes_renk");
anahtarBagla($("#bekAcik"), "bekleme_acik");
anahtarBagla($("#ggGeri"), "gg_geri");
renkleriCiz($("#renkler"));
renkleriCiz($("#bekRenkler"));
$("#btnMin").addEventListener("click", () => api && api.kucult());
$("#btnClose").addEventListener("click", () => api && api.kapat());

klavyeCiz();
new ResizeObserver(() => { klavyeCiz(); sonKare = ""; }).observe($("#stage"));

if (window.pywebview && window.pywebview.api) basla(window.pywebview.api);
else window.addEventListener("pywebviewready", () => basla(window.pywebview.api));
