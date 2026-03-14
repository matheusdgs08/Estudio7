-- Migration: algoritmo inteligente de rodízio + job T-5min
-- Data: 2026-03-13

-- ============================================================
-- ALGORITMO INTELIGENTE DE DISTRIBUIÇÃO
-- ============================================================
-- assign_instructors_smart():
--   Para cada aluno presente sem professor:
--   1. Busca último professor do aluno (workout_logs)
--   2. Tenta o próximo da fila que NÃO foi o último
--   3. Se não achou diferente → usa próximo da fila mesmo
--   4. Se p_late_only=true (aluno tardio) → próximo simples, sem match

-- handle_late_checkin():
--   Aluno faz check-in após a impressão das fichas (T-5min)
--   Sistema atribui o próximo da fila sem lógica de histórico
--   Ficha fica marcada para impressão individual

-- job_pre_class():
--   Roda todo minuto via pg_cron
--   Detecta aulas que começam em 5 minutos
--   Executa: assign_instructors_smart + marca printed_at

-- ============================================================
-- CRON JOBS
-- ============================================================
-- [* * * * *]  job-pre-class       → distribuição + impressão T-5min
-- [0 0 * * *]  rotate-schedule-midnight → rotação da escala à meia-noite

-- ============================================================
-- REGRAS DE NEGÓCIO IMPLEMENTADAS
-- ============================================================
-- Distribuição automática T-5min (sem ação da recepção)
-- Alunos tardios: próximo da fila simples
-- Alunos normais: evita repetir último professor, respeita fila
-- Fila: ORDER BY aulas_hoje ASC, priority_order ASC
-- Se todos os profs foram recentes: respeita fila acima de tudo
-- Ninguém pode alterar professor manualmente
-- Botão "Distribuir com IA" = contingência se job falhar
