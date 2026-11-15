"""
DALGA v0.5 - Apex 3 TKL icin tusa basinca bolgesel dalga efekti (arayuzlu)

Gerekenler:
    - apex_hid.py ve gg.py bu dosyayla AYNI klasorde olmali
    - pip install keyboard

SteelSeries GG acik kalabilir: Dalga calisirken GG isiklari duraklatilir,
durunca GG'deki isik profili geri gelir.
OpenRGB kapali olsun.
Calistir:  python dalga.py
Ayarlar, ayni klasordeki ayarlar.json dosyasina otomatik kaydedilir.
"""

import colorsys
import json
import math
import os
import random
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser

import keyboard

from apex_hid import ApexKlavye
from gg import GG

SURUM = "v0.5"
KLASOR = os.path.dirname(os.path.abspath(__file__))
AYAR_DOSYASI = os.path.join(KLASOR, "ayarlar.json")

BOLGE_SAYISI = 8
TOPLAM_GENISLIK = 18.5  # klavyenin tus genisligi cinsinden toplam genisligi
SOL_BOSLUK = 0.0
MIN_KALINLIK = 0.8      # bunun altinda titreme yapiyor

VARSAYILAN = {
    "hiz": 8.0,                 # dalganin yayilma hizi (bolge/saniye)
    "kalinlik": 1.6,            # dalga halkasinin kalinligi (bolge), en az 0.8
    "parlaklik": 100,           # dalga parlakligi, yuzde 5-100
    "mod": "gokkusagi",         # "gokkusagi" ya da "sabit"
    "renk": "#00d4ff",          # sabit mod rengi
    "efekt": "dalga",           # EFEKTLER listesinden biri
    "bekleme_acik": False,      # bekleme isigi acik mi
    "bekleme_mod": "sabit",     # BEKLEME_MODLARI listesinden biri
    "nefes_renk": "sabit",      # nefes modunun rengi: "sabit", "dongu", "akis"
    "bekleme_renk": "#3b1fa3",  # bekleme isigi rengi
    "bekleme_parlaklik": 35,    # bekleme isigi parlakligi, yuzde 1-100
    "bekleme_hiz": 1.0,         # bekleme animasyon hizi, 0.2x - 3x
    "gg_geri": True,            # calisirken GG isiklarini duraklat, durunca geri getir
    "omur": 0.55,               # dalganin sonme suresi (saniye)  [sadece dosyadan]
    "fps": 25,                  # kare hizi                       [sadece dosyadan]
    "max_dalga": 8,             # ayni anda en fazla dalga        [sadece dosyadan]
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------- AYARLAR ----------------------------
def ayar_temizle(ayar):
    """Dosyadan gelen bozuk / eski degerleri duzeltir."""
    for k, alt, ust in (
        ("hiz", 2.0, 20.0),
        ("kalinlik", MIN_KALINLIK, 4.0),
        ("parlaklik", 5, 100),
        ("bekleme_parlaklik", 1, 100),
        ("bekleme_hiz", 0.2, 3.0),
    ):
        try:
            v = float(ayar[k])
        except Exception:
            v = VARSAYILAN[k]
        v = max(alt, min(ust, v))
        ayar[k] = int(round(v)) if k.endswith("parlaklik") else round(v, 2)
    for k in ("renk", "bekleme_renk"):
        if not (isinstance(ayar[k], str) and HEX.match(ayar[k])):
            ayar[k] = VARSAYILAN[k]
    if ayar["mod"] not in ("gokkusagi", "sabit"):
        ayar["mod"] = VARSAYILAN["mod"]
    if ayar["bekleme_mod"] == "gokkusagi":  # eski surumden kalan ad
        ayar["bekleme_mod"] = "dongu"
    if ayar["nefes_renk"] not in ("sabit", "dongu", "akis"):
        ayar["nefes_renk"] = VARSAYILAN["nefes_renk"]
    if ayar["bekleme_mod"] not in [m[0] for m in BEKLEME_MODLARI]:
        ayar["bekleme_mod"] = VARSAYILAN["bekleme_mod"]
    if ayar["efekt"] not in EFEKT_ADLARI:
        ayar["efekt"] = VARSAYILAN["efekt"]
    ayar["bekleme_acik"] = bool(ayar["bekleme_acik"])
    ayar["gg_geri"] = bool(ayar["gg_geri"])
    return ayar


def ayar_yukle():
    ayar = dict(VARSAYILAN)
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            kayitli = json.load(f)
        for k in VARSAYILAN:
            if k in kayitli:
                ayar[k] = kayitli[k]
    except Exception:
        pass
    return ayar_temizle(ayar)


def ayar_kaydet(ayar):
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ayar, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in (r, g, b))


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = hex_rgb(c1), hex_rgb(c2)
    return rgb_hex(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


# ------------------------- TUS KONUMLARI -------------------------
# Tusun fiziksel konumu (scan code'a gore; Turkce/Ingilizce Q duzeninde ayni calisir)
KONUM = {}
KONUM[1] = 0.5  # Esc
for _i, _sc in enumerate(range(59, 69)):  # F1-F10
    KONUM[_sc] = 2.5 + _i * 1.0 + (_i // 4) * 0.5
KONUM[87] = 12.5  # F11
KONUM[88] = 13.5  # F12
KONUM[41] = 0.5  # `
for _sc in range(2, 14):  # 1 2 3 ... - =
    KONUM[_sc] = 1.5 + (_sc - 2)
KONUM[14] = 14.0  # Backspace
KONUM[15] = 0.75  # Tab
for _sc in range(16, 28):  # Q W E ... [ ]
    KONUM[_sc] = 2.0 + (_sc - 16)
KONUM[28] = 14.0  # Enter
KONUM[58] = 0.9  # Caps
for _sc in range(30, 42):  # A S D ... ; '
    KONUM[_sc] = 2.25 + (_sc - 30)
KONUM[43] = 14.0
KONUM[42] = 1.1  # Sol Shift
KONUM[86] = 2.0  # < > tusu
for _sc in range(44, 54):  # Z X C ... . /
    KONUM[_sc] = 2.75 + (_sc - 44)
KONUM[54] = 13.0  # Sag Shift
KONUM[29] = 0.7  # Ctrl
KONUM[56] = 3.5  # Alt
KONUM[57] = 7.0  # Space
KONUM[75] = 15.5  # Sol ok
KONUM[80] = 16.5  # Asagi ok
KONUM[77] = 17.5  # Sag ok
KONUM[72] = 16.5  # Yukari ok


def bolge_bul(scan_code):
    x = KONUM.get(scan_code)
    if x is None:
        return None
    oran = (x - SOL_BOSLUK) / TOPLAM_GENISLIK
    return min(max(oran * BOLGE_SAYISI, 0), BOLGE_SAYISI - 1e-6)


# (anahtar, ad, renk secilebilir mi)
BEKLEME_MODLARI = [
    ("sabit", "Sabit", True),
    ("dongu", "Renk döngüsü", False),
    ("akis", "Akan gökkuşağı", False),
    ("nefes", "Nefes", True),
]


class _Faz:
    """Hiz degisince animasyon ziplamasin diye fazi biriktirir."""

    def __init__(self):
        self.t = None
        self.faz = 0.0
        self.hiz = 1.0

    def al(self, simdi, hiz):
        if self.t is None or simdi < self.t:
            self.t = simdi
        if hiz != self.hiz:  # yeni hiza gecerken mevcut fazdan devam et
            self.faz += (simdi - self.t) * self.hiz
            self.t, self.hiz = simdi, hiz
        return self.faz + (simdi - self.t) * self.hiz


_faz = _Faz()


def bekleme_renkleri(ayar, simdi):
    """Bekleme isigi: her bolge icin (R,G,B) float. Kapaliysa siyah."""
    n = BOLGE_SAYISI
    if not ayar.get("bekleme_acik"):
        return [(0.0, 0.0, 0.0)] * n
    k = max(0.0, min(1.0, float(ayar["bekleme_parlaklik"]) / 100.0))
    mod = ayar.get("bekleme_mod")
    t = _faz.al(simdi, float(ayar.get("bekleme_hiz", 1.0)))  # hizla olceklenmis zaman
    # renk kaynagi: nefes modu kendi secimini kullanir
    kaynak = ayar.get("nefes_renk", "sabit") if mod == "nefes" else mod
    if mod == "nefes":
        # 4 saniyede bir yavasca dolup bosalan isik
        k *= 0.12 + 0.88 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 4.0))
    if kaynak == "dongu":
        # butun klavye birlikte, yavasca renk degistirir (~20 sn'de bir tur)
        r, g, b = colorsys.hsv_to_rgb((t * 0.05) % 1.0, 1.0, 1.0)
        return [(r * 255 * k, g * 255 * k, b * 255 * k)] * n
    if kaynak == "akis":
        # klavye boyunca akan gokkusagi
        sonuc = []
        for z in range(n):
            r, g, b = colorsys.hsv_to_rgb((t * 0.08 + z / n) % 1.0, 1.0, 1.0)
            sonuc.append((r * 255 * k, g * 255 * k, b * 255 * k))
        return sonuc
    r, g, b = hex_rgb(ayar["bekleme_renk"])
    return [(r * k, g * k, b * k)] * n


# ------------------------------ EFEKTLER ------------------------------
# (anahtar, ad, aciklama)
EFEKTLER = [
    ("dalga", "Dalga", "Basılan yerden iki yana yayılan halka"),
    ("yanki", "Yankı", "Halka üç kez, giderek sönerek tekrarlanır"),
    ("yildiz", "Yıldız", "Işık klavyenin öbür ucuna kuyruğuyla kayar"),
    ("nabiz", "Nabız", "Bütün klavye bir an parlayıp söner"),
    ("kivilcim", "Kıvılcım", "Basılan yerin çevresinde rastgele çakan kıvılcımlar"),
    ("isi", "Isı", "Hızlı yazdıkça ısınır: maviden kırmızıya, sonra beyaza (kendi renkleri)"),
    ("simsek", "Şimşek", "Bütün klavye şimşek gibi iki üç kez çakar"),
    ("ates", "Ateş", "Basılan yerde titreyen alevler yanar (kendi renkleri)"),
    ("carpisma", "Çarpışma", "İki ışık iki kenardan gelir, basılan yerde çarpışıp patlar"),
    ("patlama", "Patlama", "Gökkuşağı renklerinde yayılan halka"),
    ("sarkac", "Sarkaç", "Işık iki kenar arasında sekerek gidip gelir, yavaşça söner"),
    ("ice", "İçe dalga", "Halka kenarlardan basılan yere doğru daralır ve orada parlar"),
    ("konfeti", "Konfeti", "Klavyenin rastgele yerlerinde rengârenk ışıklar çakar"),
    ("yagmur", "Dijital yağmur", "Yeşil kod damlaları klavyede titreşerek söner (kendi rengi)"),
    ("seviye", "Seviye", "Yazdıkça soldan sağa dolan hız göstergesi: yeşil, sarı, kırmızı"),
]
EFEKT_ADLARI = [e[0] for e in EFEKTLER]

ISI_RENKLERI = [  # soguktan sicaga
    (0.00, (0, 0, 0)), (0.15, (20, 30, 160)), (0.35, (130, 20, 200)),
    (0.55, (255, 30, 40)), (0.75, (255, 140, 0)), (0.90, (255, 230, 60)),
    (1.00, (255, 255, 255)),
]


SEVIYE_RENKLERI = [
    (0.00, (0, 255, 60)), (0.50, (255, 220, 0)), (1.00, (255, 20, 20)),
]

ATES_RENKLERI = [
    (0.00, (0, 0, 0)), (0.25, (120, 0, 0)), (0.50, (255, 40, 0)),
    (0.75, (255, 140, 0)), (1.00, (255, 230, 90)),
]


def _isi_rengi(t, palet=ISI_RENKLERI):
    t = max(0.0, min(1.0, t))
    for (t1, c1), (t2, c2) in zip(palet, palet[1:]):
        if t <= t2:
            f = (t - t1) / (t2 - t1)
            return tuple(c1[i] + (c2[i] - c1[i]) * f for i in range(3))
    return palet[-1][1]


def _halka(mesafe, yaricap, kalinlik):
    return max(0.0, 1.0 - abs(mesafe - yaricap) / kalinlik)


def omur_sure(ayar):
    """Bir basisin ekranda kalma suresi (saniye); bundan eskiler silinir."""
    e = ayar.get("efekt", "dalga")
    omur = max(0.05, float(ayar["omur"]))
    hiz = max(0.5, float(ayar["hiz"]))
    if e == "yanki":
        return 0.7 + omur * 2.5
    if e == "yildiz":
        return (BOLGE_SAYISI + 2 * float(ayar["kalinlik"])) / hiz + omur
    if e == "kivilcim":
        return 0.7
    if e == "isi":
        return 4.5
    if e == "simsek":
        return 0.6
    if e == "ates":
        return 1.6
    if e == "carpisma":
        return BOLGE_SAYISI / hiz + omur * 2.5
    if e == "sarkac":
        return omur * 9
    if e == "ice":
        return (BOLGE_SAYISI + float(ayar["kalinlik"])) / hiz + omur * 2
    if e == "konfeti":
        return 0.8
    if e == "yagmur":
        return 1.4
    if e == "seviye":
        return 5.0
    return omur * 2.5


def kapasite(ayar):
    """Ayni anda hesaba katilan en fazla basis."""
    e = ayar.get("efekt", "dalga")
    if e in ("isi", "seviye"):
        return 60
    if e in ("kivilcim", "ates", "konfeti", "yagmur"):
        return 16
    return max(1, int(ayar["max_dalga"]))


def kare_hesapla(aktif, simdi, ayar):
    """Verilen basislar icin 8 bolgenin (R,G,B) degerlerini hesaplar."""
    n = BOLGE_SAYISI
    efekt = ayar.get("efekt", "dalga")
    hiz = float(ayar["hiz"])
    kalinlik = max(MIN_KALINLIK, float(ayar["kalinlik"]))
    omur = max(0.05, float(ayar["omur"]))
    parlaklik = max(0.0, min(1.0, float(ayar["parlaklik"]) / 100.0))
    toplam = [list(c) for c in bekleme_renkleri(ayar, simdi)]

    def ekle(z, renk, v):
        v *= parlaklik
        toplam[z][0] += renk[0] * v
        toplam[z][1] += renk[1] * v
        toplam[z][2] += renk[2] * v

    if efekt == "isi":
        enerji = [0.0] * n
        for merkez, basla, _ in aktif:
            sonum = math.exp(-(simdi - basla) / 1.4)
            for z in range(n):
                m = (z + 0.5) - merkez
                enerji[z] += sonum * math.exp(-(m * m) / (2 * (0.6 * kalinlik) ** 2))
        for z in range(n):
            ekle(z, _isi_rengi(enerji[z] / 9.0), 1.0)
        aktif = ()

    if efekt == "seviye":
        seviye = 0.0
        for merkez, basla, _ in aktif:
            yas = simdi - basla
            if yas >= 0:
                seviye += 0.7 * math.exp(-yas / 1.3)
        for z in range(n):
            dolu = max(0.0, min(1.0, seviye - z))
            if dolu > 0:
                ekle(z, _isi_rengi(z / (n - 1), SEVIYE_RENKLERI), dolu)
        aktif = ()

    if efekt == "ates":
        isi = [0.0] * n
        for merkez, basla, _ in aktif:
            yas = simdi - basla
            if yas < 0:
                continue
            atak = min(1.0, yas / 0.05)
            sonum = math.exp(-yas / 0.55) * atak
            tohum = (basla * 1000) % 97
            for z in range(n):
                m = (z + 0.5) - merkez
                yayil = math.exp(-(m * m) / (2 * (0.5 * kalinlik + yas * 0.8) ** 2))
                titre = 0.6 + 0.4 * (0.5 + 0.25 * (math.sin(simdi * 23 + z * 7.1 + tohum)
                                                   + math.sin(simdi * 37 + z * 3.3)))
                isi[z] += sonum * yayil * titre
        for z in range(n):
            ekle(z, _isi_rengi(min(1.0, isi[z]), ATES_RENKLERI), 1.0)
        aktif = ()

    for merkez, basla, renk in aktif:
        yas = simdi - basla
        if yas < 0:
            continue
        if efekt == "yanki":
            for k, guc in enumerate((1.0, 0.55, 0.3)):
                y = yas - k * 0.3
                if y < 0:
                    continue
                s = math.exp(-y / omur) * guc
                for z in range(n):
                    ekle(z, renk, _halka(abs((z + 0.5) - merkez), y * hiz, kalinlik) * s)
        elif efekt == "yildiz":
            yon = 1.0 if merkez < n / 2 else -1.0  # uzak kenara dogru kayar
            bas = merkez + yon * yas * hiz
            kuyruk = kalinlik * 2.2
            sonum = math.exp(-yas / (omur * 3))
            for z in range(n):
                d = ((z + 0.5) - bas) * yon  # >0: basin onu, <0: kuyruk
                v = max(0.0, 1.0 - d / 0.6) if d > 0 else max(0.0, 1.0 + d / kuyruk)
                ekle(z, renk, v * sonum)
        elif efekt == "nabiz":
            atak = min(1.0, yas / 0.04)
            sonum = math.exp(-yas / (omur * 0.8)) * atak
            for z in range(n):
                m = abs((z + 0.5) - merkez)
                ekle(z, renk, sonum * (0.55 + 0.45 * max(0.0, 1.0 - m / 4.0)))
        elif efekt == "kivilcim":
            rnd = random.Random(int(basla * 1e6))
            for _ in range(6):
                z = int(round(rnd.gauss(merkez - 0.5, kalinlik * 1.2)))
                if not 0 <= z < n:
                    continue
                y = yas - rnd.random() * 0.3
                if 0 <= y < 0.3:
                    ekle(z, renk, 1.0 - y / 0.3)
        elif efekt == "simsek":
            rnd = random.Random(int(basla * 1e6))
            beyaz = tuple(c + (255 - c) * 0.45 for c in renk)
            cakmalar = ((0.0, 1.0), (0.07 + rnd.random() * 0.04, 0.55),
                        (0.17 + rnd.random() * 0.08, 0.85))
            v = 0.0
            for t, guc in cakmalar:
                d = yas - t
                if 0 <= d < 0.06:
                    v = max(v, guc * (1.0 - d / 0.12))
            v = max(v, 0.25 * math.exp(-yas / 0.15))  # kisa art isik
            for z in range(n):
                ekle(z, beyaz, v)
        elif efekt == "carpisma":
            # iki isik da basilan yere AYNI ANDA varsin (yakindaki daha yavas gelir)
            bulusma = max(merkez, n - merkez) / hiz
            f = min(1.0, yas / bulusma)
            sol = merkez * f                # soldan gelen
            sag = n - (n - merkez) * f      # sagdan gelen
            for z in range(n):
                x = z + 0.5
                v = 0.0
                if f < 1.0:
                    v = max(0.0, 1.0 - abs(x - sol) / 0.8, 1.0 - abs(x - sag) / 0.8)
                d = yas - bulusma
                if d >= 0:
                    s = _halka(abs(x - merkez), d * hiz * 1.3, kalinlik)
                    if d < 0.08 and abs(x - merkez) < 1.0:
                        s = 1.0
                    v = max(v, s * math.exp(-d / omur))
                ekle(z, renk, max(0.0, v))
        elif efekt == "patlama":
            h0 = colorsys.rgb_to_hsv(*(c / 255.0 for c in renk))[0]
            sonum = math.exp(-yas / omur)
            for z in range(n):
                m = abs((z + 0.5) - merkez)
                s = _halka(m, yas * hiz, kalinlik)
                if yas < 0.08 and m < 0.8:
                    s = 1.0
                r, g, b = colorsys.hsv_to_rgb((h0 + m * 0.11) % 1.0, 1.0, 1.0)
                ekle(z, (r * 255, g * 255, b * 255), s * sonum)
        elif efekt == "sarkac":
            yon = 1.0 if merkez < n / 2 else -1.0
            q = (merkez + yon * yas * hiz) % (2 * n)
            if q > n:
                q = 2 * n - q  # kenara carpinca geri sek
            genis = max(0.5, kalinlik * 0.6)
            sonum = math.exp(-yas / (omur * 3))
            for z in range(n):
                ekle(z, renk, max(0.0, 1.0 - abs((z + 0.5) - q) / genis) * sonum)
        elif efekt == "ice":
            r0 = max(merkez, n - merkez) + kalinlik
            varis = r0 / hiz
            for z in range(n):
                m = abs((z + 0.5) - merkez)
                if yas < varis:
                    v = _halka(m, r0 - yas * hiz, kalinlik) * (0.35 + 0.65 * yas / varis)
                else:
                    d = yas - varis
                    v = math.exp(-d / (omur * 0.7)) * max(0.0, 1.0 - m / (1.0 + kalinlik))
                ekle(z, renk, v)
        elif efekt == "konfeti":
            rnd = random.Random(int(basla * 1e6))
            for _ in range(4):
                z = rnd.randrange(n)
                r, g, b = colorsys.hsv_to_rgb(rnd.random(), 1.0, 1.0)
                y = yas - rnd.random() * 0.15
                if y >= 0:
                    ekle(z, (r * 255, g * 255, b * 255), math.exp(-y / 0.18))
        elif efekt == "yagmur":
            rnd = random.Random(int(basla * 1e6))
            yesil = (0, 255, 70)
            for _ in range(5):
                z = rnd.randrange(n)
                y = yas - rnd.random() * 0.5
                if y >= 0:
                    titre = 0.65 + 0.35 * math.sin(simdi * 40 + z * 5.0 + rnd.random() * 6)
                    bas = 1.0 if y < 0.05 else 0.0  # damlanin basi beyazimsi parlasin
                    ekle(z, tuple(c + (255 - c) * 0.6 * bas for c in yesil),
                         math.exp(-y / 0.35) * titre)
        else:  # dalga
            sonum = math.exp(-yas / omur)
            for z in range(n):
                m = abs((z + 0.5) - merkez)
                s = _halka(m, yas * hiz, kalinlik)
                if yas < 0.08 and m < 0.8:  # basilan yer ilk anda parlasin
                    s = 1.0
                ekle(z, renk, s * sonum)

    return tuple(
        (min(255, int(c[0])), min(255, int(c[1])), min(255, int(c[2]))) for c in toplam
    )


# ------------------------------ MOTOR ------------------------------
class Motor:
    """Tus dinler, dalgalari hesaplar, klavyeye gonderir (arka planda)."""

    def __init__(self, ayar):
        self.ayar = ayar
        self.kb = ApexKlavye()
        self.gg = GG()
        self.kilit = threading.Lock()
        self.dalgalar = []
        self.hue = 0.0
        self.durdur_ev = threading.Event()
        self.thread = None
        self._hook = None
        self.calisiyor = False
        self.durum = "Durdu"
        self.durum_hata = False
        self.son_kare = None  # arayuz onizlemesi icin

    def _renk_sec(self):
        if self.ayar["mod"] == "sabit":
            return hex_rgb(self.ayar["renk"])
        self.hue = (self.hue + 0.06) % 1.0
        r, g, b = colorsys.hsv_to_rgb(self.hue, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    def _tus(self, olay):
        if olay.event_type != "down":
            return
        merkez = bolge_bul(olay.scan_code)
        if merkez is None:
            return
        with self.kilit:
            self.dalgalar.append((merkez, time.time(), self._renk_sec()))
            del self.dalgalar[: -kapasite(self.ayar)]

    def baslat(self):
        if self.calisiyor:
            return True
        if not self.kb.baglan():
            self.durum = "Klavye bulunamadı. OpenRGB kapalı mı?"
            self.durum_hata = True
            return False
        if self.ayar.get("gg_geri") and self.gg.devral():
            time.sleep(0.25)  # GG son yazimini bitirsin, sonra biz baslayalim
        with self.kilit:
            self.dalgalar.clear()
        self.durdur_ev.clear()
        self._hook = keyboard.hook(self._tus)
        self.thread = threading.Thread(target=self._dongu, daemon=True)
        self.thread.start()
        self.calisiyor = True
        self.durum = "Çalışıyor"
        self.durum_hata = False
        return True

    def durdur(self):
        if not self.calisiyor:
            return
        self.durdur_ev.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        try:
            keyboard.unhook(self._hook)
        except Exception:
            pass
        self._hook = None
        try:
            self.kb.renk_gonder([(0, 0, 0)] * BOLGE_SAYISI)
        except Exception:
            pass
        self.kb.kapat()
        self.gg.birak()  # GG'yi devralmadiysak da zararsiz; profil geri gelir
        self.son_kare = None
        self.calisiyor = False
        self.durum = "Durdu"
        self.durum_hata = False

    def _dongu(self):
        son_gonderilen = None
        while not self.durdur_ev.is_set():
            t0 = time.time()
            aralik = 1.0 / max(5, int(self.ayar["fps"]))
            sure = omur_sure(self.ayar)
            with self.kilit:
                self.dalgalar[:] = [d for d in self.dalgalar if t0 - d[1] < sure]
                aktif = list(self.dalgalar)

            kare = kare_hesapla(aktif, t0, self.ayar)

            if kare != son_gonderilen:  # sadece isiklar degistiyse gonder
                if self.kb.renk_gonder(list(kare)):
                    son_gonderilen = kare
                    self.son_kare = kare
                    self.durum = "Çalışıyor"
                    self.durum_hata = False
                else:
                    self.durum = "Bağlantı koptu, yeniden deneniyor..."
                    self.durum_hata = True
                    son_gonderilen = None
                    self.durdur_ev.wait(0.5)

            gecen = time.time() - t0
            if gecen < aralik:
                self.durdur_ev.wait(aralik - gecen)


# ----------------------------- TASARIM -----------------------------
# Sade, notr koyu tema. Renk sadece klavye onizlemesinden gelir.
BG = "#0f0f11"
YUZEY = "#17171a"
CIZGI = "#26262b"
TUS = "#1d1d21"
TUS_KENAR = "#2a2a30"
FG = "#ededf0"
SOLUK = "#8a8a93"
PASIF = "#4a4a52"
YESIL = "#4ade80"
HATA = "#f87171"

OLCEK = 1.0  # ekran olcegi (main icinde ayarlanir)
FONT = "Segoe UI"


def px(v):
    return int(round(v * OLCEK))


def yuvarlak(c, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    nk = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
          x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(nk, smooth=True, **kw)


def font(boyut, kalin=False):
    return (FONT, boyut, "bold") if kalin else (FONT, boyut)


# ---------------------------- BILESENLER ----------------------------
class Kaydirici(tk.Canvas):
    """Ince cizgili, yuvarlak tutamakli kaydirici. Fare tekerlegiyle de oynar."""

    def __init__(self, ebeveyn, alt, ust, adim, deger, geri, bg, genislik=220):
        super().__init__(ebeveyn, width=px(genislik), height=px(22), bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.alt, self.ust, self.adim = alt, ust, adim
        self.deger, self.geri, self.aktif = float(deger), geri, True
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Button-1>", self._fare)
        self.bind("<B1-Motion>", self._fare)
        self.bind("<MouseWheel>", self._teker)

    def _x_aralik(self):
        p = px(8)
        return p, max(p + 1, self.winfo_width() - p)

    def ciz(self):
        self.delete("all")
        x1, x2 = self._x_aralik()
        y = self.winfo_height() / 2
        t = (self.deger - self.alt) / (self.ust - self.alt)
        xk = x1 + (x2 - x1) * t
        dolu = FG if self.aktif else PASIF
        self.create_line(x1, y, x2, y, fill=CIZGI, width=px(4), capstyle="round")
        self.create_line(x1, y, xk, y, fill=dolu, width=px(4), capstyle="round")
        r = px(7)
        self.create_oval(xk - r, y - r, xk + r, y + r, fill=dolu, outline="")

    def _ayarla(self, v):
        v = round(round((v - self.alt) / self.adim) * self.adim + self.alt, 4)
        v = max(self.alt, min(self.ust, v))
        if v != self.deger:
            self.deger = v
            self.ciz()
            self.geri(v)

    def _fare(self, e):
        if not self.aktif:
            return
        x1, x2 = self._x_aralik()
        t = max(0.0, min(1.0, (e.x - x1) / (x2 - x1)))
        self._ayarla(self.alt + t * (self.ust - self.alt))

    def _teker(self, e):
        if self.aktif:
            self._ayarla(self.deger + (self.adim if e.delta > 0 else -self.adim))


class Anahtar(tk.Canvas):
    def __init__(self, ebeveyn, deger, geri, bg):
        super().__init__(ebeveyn, width=px(38), height=px(22), bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.deger, self.geri = bool(deger), geri
        self.bind("<Button-1>", self._tik)
        self.ciz()

    def ciz(self):
        self.delete("all")
        w, h = px(38), px(22)
        yuvarlak(self, 1, 1, w - 1, h - 1, h / 2, fill=FG if self.deger else CIZGI, outline="")
        r = h / 2 - px(3)
        cx = w - h / 2 if self.deger else h / 2
        self.create_oval(cx - r, h / 2 - r, cx + r, h / 2 + r,
                         fill=BG if self.deger else SOLUK, outline="")

    def _tik(self, _):
        self.deger = not self.deger
        self.ciz()
        self.geri(self.deger)


class Segment(tk.Canvas):
    def __init__(self, ebeveyn, secenekler, deger, geri, bg, genislik=220):
        super().__init__(ebeveyn, width=px(genislik), height=px(30), bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.secenekler, self.deger, self.geri, self.aktif = secenekler, deger, geri, True
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Button-1>", self._tik)

    def ciz(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.config(cursor="hand2" if self.aktif else "arrow")
        yuvarlak(self, 0, 0, w, h, px(8), fill=CIZGI if self.aktif else YUZEY, outline="")
        n = len(self.secenekler)
        for i, (ad, d) in enumerate(self.secenekler):
            x1, x2 = w * i / n, w * (i + 1) / n
            secili = d == self.deger
            if secili:
                yuvarlak(self, x1 + px(3), px(3), x2 - px(3), h - px(3), px(6),
                         fill=YUZEY, outline="")
            if not self.aktif:
                yazi = PASIF
            else:
                yazi = FG if secili else SOLUK
            self.create_text((x1 + x2) / 2, h / 2, text=ad, font=font(9, secili), fill=yazi)

    def _tik(self, e):
        if not self.aktif:
            return
        i = min(len(self.secenekler) - 1, int(e.x / self.winfo_width() * len(self.secenekler)))
        d = self.secenekler[i][1]
        if d != self.deger:
            self.deger = d
            self.ciz()
            self.geri(d)


class Secim(tk.Canvas):
    """Izgara halinde secenek kutucuklari (efekt secici)."""

    def __init__(self, ebeveyn, secenekler, deger, geri, bg, sutun=3):
        self.sutun = sutun
        self.satir = (len(secenekler) + sutun - 1) // sutun
        self.sh, self.ara = px(34), px(6)
        super().__init__(ebeveyn, height=self.satir * self.sh + (self.satir - 1) * self.ara,
                         bg=bg, highlightthickness=0, cursor="hand2")
        self.secenekler, self.deger, self.geri, self.ust = secenekler, deger, geri, None
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Button-1>", self._tik)
        self.bind("<Motion>", self._hareket)
        self.bind("<Leave>", lambda e: self._hareket(None))

    def _kutu(self, i):
        w = self.winfo_width()
        kw = (w - (self.sutun - 1) * self.ara) / self.sutun
        r, c = divmod(i, self.sutun)
        x1, y1 = c * (kw + self.ara), r * (self.sh + self.ara)
        return x1, y1, x1 + kw, y1 + self.sh

    def _indeks(self, e):
        for i in range(len(self.secenekler)):
            x1, y1, x2, y2 = self._kutu(i)
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                return i
        return None

    def ciz(self):
        self.delete("all")
        for i, (ad, d) in enumerate(self.secenekler):
            x1, y1, x2, y2 = self._kutu(i)
            secili = d == self.deger
            if secili:
                yuvarlak(self, x1, y1, x2, y2, px(8), fill=FG, outline="")
            else:
                yuvarlak(self, x1, y1, x2, y2, px(8),
                         fill=CIZGI if self.ust == i else YUZEY, outline=CIZGI)
            self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=ad, font=font(9, secili),
                             fill=BG if secili else FG)

    def _hareket(self, e):
        i = None if e is None else self._indeks(e)
        if i != self.ust:
            self.ust = i
            self.ciz()

    def _tik(self, e):
        i = self._indeks(e)
        if i is not None and self.secenekler[i][1] != self.deger:
            self.deger = self.secenekler[i][1]
            self.ciz()
            self.geri(self.deger)


class Ornek(tk.Canvas):
    """Renk kutucugu. Tiklayinca renk secici acar."""

    def __init__(self, ebeveyn, renk, geri, bg):
        super().__init__(ebeveyn, width=px(30), height=px(30), bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.renk, self.gokkusagi, self.aktif, self.bg = renk, False, True, bg
        self.bind("<Button-1>", lambda e: self.aktif and not self.gokkusagi and geri())
        self.ciz()

    def ciz(self):
        self.delete("all")
        s = px(30)
        if self.gokkusagi:
            for i in range(s):
                r, g, b = colorsys.hsv_to_rgb(i / s, 0.75, 0.95 if self.aktif else 0.35)
                self.create_line(i, 0, i, s, fill=rgb_hex(r * 255, g * 255, b * 255))
            yuvarlak(self, -px(1), -px(1), s + px(1), s + px(1), px(9),
                     outline=self.bg, width=px(4), fill="")
        else:
            renk = self.renk if self.aktif else lerp(self.renk, YUZEY, 0.75)
            yuvarlak(self, 1, 1, s - 1, s - 1, px(8), fill=renk, outline=TUS_KENAR)
        self.config(cursor="hand2" if self.aktif and not self.gokkusagi else "arrow")


class Dugme(tk.Canvas):
    def __init__(self, ebeveyn, metin, geri, bg, yukseklik=46):
        super().__init__(ebeveyn, height=px(yukseklik), bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.metin, self.geri, self.dolu, self.ust = metin, geri, True, False
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Enter>", lambda e: self._uzeri(True))
        self.bind("<Leave>", lambda e: self._uzeri(False))
        self.bind("<ButtonRelease-1>", lambda e: self.geri())

    def _uzeri(self, v):
        self.ust = v
        self.ciz()

    def ayarla(self, metin, dolu):
        self.metin, self.dolu = metin, dolu
        self.ciz()

    def ciz(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if self.dolu:
            yuvarlak(self, 1, 1, w - 1, h - 1, px(10),
                     fill="#ffffff" if self.ust else FG, outline="")
            yazi = BG
        else:
            yuvarlak(self, 1, 1, w - 1, h - 1, px(10),
                     fill=CIZGI if self.ust else YUZEY, outline=TUS_KENAR, width=px(1))
            yazi = FG
        self.create_text(w / 2, h / 2, text=self.metin, font=font(11, True), fill=yazi)


# ------------------------- KLAVYE ONIZLEMESI -------------------------
# TKL duzeni, tus genisligi cinsinden. Negatif sayi = bosluk.
DUZEN = [
    [1, -1, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.25, 1, 1, 1],
    [1] * 13 + [2, -0.25, 1, 1, 1],
    [1.5] + [1] * 12 + [1.5, -0.25, 1, 1, 1],
    [1.75] + [1] * 11 + [2.25],
    [2.25] + [1] * 10 + [2.75, -1.25, 1],
    [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25, -0.25, 1, 1, 1],
]
DUZEN_GENISLIK = 18.25


class Onizleme(tk.Canvas):
    """Klavyedeki 8 bolgenin canli kopyasi. Durmusken tiklayinca deneme dalgasi."""

    def __init__(self, ebeveyn, bg, tik_geri):
        self.u = px(23)  # bir tus birimi
        self.pad = px(14)
        w = int(DUZEN_GENISLIK * self.u + 2 * self.pad)
        h = int(6.5 * self.u + 2 * self.pad)
        super().__init__(ebeveyn, width=w, height=h, bg=bg, highlightthickness=0,
                         cursor="hand2")
        yuvarlak(self, 0, 0, w, h, px(14), fill=YUZEY, outline=CIZGI)
        self.tuslar = []  # (oge, bolge)
        bosluk = px(2)
        for satir, tuslar in enumerate(DUZEN):
            x = 0.0
            y = self.pad + satir * self.u + (0.5 * self.u if satir > 0 else 0)
            for g in tuslar:
                if g < 0:
                    x += -g
                    continue
                x1 = self.pad + x * self.u + bosluk
                x2 = self.pad + (x + g) * self.u - bosluk
                orta = (x + g / 2) / DUZEN_GENISLIK
                bolge = min(BOLGE_SAYISI - 1, int(orta * BOLGE_SAYISI))
                oge = yuvarlak(self, x1, y + bosluk, x2, y + self.u - bosluk, px(4),
                               fill=TUS, outline="")
                self.tuslar.append((oge, bolge))
                x += g
        self._son = None
        self.bind("<Button-1>", lambda e: tik_geri(
            (e.x - self.pad) / (DUZEN_GENISLIK * self.u) * BOLGE_SAYISI))

    def goster(self, kare):
        if kare == self._son:
            return
        self._son = kare
        renkler = []
        for r, g, b in kare:
            k = max(r, g, b) / 255.0
            if k <= 0:
                renkler.append((TUS, TUS_KENAR))
            else:
                # ekranda isik hissi: karanlik tus rengiyle karistir
                renk = lerp(TUS, rgb_hex(r / k, g / k, b / k), min(1.0, 0.15 + k))
                renkler.append((renk, lerp(TUS_KENAR, renk, 0.6)))
        for oge, b in self.tuslar:
            self.itemconfig(oge, fill=renkler[b][0])


# ------------------------------ UYGULAMA ------------------------------
class Uygulama:
    def __init__(self, root):
        self.root = root
        self.ayar = ayar_yukle()
        self.motor = Motor(self.ayar)
        self._kayit_zamanlayici = None
        self.deneme = []  # onizlemedeki deneme dalgalari

        root.title("Dalga")
        root.configure(bg=BG)
        root.resizable(False, False)

        govde = tk.Frame(root, bg=BG)
        govde.pack(fill="both", expand=True, padx=px(24), pady=px(22))

        # --- baslik ---
        ust = tk.Frame(govde, bg=BG)
        ust.pack(fill="x")
        tk.Label(ust, text="Dalga", font=font(18, True), fg=FG, bg=BG).pack(side="left")
        tk.Label(ust, text=SURUM, font=font(9), fg=PASIF, bg=BG).pack(
            side="left", padx=(px(8), 0), pady=(px(8), 0))
        self.durum = tk.Label(ust, text="Durdu", font=font(9), fg=SOLUK, bg=BG)
        self.durum.pack(side="right")
        self.nokta = tk.Canvas(ust, width=px(8), height=px(8), bg=BG, highlightthickness=0)
        self.nokta.pack(side="right", padx=(0, px(7)))
        tk.Label(govde, text="Apex 3 TKL  ·  tuşa bastıkça yayılan ışık", font=font(9),
                 fg=SOLUK, bg=BG, anchor="w").pack(fill="x", pady=(px(2), px(16)))

        # --- iki sutun: solda onizleme + efekt, sagda bekleme + GG ---
        sutunlar = tk.Frame(govde, bg=BG)
        sutunlar.pack(fill="both", expand=True)
        sol = tk.Frame(sutunlar, bg=BG)
        sol.grid(row=0, column=0, sticky="n")
        sag_sutun = tk.Frame(sutunlar, bg=BG, width=px(420))
        sag_sutun.grid(row=0, column=1, sticky="nsew", padx=(px(32), 0))

        # --- onizleme ---
        self.onizleme = Onizleme(sol, BG, self._deneme_dalga)
        self.onizleme.pack()
        self.ipucu = tk.Label(sol, text="", font=font(8), fg=PASIF, bg=BG)
        self.ipucu.pack(pady=(px(6), 0))

        # --- ayarlar (sol) ---
        self.liste = tk.Frame(sol, bg=BG)
        self.liste.pack(fill="x")

        self._bolum("Efekt")
        self.secim = Secim(self.liste, [(e[1], e[0]) for e in EFEKTLER],
                           self.ayar["efekt"], self._efekt_degisti, BG, sutun=5)
        self.secim.pack(fill="x", pady=(px(10), 0))
        self.efekt_aciklama = tk.Label(self.liste, text="", font=font(9), fg=SOLUK, bg=BG,
                                       anchor="w")
        self.efekt_aciklama.pack(fill="x", pady=(px(6), px(2)))
        self._kaydirici("Hız", "hiz", 2, 20, 0.5, lambda v: f"{v:.1f}")
        self._kaydirici("Kalınlık", "kalinlik", MIN_KALINLIK, 4.0, 0.1, lambda v: f"{v:.1f}")
        self._kaydirici("Parlaklık", "parlaklik", 5, 100, 1, lambda v: f"{int(v)}%", True)

        self._bolum("Renk")
        sag = self._satir("Mod")
        self.ornek = Ornek(sag, self.ayar["renk"], self._renk_sec, BG)
        self.ornek.pack(side="right")
        self.segment = Segment(sag, [("Gökkuşağı", "gokkusagi"), ("Sabit", "sabit")],
                               self.ayar["mod"], self._mod_degisti, BG, genislik=180)
        self.segment.pack(side="right", padx=(0, px(10)))

        # --- ayarlar (sag) ---
        self.ana = Dugme(sag_sutun, "Başlat", self._ac_kapat, BG)
        self.ana.pack(side="bottom", fill="x")
        self.liste = tk.Frame(sag_sutun, bg=BG)
        self.liste.pack(side="top", fill="x")
        tk.Frame(self.liste, bg=BG, width=px(420), height=1).pack()  # sutun genisligi

        self._bolum("Bekleme ışığı", ust=0)
        sag = self._satir("Açık")
        self.bek_anahtar = Anahtar(sag, self.ayar["bekleme_acik"], self._bek_ac, BG)
        self.bek_anahtar.pack(side="right")
        self.bek_secim = Secim(self.liste, [(m[1], m[0]) for m in BEKLEME_MODLARI],
                               self.ayar["bekleme_mod"], self._bek_mod_degisti, BG, sutun=4)
        self.bek_secim.pack(fill="x", pady=(px(10), 0))
        sag = self._satir("Nefes rengi")
        self.nefes_segment = Segment(
            sag, [("Seçili renk", "sabit"), ("Döngü", "dongu"), ("Gökkuşağı", "akis")],
            self.ayar["nefes_renk"], self._nefes_renk_degisti, BG, genislik=270)
        self.nefes_segment.pack(side="right")
        sag = self._satir("Renk")
        self.bek_ornek = Ornek(sag, self.ayar["bekleme_renk"], self._bek_renk_sec, BG)
        self.bek_ornek.pack(side="right")
        self.bek_hiz = self._kaydirici("Hız", "bekleme_hiz", 0.2, 3.0, 0.1,
                                       lambda v: f"{v:.1f}x")
        self.bek_slider = self._kaydirici("Parlaklık", "bekleme_parlaklik", 1, 100, 1,
                                          lambda v: f"{int(v)}%", True)

        self._bolum("SteelSeries GG")
        sag = self._satir("Çalışırken SteelSeries GG ışıklarını duraklat")
        Anahtar(sag, self.ayar["gg_geri"], self._gg_ac, BG).pack(side="right")


        self._gorunum_senkron()
        root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._durum_guncelle()
        self._kare()

    # --- yapi taslari ---
    def _bolum(self, baslik, ust=16):
        tk.Label(self.liste, text=baslik.upper(), font=font(8, True), fg=PASIF, bg=BG,
                 anchor="w").pack(fill="x", pady=(px(ust), px(4)))
        tk.Frame(self.liste, bg=CIZGI, height=1).pack(fill="x")

    def _satir(self, ad):
        satir = tk.Frame(self.liste, bg=BG)
        satir.pack(fill="x", pady=(px(8), 0))
        tk.Label(satir, text=ad, font=font(10), fg=FG, bg=BG).pack(side="left")
        return satir

    def _kaydirici(self, ad, anahtar, alt, ust, adim, bicim, tamsayi=False):
        satir = self._satir(ad)
        deger = tk.Label(satir, text=bicim(float(self.ayar[anahtar])), font=font(10),
                         fg=SOLUK, bg=BG, width=5, anchor="e")
        deger.pack(side="right")

        def degisti(v):
            v = int(round(v)) if tamsayi else round(float(v), 2)
            self.ayar[anahtar] = v
            deger.config(text=bicim(float(v)))
            self._kaydet_planla()

        k = Kaydirici(satir, alt, ust, adim, self.ayar[anahtar], degisti, BG)
        k.pack(side="right", padx=(0, px(8)))
        k.etiket = deger
        return k

    # --- gorunum / olaylar ---
    def _gorunum_senkron(self):
        self.ornek.gokkusagi = self.ayar["mod"] != "sabit"
        self.ornek.renk = self.ayar["renk"]
        self.ornek.ciz()
        acik = self.ayar["bekleme_acik"]
        renkli = next(m[2] for m in BEKLEME_MODLARI if m[0] == self.ayar["bekleme_mod"])
        nefes = self.ayar["bekleme_mod"] == "nefes"
        if nefes:
            renkli = self.ayar["nefes_renk"] == "sabit"
        self.nefes_segment.aktif = acik and nefes
        self.nefes_segment.ciz()
        self.bek_ornek.aktif = acik
        self.bek_ornek.gokkusagi = not renkli
        self.efekt_aciklama.config(
            text=next(e[2] for e in EFEKTLER if e[0] == self.ayar["efekt"]))
        self.bek_ornek.renk = self.ayar["bekleme_renk"]
        self.bek_ornek.ciz()
        self.bek_slider.aktif = acik
        self.bek_slider.ciz()
        self.bek_slider.etiket.config(fg=SOLUK if acik else PASIF)
        hareketli = acik and self.ayar["bekleme_mod"] != "sabit"
        self.bek_hiz.aktif = hareketli
        self.bek_hiz.ciz()
        self.bek_hiz.etiket.config(fg=SOLUK if hareketli else PASIF)

    def _kaydet_planla(self):
        if self._kayit_zamanlayici is not None:
            self.root.after_cancel(self._kayit_zamanlayici)
        self._kayit_zamanlayici = self.root.after(400, lambda: ayar_kaydet(self.ayar))

    def _mod_degisti(self, deger):
        self.ayar["mod"] = deger
        self._gorunum_senkron()
        self._kaydet_planla()

    def _renk_sec(self):
        sonuc = colorchooser.askcolor(color=self.ayar["renk"], title="Dalga rengi")
        if sonuc and sonuc[1]:
            self.ayar["renk"] = sonuc[1]
            self._gorunum_senkron()
            self._kaydet_planla()

    def _bek_ac(self, deger):
        self.ayar["bekleme_acik"] = bool(deger)
        self._gorunum_senkron()
        self._kaydet_planla()

    def _bek_renk_sec(self):
        sonuc = colorchooser.askcolor(color=self.ayar["bekleme_renk"],
                                      title="Bekleme ışığı rengi")
        if sonuc and sonuc[1]:
            self.ayar["bekleme_renk"] = sonuc[1]
            self._gorunum_senkron()
            self._kaydet_planla()

    def _efekt_degisti(self, deger):
        self.ayar["efekt"] = deger
        self.deneme.clear()
        self._gorunum_senkron()
        self._kaydet_planla()

    def _bek_mod_degisti(self, deger):
        self.ayar["bekleme_mod"] = deger
        self._gorunum_senkron()
        self._kaydet_planla()

    def _nefes_renk_degisti(self, deger):
        self.ayar["nefes_renk"] = deger
        self._gorunum_senkron()
        self._kaydet_planla()

    def _gg_ac(self, deger):
        self.ayar["gg_geri"] = bool(deger)
        self._kaydet_planla()

    def _deneme_dalga(self, merkez):
        if self.motor.calisiyor:
            return
        merkez = max(0.0, min(BOLGE_SAYISI - 1e-6, merkez))
        self.deneme.append((merkez, time.time(), self.motor._renk_sec()))
        del self.deneme[:-kapasite(self.ayar)]

    def _ac_kapat(self):
        self.ana.ayarla("Durduruluyor…" if self.motor.calisiyor else "Bağlanıyor…",
                        self.ana.dolu)
        self.root.update_idletasks()
        if self.motor.calisiyor:
            self.motor.durdur()
        else:
            self.motor.baslat()
        if self.motor.calisiyor:
            self.ana.ayarla("Durdur", False)
        else:
            self.ana.ayarla("Başlat", True)

    def _kare(self):
        if self.motor.calisiyor:
            kare = self.motor.son_kare or kare_hesapla([], time.time(), self.ayar)
            self.ipucu.config(text="Klavyende yazdıkça burada da görünür")
        else:
            simdi = time.time()
            sure = omur_sure(self.ayar)
            self.deneme[:] = [d for d in self.deneme if simdi - d[1] < sure]
            kare = kare_hesapla(self.deneme, simdi, self.ayar)
            self.ipucu.config(text="Denemek için önizlemeye tıkla")
        self.onizleme.goster(kare)
        self.root.after(33, self._kare)

    def _durum_guncelle(self):
        if self.motor.durum_hata:
            renk = HATA
        elif self.motor.calisiyor:
            renk = YESIL
        else:
            renk = PASIF
        self.nokta.delete("all")
        self.nokta.create_oval(0, 0, px(8), px(8), fill=renk, outline="")
        self.durum.config(text=self.motor.durum,
                          fg=HATA if self.motor.durum_hata
                          else FG if self.motor.calisiyor else SOLUK)
        self.root.after(300, self._durum_guncelle)

    def _kapat(self):
        try:
            self.motor.durdur()
        finally:
            ayar_kaydet(self.ayar)
            self.root.destroy()


def main():
    global OLCEK, FONT
    try:  # net (bulanik olmayan) yazi icin Windows DPI farkindaligi
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    OLCEK = root.winfo_fpixels("1i") / 96.0
    if "Segoe UI Variable Text" in tkfont.families():
        FONT = "Segoe UI Variable Text"
    Uygulama(root)
    root.mainloop()


if __name__ == "__main__":
    main()
