"""
gg.py - SteelSeries GG ile uyum.

Sorun: GG'nin isik motoru (SteelSeriesEngine + SteelSeriesPrism) klavyeye
surekli kendi rengini yazar, Dalga'nin renkleriyle karisir.

Cozum: Dalga calisirken bu iki sureci DONDURUR (suspend), durunca kaldigi
yerden DEVAM ETTIRIR (resume). GG'nin geri kalani (Sonar, arayuz vb.) hic
etkilenmez; Engine devam edince GG'deki isik profili kendiliginden geri gelir.

Dalga cokerse diye dondurulan surecler bir dosyaya yazilir; Dalga bir sonraki
acilista onlari otomatik devam ettirir. (GG'yi yeniden baslatmak da duzeltir.)
Sadece Windows'un kendi DLL'leri kullanilir, pip install GEREKMEZ.
"""

import atexit
import ctypes
import json
import os
import subprocess

HEDEFLER = ("SteelSeriesEngine.exe", "SteelSeriesPrism.exe")
KAYIT = os.path.join(os.environ.get("TEMP", "."), "dalga_gg_donuk.json")
PROCESS_SUSPEND_RESUME = 0x0800

_ntdll = ctypes.WinDLL("ntdll")
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.restype = ctypes.c_void_p
_k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
_k32.CloseHandle.argtypes = [ctypes.c_void_p]
_ntdll.NtSuspendProcess.argtypes = [ctypes.c_void_p]
_ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]


def _pidler(ad):
    try:
        cikti = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq " + ad, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, creationflags=0x08000000).stdout
    except Exception:
        return []
    sonuc = []
    for satir in cikti.splitlines():
        parca = satir.strip().strip('"').split('","')
        if len(parca) > 1 and parca[0].lower() == ad.lower():
            try:
                sonuc.append(int(parca[1]))
            except ValueError:
                pass
    return sonuc


def _uygula(pid, dondur):
    h = _k32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
    if not h:
        return False
    try:
        fn = _ntdll.NtSuspendProcess if dondur else _ntdll.NtResumeProcess
        return fn(h) == 0
    finally:
        _k32.CloseHandle(h)


def _kaydi_yaz(pidler):
    try:
        if pidler:
            with open(KAYIT, "w") as f:
                json.dump(pidler, f)
        elif os.path.exists(KAYIT):
            os.remove(KAYIT)
    except Exception:
        pass


def artiklari_coz():
    """Onceki bir Dalga oturumu cokup Engine'i donuk biraktiysa devam ettirir."""
    try:
        with open(KAYIT) as f:
            eski = json.load(f)
    except Exception:
        return
    canli = {p for ad in HEDEFLER for p in _pidler(ad)}
    for pid in eski:
        if pid in canli:
            _uygula(pid, False)
    _kaydi_yaz([])


class GG:
    def __init__(self):
        self.donuk = []
        artiklari_coz()
        atexit.register(self.birak)

    def calisiyor_mu(self):
        return bool(_pidler(HEDEFLER[0]))

    def devral(self):
        """GG isik motorunu dondurur. GG kapaliysa False (sorun degil)."""
        if self.donuk:
            return True
        for ad in HEDEFLER:
            for pid in _pidler(ad):
                if _uygula(pid, True):
                    self.donuk.append(pid)
        _kaydi_yaz(self.donuk)
        return bool(self.donuk)

    def birak(self):
        """Dondurulan surecleri devam ettirir; GG isiklari geri gelir."""
        for pid in reversed(self.donuk):
            _uygula(pid, False)
        self.donuk = []
        _kaydi_yaz([])
