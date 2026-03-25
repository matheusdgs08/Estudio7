"""
Serviço de Impressão Térmica — Estúdio Se7e
Impressora: Térmica 80mm USB (ESC/POS)
Roda no computador da recepção (Windows/Mac/Linux)
"""
import os, sys, time, json
from datetime import datetime
import urllib.request

# ── Config ──────────────────────────────────────────
API_BASE        = os.getenv("API_BASE",        "https://estudio7-production.up.railway.app")
API_KEY         = os.getenv("API_KEY",         "se7e2025")
JANELA_MIN      = int(os.getenv("JANELA_MIN",  "5"))   # imprimir X min antes
CHECK_SEC       = int(os.getenv("CHECK_SEC",   "60"))  # verificar a cada N segundos
PRINTER_VENDOR  = os.getenv("PRINTER_VENDOR",  None)   # ex: "0x04b8" (Epson)
PRINTER_PRODUCT = os.getenv("PRINTER_PRODUCT", None)   # ex: "0x0202"
# Se deixar None, usa a primeira térmica USB encontrada automaticamente
# ────────────────────────────────────────────────────

_impressos = set()

# ── ESC/POS helpers ──────────────────────────────────
ESC = b'\x1b'
GS  = b'\x1d'
LF  = b'\x0a'

def cmd(*parts):
    return b''.join(parts)

INIT        = ESC + b'@'
BOLD_ON     = ESC + b'E\x01'
BOLD_OFF    = ESC + b'E\x00'
ALIGN_L     = ESC + b'a\x00'
ALIGN_C     = ESC + b'a\x01'
ALIGN_R     = ESC + b'a\x02'
DOUBLE_H    = GS + b'!\x01'   # altura dupla
DOUBLE_HW   = GS + b'!\x11'   # largura+altura dupla
NORMAL_SIZE = GS + b'!\x00'
CUT         = GS + b'V\x41\x03'  # corte parcial com avanço
FEED3       = ESC + b'd\x03'  # avança 3 linhas

COLS = 48  # colunas em 80mm fonte normal

def linha(txt='', align='L'):
    t = str(txt)
    if align == 'C':
        t = t.center(COLS)
    elif align == 'R':
        t = t.rjust(COLS)
    else:
        t = t.ljust(COLS)
    return (t[:COLS] + '\n').encode('cp850', errors='replace')

def linha2col(esq, dir_, pad=COLS):
    """Linha com texto esquerdo e direito na mesma linha."""
    espaco = pad - len(str(esq)) - len(str(dir_))
    if espaco < 1: espaco = 1
    return (str(esq) + ' ' * espaco + str(dir_) + '\n').encode('cp850', errors='replace')

def separador(char='-'):
    return (char * COLS + '\n').encode('cp850', errors='replace')

def separador_duplo():
    return ('=' * COLS + '\n').encode('cp850', errors='replace')


def montar_ficha_escpos(ficha):
    """Monta bytes ESC/POS de uma ficha de treino."""
    buf = bytearray()

    data_fmt = datetime.strptime(ficha['data'], '%Y-%m-%d').strftime('%d/%m/%Y')
    hora_fmt = datetime.now().strftime('%H:%M')

    # ── Cabeçalho ──
    buf += INIT
    buf += ALIGN_C
    buf += DOUBLE_HW
    buf += BOLD_ON
    buf += 'ESTUDIO Se7e\n'.encode('cp850', errors='replace')
    buf += NORMAL_SIZE
    buf += BOLD_OFF
    buf += separador('═' if hasattr(str, 'center') else '=')

    # Nome do aluno
    buf += BOLD_ON
    buf += DOUBLE_H
    buf += ALIGN_C
    nm = ficha['nome'].upper()
    # Quebra se nome longo
    if len(nm) > 24:
        partes = nm.split()
        nm1 = partes[0]
        nm2 = ' '.join(partes[1:])[:24]
        buf += (nm1 + '\n').encode('cp850', errors='replace')
        buf += (nm2 + '\n').encode('cp850', errors='replace')
    else:
        buf += (nm + '\n').encode('cp850', errors='replace')

    buf += NORMAL_SIZE
    buf += BOLD_OFF

    # Ficha e data
    buf += ALIGN_C
    buf += BOLD_ON
    buf += ('[ ' + ficha['ficha_nome'].upper() + ' ]\n').encode('cp850', errors='replace')
    buf += BOLD_OFF
    buf += (data_fmt + '  -  IMPRESSO ' + hora_fmt + '\n').encode('cp850', errors='replace')
    buf += separador_duplo()

    # ── Exercícios ──
    buf += ALIGN_L
    for i, ex in enumerate(ficha['exercicios']):
        # Linha grupo (pequena)
        buf += ALIGN_L
        grupo = ex.get('grupo', '').upper()[:COLS]
        buf += ('  ' + grupo + '\n').encode('cp850', errors='replace')

        # Nome do exercício em negrito
        buf += BOLD_ON
        nome = ex['nome'].upper()
        # Quebra nomes longos
        if len(nome) > COLS - 2:
            palavras = nome.split(' - ')
            if len(palavras) > 1:
                # formato "APARELHO - MOVIMENTO"
                ap = palavras[0]
                mv = ' - '.join(palavras[1:])
                buf += ('  ' + ap + '\n').encode('cp850', errors='replace')
                buf += ('  ' + mv[:COLS-2] + '\n').encode('cp850', errors='replace')
            else:
                buf += ('  ' + nome[:COLS-2] + '\n').encode('cp850', errors='replace')
        else:
            buf += ('  ' + nome + '\n').encode('cp850', errors='replace')
        buf += BOLD_OFF

        # Series × Reps  |  Carga
        series_reps = f"  {ex['series']}x{ex['reps']}"
        carga = f"{ex['ultima_carga']} kg" if ex.get('ultima_carga') else 'SEM CARGA'

        # Carga em destaque se existe
        if ex.get('ultima_carga'):
            buf += BOLD_ON
        buf += linha2col(series_reps, carga)
        if ex.get('ultima_carga'):
            buf += BOLD_OFF

        # Descanso
        if ex.get('descanso'):
            buf += ('  descanso: ' + str(ex['descanso']) + 's\n').encode('cp850', errors='replace')

        # Observação
        if ex.get('obs'):
            obs = ex['obs'][:COLS - 5]
            buf += ('  ** ' + obs + '\n').encode('cp850', errors='replace')

        # Separador entre exercícios (exceto o último)
        if i < len(ficha['exercicios']) - 1:
            buf += separador('-')

    # ── Rodapé ──
    buf += separador_duplo()
    buf += ALIGN_C
    buf += 'Bom treino! :)\n'.encode('cp850', errors='replace')
    buf += FEED3
    buf += CUT

    return bytes(buf)


# ── Comunicação com a impressora USB ─────────────────

def get_printer():
    """Retorna objeto da impressora. Tenta usb, raw e win32print."""

    # Opção 1: python-escpos (pip install python-escpos)
    try:
        from escpos.printer import Usb, Win32Raw
        if sys.platform == 'win32':
            return Win32Raw()
        # Detecta automaticamente a primeira impressora térmica USB
        import usb.core
        if PRINTER_VENDOR and PRINTER_PRODUCT:
            vid = int(PRINTER_VENDOR, 16)
            pid = int(PRINTER_PRODUCT, 16)
            return Usb(vid, pid)
        # Tenta encontrar automaticamente
        vendors_conhecidos = [0x04b8, 0x067b, 0x0483, 0x154f, 0x0dd4, 0x1fc9]
        for dev in usb.core.find(find_all=True):
            if dev.idVendor in vendors_conhecidos:
                try:
                    p = Usb(dev.idVendor, dev.idProduct)
                    return p
                except:
                    pass
    except ImportError:
        pass

    # Opção 2: Envio direto via /dev/usb/lp0 (Linux)
    if sys.platform != 'win32' and os.path.exists('/dev/usb/lp0'):
        class RawPrinter:
            def __init__(self, path='/dev/usb/lp0'):
                self.path = path
            def write(self, data):
                with open(self.path, 'wb') as f:
                    f.write(data)
        return RawPrinter()

    # Opção 3: Windows — win32print
    if sys.platform == 'win32':
        try:
            import win32print
            class Win32Printer:
                def write(self, data):
                    pname = win32print.GetDefaultPrinter()
                    h = win32print.OpenPrinter(pname)
                    try:
                        win32print.StartDocPrinter(h, 1, ("Ficha Treino", None, "RAW"))
                        win32print.StartPagePrinter(h)
                        win32print.WritePrinter(h, data)
                        win32print.EndPagePrinter(h)
                        win32print.EndDocPrinter(h)
                    finally:
                        win32print.ClosePrinter(h)
            return Win32Printer()
        except ImportError:
            pass

    raise RuntimeError(
        "Impressora não encontrada. Instale 'python-escpos' ou configure PRINTER_VENDOR/PRINTER_PRODUCT.\n"
        "  pip install python-escpos pyusb\n"
        "  (Windows também: pip install pywin32)"
    )


def imprimir_ficha(ficha, printer):
    dados = montar_ficha_escpos(ficha)
    printer.write(dados)
    print(f"  🖨️  {ficha['nome']} — {ficha['ficha_nome']}")


# ── API helpers ───────────────────────────────────────

def api_get(path):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"x-api-key": API_KEY}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def api_post(path):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=b'{}',
        method="POST",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ── Loop principal ────────────────────────────────────

def verificar(printer):
    agora = datetime.now()
    data  = agora.strftime("%Y-%m-%d")

    try:
        resp = api_get(f"/impressao/horarios/{data}")
    except Exception as e:
        print(f"  ⚠️  API inacessível: {e}")
        return

    for h in resp.get("horarios", []):
        hora_aula = datetime.strptime(f"{data} {h['horario']}", "%Y-%m-%d %H:%M")
        diff_min  = (hora_aula - agora).total_seconds() / 60
        if 0 <= diff_min <= JANELA_MIN:
            print(f"  ⏰ {h['horario']} ({diff_min:.1f}min) — {h['confirmados']} alunos")
            try:
                dados = api_get(f"/impressao/aula/{h['slot_id']}/{data}")
            except Exception as e:
                print(f"  ❌ {e}"); continue

            for ficha in dados.get("fichas", []):
                eid = ficha["enrollment_id"]
                if eid in _impressos or ficha.get("ja_impressa"):
                    continue
                try:
                    imprimir_ficha(ficha, printer)
                    api_post(f"/impressao/marcar/{eid}")
                    _impressos.add(eid)
                except Exception as e:
                    print(f"  ❌ Erro ao imprimir {ficha['nome']}: {e}")


def main():
    print("=" * 50)
    print("  Serviço de Impressão — Estúdio Se7e")
    print("  Impressora: Térmica 80mm USB (ESC/POS)")
    print(f"  API: {API_BASE}")
    print(f"  Janela: {JANELA_MIN} min antes da aula")
    print("=" * 50)

    # Conectar impressora
    try:
        printer = get_printer()
        print("  ✅ Impressora conectada\n")
    except Exception as e:
        print(f"\n  ❌ ERRO: {e}\n")
        print("  Verifique se a impressora está ligada e conectada via USB.")
        print("  Para instalar dependências:")
        print("    pip install python-escpos pyusb")
        if sys.platform == 'win32':
            print("    pip install pywin32")
        sys.exit(1)

    # Imprimir teste
    try:
        teste_bytes = (
            INIT + ALIGN_C + BOLD_ON +
            "TESTE OK - Estudio Se7e\n".encode('cp850') +
            BOLD_OFF + FEED3 + CUT
        )
        printer.write(teste_bytes)
        print("  🖨️  Página de teste impressa\n")
    except Exception as e:
        print(f"  ⚠️  Teste de impressão falhou: {e}\n")

    print("  Monitorando horários...\n")
    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] verificando...")
        try:
            verificar(printer)
        except Exception as e:
            print(f"  ⚠️  {e}")
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    main()
