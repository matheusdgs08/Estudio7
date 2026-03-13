# Estúdio Se7e — Sistema Operacional

Sistema de gestão interno do Estúdio Se7e, academia boutique fitness em Vila Mariana, São Paulo.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Banco de dados | Supabase (PostgreSQL) |
| Backend | Python + FastAPI |
| Frontend Web | React + Tailwind CSS |
| App Aluno / Professor | React Native (fase 2) |
| WhatsApp | Z-API (2 instâncias) |
| Push notifications | Expo Push / Firebase |
| Deploy | Railway |

## Estrutura do Repositório

```
estudio7/
├── docs/               # Documentação v3 (regras, banco, arquitetura, fluxos)
├── database/           # Schema SQL, migrations, seeds
│   ├── schema.sql      # Schema completo Supabase
│   ├── migrations/     # Alterações incrementais
│   └── seeds/          # Dados iniciais
├── backend/            # Python + FastAPI (fase 2)
├── frontend/           # React + Tailwind CSS (fase 3)
├── app-aluno/          # React Native — App do Aluno (fase 8)
└── app-professor/      # React Native — App do Professor (fase 9)
```

## Fases de Implementação

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Schema banco de dados (Supabase + RLS) | ✅ Concluída |
| 2 | Backend FastAPI (contratos, agenda, rodízio) | 🔲 Pendente |
| 3 | Frontend React (painel admin, recepção, coordenador) | 🔲 Pendente |
| 4 | Motor de treinos (sequências, histórico, impressão) | 🔲 Pendente |
| 5 | Migração de dados do Tecnofit/Bubble | 🔲 Pendente |
| 6 | Período paralelo (dois sistemas) | 🔲 Pendente |
| 7 | Desativação do Tecnofit e Bubble | 🔲 Pendente |
| 8 | App do Aluno (React Native) | 🔲 Pendente |
| 9 | App do Professor (React Native / PWA) | 🔲 Pendente |

## Documentação

Consulte a pasta `/docs` para os documentos v3:
- `regras_de_negocio_v3.md` — Regras completas do negócio
- `banco_de_dados_v3.md` — Modelo do banco de dados
- `arquitetura_v3.md` — Arquitetura do sistema
- `fluxos_operacionais_v3.md` — Fluxos passo a passo

## Banco de Dados

O schema completo está em `database/schema.sql`.  
Execute no **Supabase SQL Editor** para criar todas as tabelas, índices e RLS.

---
*Projeto privado — Estúdio Se7e / Matheus*
