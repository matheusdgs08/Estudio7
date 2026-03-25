"""
Serviço Local de Impressão — Estúdio Se7e
Roda no computador da recepção.
Busca fichas via API a cada minuto e imprime 5 min antes da aula.
"""
import os, time, json, threading, webbrowser, tempfile
from datetime import datetime, timedelta
import urllib.request, urllib.error

# ── Config ──
API_BASE   = os.getenv("API_BASE",   "https://estudio7-production.up.railway.app")
API_KEY    = os.getenv("API_KEY",    "se7e2025")
JANELA_MIN = int(os.getenv("JANELA_MIN", "5"))   # imprime X minutos antes
CHECK_INTERVALO = int(os.getenv("CHECK_INTERVALO", "60"))  # verifica a cada N segundos

_impressos = set()  # enrollment_ids já impressos nesta sessão

def api_get(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"x-api-key": API_KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def api_post(path, data=None):
    url  = f"{API_BASE}{path}"
    body = json.dumps(data or {}).encode()
    req  = urllib.request.Request(url, data=body, method="POST",
             headers={"x-api-key": API_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def gerar_html_ficha(ficha):
    """Gera HTML de uma ficha individual para impressão."""
    data_fmt = datetime.strptime(ficha["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
    exercicios_html = ""
    for ex in ficha["exercicios"]:
        carga = f"{ex['ultima_carga']} kg" if ex["ultima_carga"] else "—"
        bg = "#fff" if ficha["exercicios"].index(ex) % 2 == 0 else "#F9F7F4"
        exercicios_html += f"""
        <tr style="background:{bg}">
          <td style="padding:6px 10px;font-size:12px;color:#4A453F">{ex['grupo']}</td>
          <td style="padding:6px 10px;font-size:13px;font-weight:600;color:#1C1916">{ex['nome']}</td>
          <td style="padding:6px 10px;font-size:13px;text-align:center;color:#6D28D9;font-weight:700">{ex['series']}×{ex['reps']}</td>
          <td style="padding:6px 10px;font-size:13px;text-align:center;font-weight:700;color:{"#DC2626" if ex["ultima_carga"] else "#8A8278"}">{carga}</td>
          <td style="padding:6px 10px;font-size:11px;color:#8A8278">{ex['obs'] or ""}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Treino — {ficha['nome']}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; padding:16px; max-width:720px; margin:0 auto }}
  @media print {{
    body {{ padding:8px }}
    .no-print {{ display:none }}
  }}
</style>
</head><body>
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding-bottom:10px;border-bottom:3px solid #6D28D9">
  <div>
    <div style="font-size:22px;font-weight:900;color:#1C1916">{ficha['nome']}</div>
    <div style="font-size:13px;color:#6D28D9;font-weight:700">{ficha['ficha_nome']}</div>
    <div style="font-size:12px;color:#8A8278;margin-top:2px">{data_fmt}</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:32px;font-weight:900;color:#6D28D9">{ficha['ficha_nome'].split()[-1] if ficha['ficha_nome'].split() else ''}</div>
    <div style="font-size:11px;color:#8A8278">ESTÚDIO Se7e</div>
  </div>
</div>
<table style="width:100%;border-collapse:collapse;border:1px solid #E8E3DC;border-radius:8px;overflow:hidden">
  <thead>
    <tr style="background:#1C1916;color:#fff">
      <th style="padding:8px 10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.5px;width:90px">Grupo</th>
      <th style="padding:8px 10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Exercício</th>
      <th style="padding:8px 10px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:.5px;width:70px">Séries</th>
      <th style="padding:8px 10px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:.5px;width:80px">Carga</th>
      <th style="padding:8px 10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.5px;width:120px">Obs</th>
    </tr>
  </thead>
  <tbody>{exercicios_html}</tbody>
</table>
<div style="margin-top:10px;padding:8px;background:#F5F0E8;border-radius:6px;font-size:11px;color:#8A8278;text-align:center">
  Impresso automaticamente às {datetime.now().strftime("%H:%M")} · Estúdio Se7e
</div>
<script>window.onload=function(){{window.print();setTimeout(function(){{window.close();}},1000);}}</script>
</body></html>"""

def imprimir_ficha(ficha):
    """Salva HTML em arquivo temp e abre para impressão via Chrome --kiosk-printing."""
    html = gerar_html_ficha(ficha)
    tmp  = tempfile.NamedTemporaryFile(mode="w", suffix=".html",
             delete=False, encoding="utf-8")
    tmp.write(html)
    tmp.close()

    # Tenta Chrome com kiosk-printing (sem diálogo)
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    chrome = next((p for p in chrome_paths if os.path.exists(p)), None)
    if chrome:
        os.system(f'"{chrome}" --headless --disable-gpu --print-to-pdf="{tmp.name}.pdf" '
                  f'--no-margins "file:///{tmp.name}" 2>/dev/null || '
                  f'"{chrome}" --kiosk-printing "file:///{tmp.name}"')
    else:
        # Fallback: abre no navegador padrão
        webbrowser.open(f"file:///{tmp.name}")

    print(f"  🖨️  {ficha['nome']} — {ficha['ficha_nome']}")

def verificar_e_imprimir():
    agora = datetime.now()
    data  = agora.strftime("%Y-%m-%d")

    print(f"\n[{agora.strftime('%H:%M:%S')}] Verificando horários...")

    try:
        resp = api_get(f"/impressao/horarios/{data}")
    except Exception as e:
        print(f"  ❌ Erro ao buscar horários: {e}")
        return

    for h in resp.get("horarios", []):
        # Verifica se está dentro da janela de impressão (próximos JANELA_MIN min)
        hora_aula = datetime.strptime(f"{data} {h['horario']}", "%Y-%m-%d %H:%M")
        diff_min  = (hora_aula - agora).total_seconds() / 60

        if 0 <= diff_min <= JANELA_MIN:
            print(f"  ⏰ {h['horario']} — {h['confirmados']} alunos — {diff_min:.1f}min p/ início")
            try:
                dados = api_get(f"/impressao/aula/{h['slot_id']}/{data}")
            except Exception as e:
                print(f"  ❌ Erro ao buscar fichas: {e}")
                continue

            for ficha in dados.get("fichas", []):
                eid = ficha["enrollment_id"]
                if eid in _impressos or ficha.get("ja_impressa"):
                    continue  # já impresso

                try:
                    imprimir_ficha(ficha)
                    api_post(f"/impressao/marcar/{eid}")
                    _impressos.add(eid)
                except Exception as e:
                    print(f"  ❌ Erro ao imprimir {ficha['nome']}: {e}")

def loop_impressao():
    print("🖨️  Serviço de impressão iniciado")
    print(f"   API: {API_BASE}")
    print(f"   Janela: {JANELA_MIN} min antes da aula")
    print(f"   Verificação: a cada {CHECK_INTERVALO}s\n")

    while True:
        try:
            verificar_e_imprimir()
        except Exception as e:
            print(f"Erro inesperado: {e}")
        time.sleep(CHECK_INTERVALO)

if __name__ == "__main__":
    loop_impressao()
