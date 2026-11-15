"""
arayuz_web.py - Dalga'nin modern arayuzu (pywebview).

Arayuz arayuz/ klasorundeki HTML/CSS/JS ile cizilir; Windows'un kendi
Edge WebView2 motorunda calisir. Efekt hesabi, klavye (HID) ve GG uyumu
dalga.py / apex_hid.py / gg.py icindeki kodun aynisidir.

Gerekenler:  pip install keyboard pywebview
Calistir:    py dalga.py
"""

import json
import os
import random
import threading
import time

import webview

import dalga
from dalga import (BOLGE_SAYISI, BEKLEME_MODLARI, EFEKTLER, SURUM, Motor, ayar_kaydet,
                   ayar_temizle, ayar_yukle, kapasite, kare_hesapla, omur_sure)

KLASOR = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(KLASOR, "arayuz", "index.html")
FPS = 30


class Api:
    """JavaScript'ten window.pywebview.api.<ad>() ile cagrilir.

    Not: pywebview acik (alt cizgisiz) ozellikleri JS'e tasimaya calisir,
    bu yuzden tum durum alt cizgili tutulur."""

    def __init__(self):
        self._ayar = ayar_yukle()
        self._motor = Motor(self._ayar)
        self._deneme = []
        self._kilit = threading.Lock()
        self._dur = threading.Event()
        self._pencere = None
        self._kayit_zamani = None
        self._son_durum = None
        self._sonraki_degisim = None  # otomatik efekt degisimi zamani (time.time)
        self._son_kalan = None

    # ---------------- JS'in cagirdiklari ----------------
    def baslangic(self):
        return {
            "surum": SURUM,
            "ayar": self._ayar,
            "efektler": [{"id": e, "ad": ad, "aciklama": ac} for e, ad, ac in EFEKTLER],
            "bekleme_modlari": [{"id": m, "ad": ad, "renkli": r}
                                for m, ad, r in BEKLEME_MODLARI],
            "bolge": BOLGE_SAYISI,
        }

    def ayar(self, degerler):
        if "oto_degis" in degerler or "oto_dakika" in degerler:
            self._sonraki_degisim = None  # sayaci yeniden kur
        with self._kilit:
            yeni = dict(self._ayar)
            for k, v in (degerler or {}).items():
                if k in dalga.VARSAYILAN:
                    yeni[k] = v
            ayar_temizle(yeni)
            if yeni.get("efekt") != self._ayar.get("efekt"):
                self._deneme.clear()
            self._ayar.update(yeni)  # Motor ayni sozlugu kullanir
        self._kayit_zamani = time.time() + 0.4
        return self._ayar

    def baslat(self):
        self._sonraki_degisim = None
        self._motor.baslat()
        return self._durum()

    def durdur(self):
        self._motor.durdur()
        return self._durum()

    def deneme(self, merkez):
        if self._motor.calisiyor:
            return
        m = max(0.0, min(BOLGE_SAYISI - 1e-6, float(merkez)))
        with self._kilit:
            self._deneme.append((m, time.time(), self._motor._renk_sec()))
            del self._deneme[:-kapasite(self._ayar)]

    def kucult(self):
        if self._pencere:
            self._pencere.minimize()

    def kapat(self):
        if self._pencere:
            self._pencere.destroy()

    # ---------------- ic isler ----------------
    def _durum(self):
        m = self._motor
        return {"calisiyor": m.calisiyor, "mesaj": m.durum, "hata": m.durum_hata}

    def _oto_degisim(self, simdi):
        """Acik ve calisiyorsa, sure dolunca rastgele baska bir efekte gecer.
        Kalan saniyeyi (ya da None) dondurur; efekt degistiyse ikinci deger True."""
        if not (self._ayar.get("oto_degis") and self._motor.calisiyor):
            self._sonraki_degisim = None
            return None, False
        aralik = max(1, int(self._ayar.get("oto_dakika", 5))) * 60
        if self._sonraki_degisim is None:
            self._sonraki_degisim = simdi + aralik
        if simdi < self._sonraki_degisim:
            return self._sonraki_degisim - simdi, False
        secenekler = [e for e, _, _ in EFEKTLER if e != self._ayar.get("efekt")]
        self._ayar["efekt"] = random.choice(secenekler)
        self._deneme.clear()
        with self._motor.kilit:
            self._motor.dalgalar.clear()
        self._sonraki_degisim = simdi + aralik
        self._kayit_zamani = simdi + 0.4
        return aralik, True

    def _galeri(self, simdi):
        """Her efekt icin 2.2 sn'de bir tekrarlanan demo basislariyla bir kare."""
        a = dict(self._ayar)
        a["bekleme_acik"] = False
        donem = 2.2
        basla = simdi - (simdi % donem)
        if a["mod"] == "sabit":
            renk = dalga.hex_rgb(a["renk"])
        else:
            r, g, b = dalga.colorsys.hsv_to_rgb((basla * 0.07) % 1.0, 1.0, 1.0)
            renk = (int(r * 255), int(g * 255), int(b * 255))
        kareler = {}
        for e, _, _ in EFEKTLER:
            a["efekt"] = e
            if e in ("isi", "seviye"):  # hizli yazma taklidi
                basislar = [(3.0 + (i % 3) * 0.7, basla + i * 0.09, renk)
                            for i in range(14) if basla + i * 0.09 <= simdi]
            else:
                merkez = 1.5 if e in ("yildiz", "sarkac") else 3.0
                basislar = [(merkez, basla, renk)]
            kareler[e] = kare_hesapla(basislar, simdi, a)
        return kareler

    def _dongu(self):
        js = getattr(self._pencere, "run_js", None) or self._pencere.evaluate_js
        sayac = 0
        while not self._dur.is_set():
            t0 = time.time()
            with self._kilit:
                if self._motor.calisiyor:
                    kare = self._motor.son_kare or kare_hesapla([], t0, self._ayar)
                else:
                    sure = omur_sure(self._ayar)
                    self._deneme[:] = [d for d in self._deneme if t0 - d[1] < sure]
                    kare = kare_hesapla(self._deneme, t0, self._ayar)
                galeri = self._galeri(t0) if sayac % 2 == 0 else None
            paket = {"kare": kare}
            if galeri is not None:
                paket["galeri"] = galeri
            d = self._durum()
            if d != self._son_durum:
                self._son_durum = d
                paket["durum"] = d
            with self._kilit:
                kalan, degisti = self._oto_degisim(t0)
            kalan = None if kalan is None else int(kalan + 0.999)
            if kalan != self._son_kalan:
                self._son_kalan = kalan
                paket["oto_kalan"] = kalan if kalan is not None else -1
            if degisti:
                paket["ayar"] = self._ayar
            try:
                js("window.dalgaKare && window.dalgaKare(%s)" % json.dumps(paket))
            except Exception:
                pass
            if self._kayit_zamani and t0 >= self._kayit_zamani:
                self._kayit_zamani = None
                ayar_kaydet(self._ayar)
            sayac += 1
            gecen = time.time() - t0
            self._dur.wait(max(0.0, 1 / FPS - gecen))

    def _baslat_dongu(self):
        threading.Thread(target=self._dongu, daemon=True).start()

    def _kapaniyor(self):
        self._dur.set()
        try:
            self._motor.durdur()
        finally:
            ayar_kaydet(self._ayar)


def main():
    api = Api()
    pencere = webview.create_window(
        "Dalga", HTML, js_api=api, width=1240, height=780, min_size=(1100, 700),
        frameless=True, easy_drag=False, background_color="#0b0b0d")
    api._pencere = pencere
    pencere.events.loaded += api._baslat_dongu
    pencere.events.closing += api._kapaniyor
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    main()
