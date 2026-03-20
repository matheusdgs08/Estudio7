# Estúdio Se7e — Backend API

FastAPI + Supabase. Deploy no Railway.

## Variáveis de ambiente (Railway → Variables)

```
SUPABASE_URL=https://kfmkcbhalwupgknysukj.supabase.co
SUPABASE_KEY=<service_role_key>
API_SECRET=<uma_string_aleatoria_segura>
```

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status + teste Supabase |
| GET | `/alunos` | Lista todos os alunos |
| GET | `/alunos/{id}` | Dados de um aluno |
| GET | `/alunos/{id}/programas` | Programas do aluno |
| GET | `/programas/{id}/fichas` | Fichas com exercícios |
| POST | `/programas/salvar` | Salva programa completo |
| GET | `/exercises` | Catálogo de exercícios |
| POST | `/exercises` | Adiciona exercício |
| GET | `/alunos/{id}/avaliacoes` | Avaliações físicas |
| POST | `/avaliacoes` | Cria avaliação |

## Auth

Todas as rotas (exceto `/` e `/health`) requerem header:
```
x-api-key: <API_SECRET>
```

## Deploy Railway

1. Novo projeto → "Deploy from GitHub repo"
2. Aponta para este repo (branch `main`)
3. Adiciona as variáveis de ambiente acima
4. Railway detecta `Procfile` automaticamente
