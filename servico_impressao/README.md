# Serviço Local de Impressão — Estúdio Se7e

Roda no computador da recepção. Verifica a cada minuto se há aulas
começando nos próximos 5 minutos e imprime as fichas automaticamente.

## Instalação

1. Instalar Python 3.8+ no computador
2. Instalar Google Chrome

## Configuração

Variáveis de ambiente (ou editar no topo do arquivo):

```bash
API_BASE=https://estudio7-production.up.railway.app
API_KEY=se7e2025
JANELA_MIN=5       # imprimir X minutos antes da aula
CHECK_INTERVALO=60 # verificar a cada N segundos
```

## Executar

```bash
python impressora.py
```

## Executar como serviço (Windows — Task Scheduler)

Criar tarefa agendada:
- Programa: `python`
- Argumentos: `C:\se7e\impressora.py`
- Iniciar quando: "Ao fazer logon"
- Executar continuamente

## Executar como serviço (Mac/Linux — cron)

```bash
# crontab -e
@reboot cd /path/to/se7e && python impressora.py >> /tmp/impressora.log 2>&1 &
```

## Logs

O serviço imprime no terminal:
```
[08:55:01] Verificando horários...
  ⏰ 09:00 — 8 alunos — 4.9min p/ início
  🖨️  Maria Silva — Treino A
  🖨️  João Santos — Treino B
  ...
```
