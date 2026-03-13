-- ============================================================
-- ESTÚDIO SE7E — Schema Completo Supabase / PostgreSQL
-- v3.0 | 2025
-- Gerado com base na documentação v3 + análise do Bubble.io
-- ============================================================

-- ============================================================
-- 0. EXTENSÕES
-- ============================================================
create extension if not exists "uuid-ossp";
create extension if not exists "pg_cron";


-- ============================================================
-- 1. ENUMS
-- ============================================================

create type user_role as enum (
  'admin',
  'coordinator',
  'receptionist',
  'teacher',
  'student'
);

create type contract_status as enum (
  'active',
  'paused',
  'ended',
  'cancelled'
);

create type payment_type as enum (
  'monthly',
  'recurring',
  'annual'
);

create type pause_type as enum (
  'vacation',
  'medical',
  'administrative'
);

create type enrollment_type as enum (
  'fixed',
  'original_flexible',
  'replacement',
  'replacement_from_flexible',
  'extra_credit',
  'saturday'
);

create type enrollment_status as enum (
  'confirmed',
  'attended',
  'missed',
  'cancelled'
);

create type slot_type as enum (
  'normal',
  'saturday'
);

create type waitlist_status as enum (
  'waiting',
  'notified',
  'enrolled',
  'removed'
);

create type credit_origin as enum (
  'cancellation',
  'transferred',
  'extra_credit'
);

create type payment_status as enum (
  'pending',
  'paid',
  'failed',
  'refunded'
);

create type payment_type_item as enum (
  'monthly',
  'annual',
  'upgrade',
  'downgrade_credit',
  'extra_credit'
);

create type lead_status as enum (
  'new',
  'scheduled',
  'attended',
  'no_show',
  'converted',
  'lost'
);

create type experimental_status as enum (
  'scheduled',
  'confirmed',
  'attended',
  'no_show',
  'rescheduled',
  'converted'
);

create type change_request_status as enum (
  'pending',
  'approved',
  'rejected'
);

create type notification_channel as enum (
  'push',
  'whatsapp',
  'both'
);

create type notification_event as enum (
  'experimental_confirmed',
  'experimental_reminder',
  'followup_24h',
  'followup_72h',
  'followup_7d',
  'waitlist_slot_open',
  'physical_assessment_reminder',
  'delinquency_warning',
  'delinquency_block',
  'contract_cancelled',
  'exercise_change_approved',
  'exercise_change_rejected'
);


-- ============================================================
-- 2. PESSOAS
-- ============================================================

-- profiles: espelha auth.users do Supabase
create table profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  full_name     text not null,
  phone         text,                          -- WhatsApp principal (com DDI, ex: 5511999990000)
  role          user_role not null default 'student',
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

comment on table profiles is 'Usuários do sistema. id = auth.users.id do Supabase Auth.';
comment on column profiles.phone is 'Número WhatsApp com DDI. Ex: 5511999990000';


-- students: extensão de profiles para alunos
create table students (
  id                    uuid primary key references profiles(id) on delete cascade,
  matricula             int unique,                    -- Matrícula no Tecnofit (para migração)
  phone_secondary       text,
  birth_date            date,
  notes                 text,                          -- Observações gerais / restrições saúde
  next_training_session int not null default 1,        -- Índice do próximo treino na sequência
  current_program_id    uuid,                          -- FK adicionada após criar training_programs
  blocked               boolean not null default false,
  blocked_reason        text
);

comment on column students.next_training_session is 'Posição atual na sequência de treinos. Avança apenas quando há presença confirmada.';
comment on column students.matricula is 'Matrícula original no Tecnofit. Usado durante migração e período paralelo.';


-- leads: prospects captados via WhatsApp comercial
create table leads (
  id                    uuid primary key default uuid_generate_v4(),
  name                  text not null,
  phone                 text not null,
  origin                text,                  -- 'instagram' | 'indicação' | 'google' | 'outro'
  status                lead_status not null default 'new',
  converted_student_id  uuid references students(id),
  notes                 text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);


-- ============================================================
-- 3. PLANOS
-- ============================================================

create table plans (
  id                  uuid primary key default uuid_generate_v4(),
  name                text not null,           -- Ex: Plano 3x Semanal
  frequency_per_week  int not null check (frequency_per_week between 1 and 5),
  monthly_price       numeric(10,2),
  recurring_price     numeric(10,2),
  annual_price        numeric(10,2),
  renewal_price       numeric(10,2),           -- Preço especial de renovação
  annual_classes      int,                     -- Total de aulas no plano anual
  active              boolean not null default true,
  created_at          timestamptz not null default now()
);

comment on column plans.annual_classes is 'Ex: 2x/semana = 108 aulas. Calculado como frequency_per_week * 54.';


-- ============================================================
-- 4. CONTRATOS
-- ============================================================

create table contracts (
  id                        uuid primary key default uuid_generate_v4(),
  student_id                uuid not null references students(id),
  plan_id                   uuid not null references plans(id),
  payment_type              payment_type not null,
  has_fixed_schedule        boolean not null default true,  -- false = aluno flexível
  total_classes             int not null,
  remaining_classes         int not null,
  start_date                date not null,
  end_date                  date not null,
  status                    contract_status not null default 'active',
  previous_contract_id      uuid references contracts(id),
  replacements_transferred  boolean not null default false,
  upgrade_downgrade_from    uuid references contracts(id),
  pause_start               date,
  pause_end                 date,
  pause_type                pause_type,
  due_date                  date,                           -- Vencimento do pagamento
  grace_period_end          date generated always as (due_date + interval '7 days') stored,
  created_by                uuid not null references profiles(id),
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),

  constraint remaining_non_negative check (remaining_classes >= 0),
  constraint pause_dates_valid check (
    (pause_start is null and pause_end is null) or
    (pause_start is not null and pause_end is not null and pause_end > pause_start)
  )
);

comment on column contracts.has_fixed_schedule is 'true = aluno com horário fixo. false = aluno flexível que agenda conforme disponibilidade.';
comment on column contracts.replacements_transferred is 'true = reposições do contrato anterior já foram transferidas. Irreversível.';
comment on column contracts.grace_period_end is 'Calculado automaticamente: due_date + 7 dias.';


-- horários fixos reservados por contrato
create table fixed_slots (
  id              uuid primary key default uuid_generate_v4(),
  student_id      uuid not null references students(id),
  contract_id     uuid not null references contracts(id),
  class_slot_id   uuid not null,               -- FK adicionada após criar class_slots
  start_date      date not null,
  end_date        date not null,               -- = contract.end_date
  active          boolean not null default true,  -- false = inativo/trocado
  created_at      timestamptz not null default now()
);


-- ============================================================
-- 5. CRÉDITOS DE REPOSIÇÃO
-- ============================================================

create table replacement_credits (
  id                  uuid primary key default uuid_generate_v4(),
  student_id          uuid not null references students(id),
  contract_id         uuid not null references contracts(id),
  origin_type         credit_origin not null,
  source_contract_id  uuid references contracts(id),   -- Preenchido se origin_type = 'transferred'
  quantity_total      int not null check (quantity_total > 0),
  quantity_remaining  int not null check (quantity_remaining >= 0),
  expires_at          timestamptz,                     -- NULL = vale até contract.end_date
  active              boolean not null default true,
  created_at          timestamptz not null default now(),

  constraint quantity_remaining_lte_total check (quantity_remaining <= quantity_total)
);

comment on column replacement_credits.expires_at is 'NULL por padrão — reposição vale até contract.end_date. Não expira em 72h.';
comment on column replacement_credits.source_contract_id is 'Preenchido quando origin_type = transferred. Indica o contrato de origem.';


-- ============================================================
-- 6. AGENDA
-- ============================================================

-- horários recorrentes (grades da semana)
create table class_slots (
  id          uuid primary key default uuid_generate_v4(),
  weekday     int not null check (weekday between 0 and 6),  -- 0=dom, 6=sáb
  start_time  time not null,
  end_time    time not null,
  capacity    int not null check (capacity in (7, 8, 9)),    -- 9=normal, 8=quebrado, 7=sábado
  slot_type   slot_type not null default 'normal',
  active      boolean not null default true,
  created_at  timestamptz not null default now(),

  unique (weekday, start_time)
);

comment on column class_slots.capacity is '9 = horário normal | 8 = horário quebrado | 7 = sábado';
comment on column class_slots.weekday is '0=Domingo, 1=Segunda, 2=Terça, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sábado';

-- adicionar FK de fixed_slots após class_slots existir
alter table fixed_slots
  add constraint fixed_slots_class_slot_id_fkey
  foreign key (class_slot_id) references class_slots(id);


-- inscrições em aulas (ocorrência específica de uma data)
create table class_enrollments (
  id                    uuid primary key default uuid_generate_v4(),
  student_id            uuid not null references students(id),
  class_slot_id         uuid not null references class_slots(id),
  class_date            date not null,
  enrollment_type       enrollment_type not null,
  parent_enrollment_id  uuid references class_enrollments(id),  -- Origem da reposição
  reschedule_count      int not null default 0 check (reschedule_count in (0, 1)),
  status                enrollment_status not null default 'confirmed',
  checked_in_at         timestamptz,
  printed_at            timestamptz,                -- Controle de impressão do treino
  training_session_id   uuid,                       -- FK adicionada após criar training_sessions
  instructor_id         uuid references profiles(id),
  credit_ref_id         uuid references replacement_credits(id),
  created_at            timestamptz not null default now(),
  cancelled_at          timestamptz,

  unique (student_id, class_slot_id, class_date, status),

  constraint cancelled_has_timestamp check (
    (status = 'cancelled' and cancelled_at is not null) or
    (status != 'cancelled')
  )
);

comment on column class_enrollments.reschedule_count is 'Apenas para enrollment_type = original_flexible. 0 = pode remarcar, 1 = já remarcou (não pode mais).';
comment on column class_enrollments.printed_at is 'Preenchido quando o PDF do treino foi enviado para impressão. Evita reimpressão duplicada.';
comment on column class_enrollments.parent_enrollment_id is 'Para reposições: referência ao enrollment original que gerou esta reposição.';


-- lista de espera
create table waitlist (
  id                  uuid primary key default uuid_generate_v4(),
  student_id          uuid not null references students(id),
  class_slot_id       uuid not null references class_slots(id),
  class_date          date not null,
  status              waitlist_status not null default 'waiting',
  notification_count  int not null default 0,      -- Após 3 notificações sem ação → removido
  notified_at         timestamptz,
  created_at          timestamptz not null default now(),

  unique (student_id, class_slot_id, class_date)
);

comment on column waitlist.notification_count is 'Ao atingir 3 notificações sem resposta, aluno é removido automaticamente da fila.';


-- ============================================================
-- 7. CHECK-IN E PONTO
-- ============================================================

-- check-ins dos alunos (registrado pelo app)
create table student_checkins (
  id              uuid primary key default uuid_generate_v4(),
  student_id      uuid not null references students(id),
  enrollment_id   uuid not null references class_enrollments(id),
  checked_in_at   timestamptz not null default now(),
  class_date      date not null,
  class_slot_id   uuid not null references class_slots(id),

  unique (enrollment_id)   -- um check-in por enrollment
);

comment on table student_checkins is 'Validação: check-in só permitido se enrollment.status = confirmed para aquele slot + data.';


-- ponto eletrônico dos professores (QR Code)
create table instructor_timeclock (
  id              uuid primary key default uuid_generate_v4(),
  instructor_id   uuid not null references profiles(id),
  clock_in        timestamptz not null,
  clock_out       timestamptz,
  date            date not null,
  notes           text,
  created_at      timestamptz not null default now(),

  constraint clock_out_after_in check (
    clock_out is null or clock_out > clock_in
  )
);


-- ============================================================
-- 8. EXPERIMENTAIS (AULA EXPERIMENTAL)
-- ============================================================

create table experimentals (
  id                  uuid primary key default uuid_generate_v4(),
  lead_id             uuid not null references leads(id),
  scheduled_date      date not null unique,    -- MÁXIMO 1 EXPERIMENTAL POR DIA
  scheduled_time      time not null,
  status              experimental_status not null default 'scheduled',
  attended_at         timestamptz,
  converted_at        timestamptz,
  followup_24h_sent   boolean not null default false,
  followup_72h_sent   boolean not null default false,
  followup_7d_sent    boolean not null default false,
  created_by          uuid not null references profiles(id),
  notes               text,
  created_at          timestamptz not null default now()
);

comment on column experimentals.scheduled_date is 'UNIQUE — máximo 1 experimental por dia em todo o estúdio.';


-- ============================================================
-- 9. TREINOS
-- ============================================================

-- catálogo de exercícios
create table exercises (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null unique,
  muscle_group text,                    -- grupo muscular principal
  equipment   text,                    -- equipamento necessário
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);


-- programas de treino (por aluno)
create table training_programs (
  id          uuid primary key default uuid_generate_v4(),
  student_id  uuid not null references students(id),
  name        text not null,           -- Ex: Programa Hipertrofia Jan/2025
  created_by  uuid not null references profiles(id),  -- Somente coordinator ou admin
  active      boolean not null default true,
  notes       text,
  created_at  timestamptz not null default now()
);

-- adicionar FK de students.current_program_id após training_programs existir
alter table students
  add constraint students_current_program_id_fkey
  foreign key (current_program_id) references training_programs(id);


-- sessões de treino (sequência dentro do programa)
create table training_sessions (
  id          uuid primary key default uuid_generate_v4(),
  program_id  uuid not null references training_programs(id) on delete cascade,
  "order"     int not null,            -- posição na sequência: 1, 2, 3...
  name        text not null,           -- Ex: Treino A, Treino B
  notes       text,
  created_at  timestamptz not null default now(),

  unique (program_id, "order")
);

comment on column training_sessions."order" is 'Posição na sequência rotacional. Loop: ao atingir o último, volta ao 1.';

-- adicionar FK de class_enrollments.training_session_id
alter table class_enrollments
  add constraint class_enrollments_training_session_id_fkey
  foreign key (training_session_id) references training_sessions(id);


-- exercícios dentro de cada sessão
create table training_exercises (
  id            uuid primary key default uuid_generate_v4(),
  session_id    uuid not null references training_sessions(id) on delete cascade,
  exercise_id   uuid not null references exercises(id),
  sets          int not null check (sets > 0),
  reps          text not null,         -- Ex: '12' ou '10-12' ou '5 minutos'
  rest_seconds  int,
  "order"       int not null,          -- ordem dentro do treino
  observation   text,
  created_at    timestamptz not null default now(),

  unique (session_id, "order")
);


-- log de aulas realizadas
create table workout_logs (
  id                    uuid primary key default uuid_generate_v4(),
  student_id            uuid not null references students(id),
  enrollment_id         uuid not null references class_enrollments(id) unique,
  training_session_id   uuid not null references training_sessions(id),
  instructor_id         uuid not null references profiles(id),
  class_date            date not null,
  confirmed_at          timestamptz not null default now(),
  notes                 text
);

comment on table workout_logs is 'Criado pelo professor ao confirmar a aula. Dispara avanço de next_training_session no student.';


-- cargas registradas por exercício em cada aula
create table exercise_logs (
  id                      uuid primary key default uuid_generate_v4(),
  workout_log_id          uuid not null references workout_logs(id) on delete cascade,
  exercise_id             uuid not null references exercises(id),
  weight_kg               numeric(6,2),
  sets_done               int,
  reps_done               text,
  changed_from_previous   boolean not null default false,  -- true = houve alteração de carga
  notes                   text,
  created_at              timestamptz not null default now()
);

comment on column exercise_logs.changed_from_previous is 'true = professor alterou a carga em relação à última registrada.';


-- histórico de última carga por aluno/exercício (tabela de leitura rápida)
create table exercise_history (
  id                uuid primary key default uuid_generate_v4(),
  student_id        uuid not null references students(id),
  exercise_id       uuid not null references exercises(id),
  last_weight_kg    numeric(6,2),
  last_recorded_at  timestamptz not null default now(),
  workout_log_id    uuid not null references workout_logs(id),

  unique (student_id, exercise_id)
);

comment on table exercise_history is 'Uma linha por aluno/exercício. Atualizada a cada alteração de carga. Usada para exibição no app do professor e PDF de treino.';


-- exercícios bloqueados por aluno (restrições médicas)
create table blocked_exercises (
  id            uuid primary key default uuid_generate_v4(),
  student_id    uuid not null references students(id),
  exercise_id   uuid not null references exercises(id),
  reason        text not null,
  blocked_at    date not null default current_date,
  active        boolean not null default true,
  created_at    timestamptz not null default now(),

  unique (student_id, exercise_id)
);


-- solicitações de troca de exercício
create table exercise_change_requests (
  id                      uuid primary key default uuid_generate_v4(),
  student_id              uuid not null references students(id),
  training_exercise_id    uuid not null references training_exercises(id),
  suggested_exercise_id   uuid not null references exercises(id),
  reason                  text not null,
  status                  change_request_status not null default 'pending',
  requested_by            uuid not null references profiles(id),  -- professor solicitante
  reviewed_by             uuid references profiles(id),           -- coordenador que analisou
  reviewed_at             timestamptz,
  created_at              timestamptz not null default now()
);


-- ============================================================
-- 10. AVALIAÇÃO FÍSICA
-- ============================================================

create table physical_assessments (
  id            uuid primary key default uuid_generate_v4(),
  student_id    uuid not null references students(id),
  assessed_at   date not null,
  weight_kg     numeric(5,2),
  body_fat_pct  numeric(5,2),
  lean_mass_kg  numeric(5,2),
  chest_cm      numeric(5,1),
  waist_cm      numeric(5,1),
  hip_cm        numeric(5,1),
  arm_cm        numeric(5,1),
  thigh_cm      numeric(5,1),
  photo_urls    text[],                  -- URLs no Supabase Storage
  notes         text,
  assessed_by   uuid not null references profiles(id),   -- coordinator ou admin
  created_at    timestamptz not null default now()
);

comment on table physical_assessments is 'Aluno vê dados e gráficos no app, mas não pode editar nem interagir.';


-- ============================================================
-- 11. FINANCEIRO
-- ============================================================

create table payments (
  id              uuid primary key default uuid_generate_v4(),
  student_id      uuid not null references students(id),
  contract_id     uuid not null references contracts(id),
  amount          numeric(10,2) not null check (amount > 0),
  type            payment_type_item not null,
  status          payment_status not null default 'pending',
  payment_method  text,                  -- 'pix' | 'credit_card' | 'link'
  gateway_id      text,                  -- ID na operadora
  paid_at         timestamptz,
  due_date        date not null,
  created_at      timestamptz not null default now()
);

comment on column payments.gateway_id is 'ID do pagamento no gateway externo para reconciliação.';


-- ============================================================
-- 12. NOTIFICAÇÕES
-- ============================================================

create table notification_logs (
  id          uuid primary key default uuid_generate_v4(),
  student_id  uuid references students(id),
  lead_id     uuid references leads(id),
  event       notification_event not null,
  channel     notification_channel not null,
  payload     jsonb,                     -- corpo da mensagem enviada
  sent_at     timestamptz not null default now(),
  success     boolean not null default true,
  error_msg   text
);

comment on table notification_logs is 'Log de todas as notificações enviadas (WhatsApp Z-API + Push Expo/Firebase).';


-- ============================================================
-- 13. ÍNDICES
-- ============================================================

-- profiles
create index idx_profiles_role on profiles(role);
create index idx_profiles_active on profiles(active);

-- students
create index idx_students_matricula on students(matricula);
create index idx_students_current_program on students(current_program_id);
create index idx_students_blocked on students(blocked);

-- contracts
create index idx_contracts_student on contracts(student_id);
create index idx_contracts_status on contracts(status);
create index idx_contracts_end_date on contracts(end_date);
create index idx_contracts_due_date on contracts(due_date);

-- replacement_credits
create index idx_replacement_credits_student on replacement_credits(student_id);
create index idx_replacement_credits_contract on replacement_credits(contract_id);
create index idx_replacement_credits_active on replacement_credits(active, quantity_remaining);

-- class_slots
create index idx_class_slots_weekday on class_slots(weekday);
create index idx_class_slots_active on class_slots(active);

-- class_enrollments
create index idx_enrollments_student on class_enrollments(student_id);
create index idx_enrollments_slot_date on class_enrollments(class_slot_id, class_date);
create index idx_enrollments_status on class_enrollments(status);
create index idx_enrollments_printed_at on class_enrollments(printed_at) where printed_at is null;
create index idx_enrollments_date on class_enrollments(class_date);

-- fixed_slots
create index idx_fixed_slots_student on fixed_slots(student_id);
create index idx_fixed_slots_contract on fixed_slots(contract_id);
create index idx_fixed_slots_active on fixed_slots(active);

-- waitlist
create index idx_waitlist_slot_date on waitlist(class_slot_id, class_date);
create index idx_waitlist_student on waitlist(student_id);
create index idx_waitlist_status on waitlist(status);

-- workout_logs
create index idx_workout_logs_student on workout_logs(student_id);
create index idx_workout_logs_date on workout_logs(class_date);
create index idx_workout_logs_session on workout_logs(training_session_id);

-- exercise_history
create index idx_exercise_history_student on exercise_history(student_id);

-- exercise_change_requests
create index idx_change_requests_status on exercise_change_requests(status);

-- payments
create index idx_payments_student on payments(student_id);
create index idx_payments_contract on payments(contract_id);
create index idx_payments_status on payments(status);
create index idx_payments_due_date on payments(due_date);

-- notification_logs
create index idx_notifications_student on notification_logs(student_id);
create index idx_notifications_event on notification_logs(event);

-- physical_assessments
create index idx_assessments_student on physical_assessments(student_id);
create index idx_assessments_date on physical_assessments(assessed_at);

-- instructor_timeclock
create index idx_timeclock_instructor on instructor_timeclock(instructor_id);
create index idx_timeclock_date on instructor_timeclock(date);


-- ============================================================
-- 14. ROW LEVEL SECURITY (RLS)
-- ============================================================

alter table profiles enable row level security;
alter table students enable row level security;
alter table leads enable row level security;
alter table plans enable row level security;
alter table contracts enable row level security;
alter table fixed_slots enable row level security;
alter table replacement_credits enable row level security;
alter table class_slots enable row level security;
alter table class_enrollments enable row level security;
alter table waitlist enable row level security;
alter table student_checkins enable row level security;
alter table instructor_timeclock enable row level security;
alter table experimentals enable row level security;
alter table exercises enable row level security;
alter table training_programs enable row level security;
alter table training_sessions enable row level security;
alter table training_exercises enable row level security;
alter table workout_logs enable row level security;
alter table exercise_logs enable row level security;
alter table exercise_history enable row level security;
alter table blocked_exercises enable row level security;
alter table exercise_change_requests enable row level security;
alter table physical_assessments enable row level security;
alter table payments enable row level security;
alter table notification_logs enable row level security;
alter table physical_assessments enable row level security;


-- helper: retorna o role do usuário logado
create or replace function auth_role()
returns user_role
language sql stable
as $$
  select role from profiles where id = auth.uid()
$$;


-- ── PROFILES ────────────────────────────────────────────────

-- todos veem o próprio perfil; admin/coordinator/receptionist veem todos
create policy "profiles: leitura" on profiles
  for select using (
    id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist')
  );

create policy "profiles: admin gerencia" on profiles
  for all using (auth_role() = 'admin');

create policy "profiles: self update" on profiles
  for update using (id = auth.uid());


-- ── STUDENTS ────────────────────────────────────────────────

create policy "students: leitura interna" on students
  for select using (
    id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist', 'teacher')
  );

create policy "students: admin/receptionist escrita" on students
  for all using (auth_role() in ('admin', 'receptionist'));


-- ── LEADS ───────────────────────────────────────────────────

create policy "leads: admin/receptionist/coordinator" on leads
  for all using (auth_role() in ('admin', 'receptionist', 'coordinator'));


-- ── PLANS ───────────────────────────────────────────────────

create policy "plans: todos leem" on plans
  for select using (true);

create policy "plans: admin escreve" on plans
  for all using (auth_role() = 'admin');


-- ── CONTRACTS ───────────────────────────────────────────────

create policy "contracts: aluno vê o próprio" on contracts
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist')
  );

create policy "contracts: admin/receptionist escrita" on contracts
  for all using (auth_role() in ('admin', 'receptionist'));


-- ── REPLACEMENT_CREDITS ─────────────────────────────────────

create policy "replacement_credits: aluno vê o próprio" on replacement_credits
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist')
  );

create policy "replacement_credits: admin/receptionist escrita" on replacement_credits
  for all using (auth_role() in ('admin', 'receptionist'));


-- ── CLASS_SLOTS ─────────────────────────────────────────────

create policy "class_slots: todos leem" on class_slots
  for select using (true);

create policy "class_slots: admin escreve" on class_slots
  for all using (auth_role() = 'admin');


-- ── CLASS_ENROLLMENTS ───────────────────────────────────────

create policy "enrollments: aluno vê o próprio" on class_enrollments
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist', 'teacher')
  );

create policy "enrollments: aluno cria o próprio" on class_enrollments
  for insert with check (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist')
  );

create policy "enrollments: admin/receptionist/teacher escrita" on class_enrollments
  for update using (auth_role() in ('admin', 'receptionist', 'teacher'));

create policy "enrollments: admin/receptionist deleta" on class_enrollments
  for delete using (auth_role() in ('admin', 'receptionist'));


-- ── FIXED_SLOTS ─────────────────────────────────────────────

create policy "fixed_slots: leitura interna" on fixed_slots
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'coordinator', 'receptionist')
  );

create policy "fixed_slots: admin/receptionist escrita" on fixed_slots
  for all using (auth_role() in ('admin', 'receptionist'));


-- ── WAITLIST ────────────────────────────────────────────────

create policy "waitlist: aluno vê o próprio" on waitlist
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist', 'coordinator')
  );

create policy "waitlist: aluno gerencia o próprio" on waitlist
  for all using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist')
  );


-- ── STUDENT_CHECKINS ────────────────────────────────────────

create policy "checkins: aluno vê o próprio" on student_checkins
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist', 'teacher')
  );

create policy "checkins: aluno cria o próprio" on student_checkins
  for insert with check (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist')
  );


-- ── INSTRUCTOR_TIMECLOCK ─────────────────────────────────────

create policy "timeclock: professor vê o próprio" on instructor_timeclock
  for select using (
    instructor_id = auth.uid() or
    auth_role() in ('admin', 'coordinator')
  );

create policy "timeclock: professor registra o próprio" on instructor_timeclock
  for insert with check (
    instructor_id = auth.uid() or
    auth_role() = 'admin'
  );

create policy "timeclock: admin edita" on instructor_timeclock
  for update using (auth_role() = 'admin');


-- ── EXPERIMENTALS ───────────────────────────────────────────

create policy "experimentals: admin/receptionist/coordinator" on experimentals
  for all using (auth_role() in ('admin', 'receptionist', 'coordinator'));


-- ── EXERCISES ───────────────────────────────────────────────

create policy "exercises: todos leem" on exercises
  for select using (true);

create policy "exercises: admin/coordinator escrita" on exercises
  for all using (auth_role() in ('admin', 'coordinator'));


-- ── TRAINING_PROGRAMS ───────────────────────────────────────

create policy "training_programs: coordinator/admin lê e escreve" on training_programs
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "training_programs: teacher lê" on training_programs
  for select using (auth_role() = 'teacher');

-- aluno NÃO tem acesso ao treino


-- ── TRAINING_SESSIONS ───────────────────────────────────────

create policy "training_sessions: coordinator/admin" on training_sessions
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "training_sessions: teacher lê" on training_sessions
  for select using (auth_role() = 'teacher');


-- ── TRAINING_EXERCISES ──────────────────────────────────────

create policy "training_exercises: coordinator/admin" on training_exercises
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "training_exercises: teacher lê" on training_exercises
  for select using (auth_role() = 'teacher');


-- ── WORKOUT_LOGS ────────────────────────────────────────────

create policy "workout_logs: teacher cria" on workout_logs
  for insert with check (
    instructor_id = auth.uid() or
    auth_role() = 'admin'
  );

create policy "workout_logs: teacher/admin/coordinator lê" on workout_logs
  for select using (auth_role() in ('admin', 'coordinator', 'teacher'));


-- ── EXERCISE_LOGS ───────────────────────────────────────────

create policy "exercise_logs: teacher/admin" on exercise_logs
  for all using (auth_role() in ('admin', 'teacher'));

create policy "exercise_logs: coordinator lê" on exercise_logs
  for select using (auth_role() = 'coordinator');


-- ── EXERCISE_HISTORY ────────────────────────────────────────

create policy "exercise_history: teacher/admin/coordinator" on exercise_history
  for all using (auth_role() in ('admin', 'coordinator', 'teacher'));


-- ── BLOCKED_EXERCISES ───────────────────────────────────────

create policy "blocked_exercises: coordinator/admin" on blocked_exercises
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "blocked_exercises: teacher lê" on blocked_exercises
  for select using (auth_role() = 'teacher');


-- ── EXERCISE_CHANGE_REQUESTS ────────────────────────────────

create policy "change_requests: teacher cria" on exercise_change_requests
  for insert with check (
    requested_by = auth.uid() or
    auth_role() = 'admin'
  );

create policy "change_requests: coordinator/admin lê e atualiza" on exercise_change_requests
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "change_requests: teacher lê o próprio" on exercise_change_requests
  for select using (
    requested_by = auth.uid() or
    auth_role() in ('admin', 'coordinator')
  );


-- ── PHYSICAL_ASSESSMENTS ────────────────────────────────────

create policy "assessments: coordinator/admin escrita" on physical_assessments
  for all using (auth_role() in ('admin', 'coordinator'));

create policy "assessments: aluno lê o próprio" on physical_assessments
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'coordinator')
  );


-- ── PAYMENTS ────────────────────────────────────────────────

create policy "payments: admin lê tudo" on payments
  for all using (auth_role() = 'admin');

create policy "payments: aluno lê o próprio" on payments
  for select using (
    student_id = auth.uid() or
    auth_role() in ('admin', 'receptionist')
  );

-- receptionist vê apenas status (não valores detalhados — aplicado no backend)


-- ── NOTIFICATION_LOGS ───────────────────────────────────────

create policy "notifications: admin lê tudo" on notification_logs
  for all using (auth_role() = 'admin');


-- ============================================================
-- 15. FUNÇÕES AUXILIARES
-- ============================================================

-- Avança next_training_session do aluno em loop após aula confirmada
create or replace function advance_training_session(p_student_id uuid)
returns void
language plpgsql
as $$
declare
  v_current     int;
  v_program_id  uuid;
  v_total       int;
begin
  select next_training_session, current_program_id
  into   v_current, v_program_id
  from   students
  where  id = p_student_id;

  if v_program_id is null then return; end if;

  select count(*) into v_total
  from   training_sessions
  where  program_id = v_program_id;

  if v_total = 0 then return; end if;

  -- Loop: ao chegar no último, volta para 1
  update students
  set    next_training_session = (v_current % v_total) + 1
  where  id = p_student_id;
end;
$$;

comment on function advance_training_session is 'Chamada após criação de workout_log com presença confirmada. Falta NÃO avança a sequência.';


-- Calcula saldo de reposições disponíveis para um aluno/contrato
create or replace function available_replacements(p_student_id uuid, p_contract_id uuid)
returns int
language sql stable
as $$
  select coalesce(sum(quantity_remaining), 0)::int
  from   replacement_credits
  where  student_id = p_student_id
  and    contract_id = p_contract_id
  and    active = true
  and    quantity_remaining > 0
  and    (expires_at is null or expires_at > now())
$$;


-- Verifica se aluno está inadimplente (passou do grace_period_end)
create or replace function is_delinquent(p_student_id uuid)
returns boolean
language sql stable
as $$
  select exists (
    select 1
    from   contracts c
    where  c.student_id = p_student_id
    and    c.status = 'active'
    and    c.grace_period_end < current_date
  )
$$;


-- Trigger: atualiza updated_at automaticamente
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger trg_contracts_updated_at
  before update on contracts
  for each row execute function set_updated_at();

create trigger trg_leads_updated_at
  before update on leads
  for each row execute function set_updated_at();


-- ============================================================
-- 16. DADOS INICIAIS (SEED)
-- ============================================================

-- Horários da semana (conforme operação atual do Estúdio Se7e)
insert into class_slots (weekday, start_time, end_time, capacity, slot_type) values
  -- Segunda a Sexta — manhã
  (1, '06:00', '07:00', 9, 'normal'),
  (1, '06:30', '07:30', 8, 'normal'),
  (1, '07:00', '08:00', 9, 'normal'),
  (1, '07:30', '08:30', 8, 'normal'),
  (1, '08:00', '09:00', 9, 'normal'),
  (1, '09:00', '10:00', 9, 'normal'),
  (1, '10:00', '11:00', 9, 'normal'),
  (1, '11:00', '12:00', 9, 'normal'),
  -- Segunda a Sexta — tarde/noite
  (1, '15:00', '16:00', 9, 'normal'),
  (1, '16:00', '17:00', 9, 'normal'),
  (1, '17:00', '18:00', 9, 'normal'),
  (1, '17:30', '18:30', 8, 'normal'),
  (1, '18:00', '19:00', 9, 'normal'),
  (1, '18:30', '19:30', 8, 'normal'),
  (1, '19:00', '20:00', 9, 'normal'),
  (1, '19:30', '20:30', 8, 'normal'),
  (1, '20:00', '21:00', 9, 'normal'),
  (1, '20:30', '21:30', 8, 'normal'),
  -- Sábado
  (6, '09:05', '09:55', 7, 'saturday'),
  (6, '09:55', '10:30', 7, 'saturday'),
  (6, '10:35', '11:15', 7, 'saturday'),
  (6, '11:20', '12:00', 7, 'saturday');

-- NOTA: Os horários de Terça (2), Quarta (3), Quinta (4) e Sexta (5)
-- devem ser inseridos com os mesmos padrões de Segunda (1).
-- Omitidos aqui por brevidade — replicar para weekday 2, 3, 4 e 5.


-- Planos padrão
insert into plans (name, frequency_per_week, monthly_price, recurring_price, annual_price, renewal_price, annual_classes) values
  ('Plano 1x Semanal',  1, null, null, null, null, 54),
  ('Plano 2x Semanal',  2, null, null, null, null, 108),
  ('Plano 3x Semanal',  3, null, null, null, null, 162),
  ('Plano 4x Semanal',  4, null, null, null, null, 216),
  ('Plano 5x Semanal',  5, null, null, null, null, 270);

-- NOTA: Preencher os valores de preço conforme tabela vigente do Estúdio Se7e.


-- ============================================================
-- FIM DO SCHEMA
-- ============================================================
-- Próximos passos:
-- 1. Executar este script no Supabase SQL Editor
-- 2. Configurar Supabase Auth (email/password + magic link)
-- 3. Criar Storage bucket 'physical-assessments' para fotos
-- 4. Configurar pg_cron para jobs de impressão e follow-ups
-- 5. Iniciar migração de dados do Bubble/Tecnofit
-- ============================================================
