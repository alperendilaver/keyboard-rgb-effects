"""
gg.py - SteelSeries GG ile uyum.

Dalga calisirken GG'nin kendi isik efektini klavyeye yazmasini durdurur,
Dalga durunca GG'deki secili isik profilini geri getirir.

Nasil: GG'nin yerel GameSense sunucusuna (sadece 127.0.0.1) "DALGA" adinda bir
oyun tanitir. Oyun aktifken GG profil efektini askiya alir ve klavyeyi oyuna
birakir; oyun durdurulunca profil geri yuklenir. GG'nin kendisi (Sonar vb.)
kapatilmaz. pip install GEREKMEZ.
"""

import json
import os
import threading
import urllib.request

OYUN = "DALGA"
OLAY = "AKTIF"
CORE = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                    "SteelSeries", "SteelSeries Engine 3", "coreProps.json")


def _adres():
    try:
        with open(CORE, "r", encoding="utf-8") as f:
            return json.load(f)["address"]
    except Exception:
        return None


def _post(adres, yol, veri):
    istek = urllib.request.Request(
        "http://%s/%s" % (adres, yol), data=json.dumps(veri).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=3) as r:
        r.read()


class GG:
    def __init__(self):
        self.adres = None
        self._dur = threading.Event()
        self._thread = None
        self._sayac = 0

    def devral(self):
        """GG'nin klavye isiklarini duraklatir. GG yoksa False (sorun degil)."""
        self.adres = _adres()
        if not self.adres:
            return False
        try:
            _post(self.adres, "game_metadata", {
                "game": OYUN, "game_display_name": "Dalga", "developer": "dalga",
                "deinitialize_timer_length_ms": 60000})
            _post(self.adres, "bind_game_event", {
                "game": OYUN, "event": OLAY, "min_value": 0, "max_value": 100,
                "value_optional": True,
                "handlers": [{"device-type": "keyboard", "zone": "all", "mode": "color",
                              "color": {"red": 0, "green": 0, "blue": 0}}]})
            self._olay()
        except Exception:
            self.adres = None
            return False
        self._dur.clear()
        self._thread = threading.Thread(target=self._nabiz, daemon=True)
        self._thread.start()
        return True

    def _olay(self):
        # deger her seferinde degissin ki GG olayi tekrar sayip zaman asimini sifirlasin
        self._sayac = (self._sayac + 1) % 100
        _post(self.adres, "game_event", {"game": OYUN, "event": OLAY,
                                         "data": {"value": self._sayac}})

    def _nabiz(self):
        while not self._dur.wait(10):
            try:
                _post(self.adres, "game_heartbeat", {"game": OYUN})
            except Exception:
                pass

    def birak(self):
        """GG'deki secili isik profilini geri getirir."""
        self._dur.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        adres = self.adres or _adres()
        self.adres = None
        if not adres:
            return False
        try:
            _post(adres, "stop_game", {"game": OYUN})
            _post(adres, "remove_game", {"game": OYUN})
            return True
        except Exception:
            return False
