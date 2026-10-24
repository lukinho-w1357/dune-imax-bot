"""
Bot que avisa cuando salen entradas (preventa) de Dune: Parte 3 en el IMAX
de Showcase Norcenter.

Usa la API pública que consume entradas.todoshowcase.com (Voy al Cine):
  - https://api.voyalcine.net/films                 -> películas cargadas
  - https://api.voyalcine.net/films/{id}/tree/3250  -> funciones en el IMAX

Uso:
  python dune_imax_bot.py           # chequea una vez
  python dune_imax_bot.py --test    # manda una notificación de prueba
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------- Configuración ----------------
# Tema de ntfy.sh para recibir push en el celular. NO va en el código porque
# el repo es público: se lee de la variable de entorno NTFY_TOPIC (secret de
# GitHub Actions) o, para correr local, del archivo ntfy_topic.txt (ignorado por git).
_topic_file = Path(__file__).resolve().parent / "ntfy_topic.txt"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip() or (
    _topic_file.read_text(encoding="utf-8").strip() if _topic_file.exists() else ""
)

# Regex para detectar la película por nombre (castellano o inglés).
TITLE_PATTERN = re.compile(r"\bdun[ae]\b", re.IGNORECASE)

IMAX_HOUSE_ID = 3250  # sala IMAX Theatre (Norcenter) en la API
API = "https://api.voyalcine.net"
TICKETS_URL = "https://entradas.todoshowcase.com/showcase/pelicula?filmid={id}&house_id=3250"
# -----------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "dune_imax_state.json"
LOG_FILE = BASE_DIR / "dune_imax_bot.log"


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def windows_toast(title, message):
    # Toast nativo de Windows vía PowerShell, sin dependencias extra.
    title = title.replace("'", "''")
    message = message.replace("'", "''")
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $t.GetElementsByTagName('text')
$n.Item(0).AppendChild($t.CreateTextNode('{title}')) > $null
$n.Item(1).AppendChild($t.CreateTextNode('{message}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Dune IMAX Bot').Show($toast)
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def ntfy_push(title, message, click_url=None):
    if not NTFY_TOPIC:
        return
    headers = {"Title": title.encode("utf-8"), "Priority": "urgent", "Tags": "film_projector"}
    if click_url:
        headers["Click"] = click_url
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode("utf-8"), headers=headers
    )
    urllib.request.urlopen(req, timeout=30)


def notify(title, message, click_url=None):
    log(f"NOTIFICACIÓN: {title} | {message}")
    if os.name == "nt":
        windows_toast(title, message)
    if not NTFY_TOPIC:
        log("Aviso: NTFY_TOPIC no está configurado, no se envía push al celular.")
        return
    try:
        ntfy_push(title, message, click_url)
    except Exception as e:
        # Nunca loguear el topic (los logs de Actions son públicos).
        log(f"Error enviando a ntfy: {str(e).replace(NTFY_TOPIC, '***')}")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen_films": [], "seen_performances": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check():
    state = load_state()
    films = get_json(f"{API}/films")
    matches = [f for f in films if TITLE_PATTERN.search(f.get("name", ""))]

    if not matches:
        log(f"Sin novedades ({len(films)} películas en la API, ninguna es Dune).")
        return

    for film in matches:
        fid, name = film["id"], film["name"].strip()
        url = TICKETS_URL.format(id=fid)

        # Aviso temprano: la película apareció en el sistema (aunque sin funciones IMAX aún).
        if fid not in state["seen_films"]:
            state["seen_films"].append(fid)
            notify("Dune apareció en Showcase", f"'{name}' ya está cargada en el sistema de entradas.", url)

        tree = get_json(f"{API}/films/{fid}/tree/{IMAX_HOUSE_ID}")
        new_perfs = []
        for day, cinemas in sorted((tree.get("days") or {}).items()):
            for cinema in cinemas:
                if "imax" not in cinema.get("name", "").lower():
                    continue
                for fmt in cinema.get("formats", []):
                    for p in fmt.get("performances", []):
                        pid = p["performanceId"]
                        if pid not in state["seen_performances"]:
                            state["seen_performances"].append(pid)
                            new_perfs.append(f"{day} {p['showTime']} ({fmt.get('formatDescription', '')})")

        if new_perfs:
            resumen = ", ".join(new_perfs[:5]) + (f" y {len(new_perfs) - 5} más" if len(new_perfs) > 5 else "")
            notify("¡ENTRADAS DUNE EN IMAX!", f"{len(new_perfs)} funciones nuevas: {resumen}", url)
        else:
            log(f"'{name}' (id {fid}) está en la API pero sin funciones nuevas en IMAX.")

    save_state(state)


if __name__ == "__main__":
    if "--test" in sys.argv:
        notify("Dune IMAX Bot", "Notificación de prueba: el bot funciona.", "https://www.todoshowcase.com/")
    else:
        try:
            check()
        except Exception as e:
            log(f"Error: {e!r}")
            sys.exit(1)
