-- Migration: rodizio e capacidade override
-- Data: 2026-03-13

create type shift_type as enum ('morning', 'evening');
create type slot_group as enum ('full', 'split');

create table instructor_schedules (
  id             uuid primary key default uuid_generate_v4(),
  instructor_id  uuid not null references profiles(id),
  date           date not null,
  shift          shift_type not null,
  slot_group     slot_group not null,
  priority_order int not null,
  present        boolean not null default true,
  created_by     uuid not null references profiles(id),
  created_at     timestamptz not null default now(),
  unique (instructor_id, date, shift, slot_group)
);

create table class_slot_overrides (
  id            uuid primary key default uuid_generate_v4(),
  class_slot_id uuid not null references class_slots(id),
  date          date not null,
  capacity      int not null check (capacity between 1 and 9),
  reason        text,
  created_by    uuid not null references profiles(id),
  created_at    timestamptz not null default now(),
  unique (class_slot_id, date)
);

create index idx_schedules_date_shift on instructor_schedules(date, shift, slot_group);
create index idx_schedules_instructor on instructor_schedules(instructor_id);
create index idx_overrides_date on class_slot_overrides(date);

alter table instructor_schedules enable row level security;
alter table class_slot_overrides enable row level security;

create or replace function get_next_instructor(
  p_date      date,
  p_shift     shift_type,
  p_slot_group slot_group
)
returns uuid language sql stable as $$
  select s.instructor_id
  from instructor_schedules s
  left join (
    select wl.instructor_id, count(*) as aulas_hoje
    from workout_logs wl
    where wl.class_date = p_date
    group by wl.instructor_id
  ) wl on wl.instructor_id = s.instructor_id
  where s.date = p_date and s.shift = p_shift
    and s.slot_group = p_slot_group and s.present = true
  order by coalesce(wl.aulas_hoje, 0) asc, s.priority_order asc
  limit 1;
$$;
