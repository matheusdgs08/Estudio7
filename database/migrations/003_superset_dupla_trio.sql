-- Migration: superset (dupla/trio) em training_exercises
-- Data: 2026-03-13

-- Adiciona suporte a duplas e trios na tabela de exercícios do treino
alter table training_exercises
  add column if not exists superset_group_id uuid,
  add column if not exists superset_order    int,
  add column if not exists superset_type     text
    check (superset_type in ('dupla', 'trio') or superset_type is null);

-- Índice para buscar exercícios do mesmo bloco
create index if not exists idx_tex_superset
  on training_exercises(superset_group_id)
  where superset_group_id is not null;

-- REGRAS:
-- superset_group_id = NULL  → exercício individual
-- superset_group_id = UUID  → exercícios do mesmo bloco compartilham o mesmo UUID
-- superset_order = 1,2      → ordem dentro da dupla
-- superset_order = 1,2,3    → ordem dentro do trio
-- rest_seconds só é preenchido no ÚLTIMO exercício do bloco
--   (os demais ficam null = sem descanso entre eles)
-- Na ficha impressa: agrupados visualmente com label 'Dupla' ou 'Trio'
