# Serviço de Impressão Térmica — Estúdio Se7e
## Impressora: 80mm USB (ESC/POS)

### 1. Instalar dependências

```bash
pip install python-escpos pyusb
# Windows também:
pip install pywin32
```

### 2. Windows: dar permissão USB (se necessário)

Baixar e instalar **Zadig** (https://zadig.akeo.ie)  
→ Selecionar a impressora → Instalar driver **libusb-win32**

### 3. Linux: permissão no dispositivo

```bash
sudo chmod 666 /dev/usb/lp0
# ou adicionar ao grupo lp:
sudo usermod -a -G lp $USER
```

### 4. Configurar (opcional)

Variáveis de ambiente ou editar no início do arquivo:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `API_BASE` | `https://estudio7-production.up.railway.app` | URL da API |
| `API_KEY` | `se7e2025` | Chave da API |
| `JANELA_MIN` | `5` | Minutos antes da aula para imprimir |
| `CHECK_SEC` | `60` | Intervalo de verificação em segundos |
| `PRINTER_VENDOR` | auto | Vendor ID hex (ex: `0x04b8` = Epson) |
| `PRINTER_PRODUCT` | auto | Product ID hex |

### 5. Executar

```bash
python impressora.py
```

### 6. Iniciar automaticamente (Windows)

Criar arquivo `iniciar.bat`:
```bat
@echo off
cd C:\se7e
python impressora.py
```
Adicionar ao **Inicializações do Windows** (Win+R → `shell:startup`)

### 7. Marcas compatíveis

Epson TM-T20, TM-T88 · Bematech MP-4200 · Daruma DR700 · 
Elgin i9 · Sweda SI-300S · Gertec GC600 · e qualquer térmica ESC/POS

### Saída esperada no terminal

```
==================================================
  Serviço de Impressão — Estúdio Se7e
  Impressora: Térmica 80mm USB (ESC/POS)
  API: https://estudio7-production.up.railway.app
  Janela: 5 min antes da aula
==================================================
  ✅ Impressora conectada
  🖨️  Página de teste impressa

  Monitorando horários...

[08:55:01] verificando...
  ⏰ 09:00 (4.8min) — 8 alunos
  🖨️  MARIA SILVA — TREINO A
  🖨️  JOAO SANTOS — TREINO B
```
