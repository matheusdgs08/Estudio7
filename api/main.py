from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import os, httpx, json
from pydantic import BaseModel

# ── Config ──
SUPABASE_URL  = os.getenv("SUPABASE_URL",  "https://kfmkcbhalwupgknysukj.supabase.co")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY",  "")   # service_role key via env var
API_SECRET    = os.getenv("API_SECRET",    "")   # shared secret entre frontend ↔ api

app = FastAPI(title="Estúdio Se7e API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Supabase client helper ──
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

async def sb_get(table: str, params: str = "") -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers=SB_HEADERS, timeout=20
        )
        r.raise_for_status()
        return r.json()

async def sb_post(table: str, data: dict | list) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS, json=data, timeout=20
        )
        r.raise_for_status()
        return r.json()

async def sb_patch(table: str, params: str, data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers=SB_HEADERS, json=data, timeout=20
        )
        r.raise_for_status()
        return r.json()

async def sb_delete(table: str, params: str):
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers={**SB_HEADERS, "Prefer": "return=minimal"}, timeout=20
        )
        r.raise_for_status()

# ── Auth dependency ──
def check_api_key(x_api_key: str = Header(default="")):
    if API_SECRET and x_api_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ── Health ──
@app.get("/")
async def root():
    return {"status": "ok", "service": "Estúdio Se7e API"}

@app.get("/health")
async def health():
    try:
        data = await sb_get("profiles", "limit=1&select=id")
        return {"status": "ok", "supabase": "connected", "profiles": len(data)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ════════════════════════════════════════
# ALUNOS
# ════════════════════════════════════════

@app.get("/alunos")
async def list_alunos(_=Depends(check_api_key)):
    """Lista todos os alunos com dados do perfil + programa atual"""
    profiles = await sb_get("profiles", "role=eq.student&active=eq.true&select=id,full_name,phone&order=full_name")
    students  = await sb_get("students", "select=id,next_training_session,current_program_id,blocked,blocked_reason")
    # Merge
    students_map = {s["id"]: s for s in students}
    result = []
    for p in profiles:
        s = students_map.get(p["id"], {})
        result.append({**p, **s})
    return result

@app.get("/alunos/{student_id}")
async def get_aluno(student_id: str, _=Depends(check_api_key)):
    profiles = await sb_get("profiles", f"id=eq.{student_id}&select=id,full_name,phone,role")
    if not profiles:
        raise HTTPException(404, "Aluno não encontrado")
    students = await sb_get("students", f"id=eq.{student_id}")
    s = students[0] if students else {}
    return {**profiles[0], **s}

# ════════════════════════════════════════
# EXERCÍCIOS
# ════════════════════════════════════════

@app.get("/exercises")
async def list_exercises(_=Depends(check_api_key)):
    data = await sb_get("exercises", "select=id,name,muscle_group&order=muscle_group,name&limit=1000")
    return data

class ExerciseCreate(BaseModel):
    name: str
    muscle_group: str

@app.post("/exercises")
async def create_exercise(ex: ExerciseCreate, _=Depends(check_api_key)):
    # Check duplicate
    existing = await sb_get("exercises", f"name=eq.{ex.name}&select=id")
    if existing:
        raise HTTPException(400, "Exercício já existe")
    data = await sb_post("exercises", {"name": ex.name.upper(), "muscle_group": ex.muscle_group.upper()})
    return data

@app.delete("/exercises/{exercise_id}")
async def delete_exercise(exercise_id: str, _=Depends(check_api_key)):
    await sb_delete("exercises", f"id=eq.{exercise_id}")
    return {"deleted": exercise_id}

# ════════════════════════════════════════
# PROGRAMAS DE TREINO
# ════════════════════════════════════════

@app.get("/alunos/{student_id}/programas")
async def get_programas(student_id: str, _=Depends(check_api_key)):
    progs = await sb_get("training_programs",
        f"student_id=eq.{student_id}&select=id,name,active,created_at,notes&order=created_at.desc")
    return progs

@app.get("/programas/{program_id}/fichas")
async def get_fichas(program_id: str, _=Depends(check_api_key)):
    """Retorna todas as sessões/fichas de um programa com exercícios"""
    sessions = await sb_get("training_sessions",
        f"program_id=eq.{program_id}&select=id,order,name,notes&order=order")
    if not sessions:
        return []
    session_ids = ",".join(s["id"] for s in sessions)
    exercises = await sb_get("training_exercises",
        f"session_id=in.({session_ids})&select=id,session_id,exercise_id,sets,reps,rest_seconds,order,observation&order=order")
    # Get exercise names
    if exercises:
        ex_ids = ",".join({e["exercise_id"] for e in exercises})
        ex_data = await sb_get("exercises", f"id=in.({ex_ids})&select=id,name,muscle_group")
        ex_map = {e["id"]: e for e in ex_data}
    else:
        ex_map = {}
    # Build response
    result = []
    for s in sessions:
        s_exs = [e for e in exercises if e["session_id"] == s["id"]]
        for e in s_exs:
            e["exercise_name"] = ex_map.get(e["exercise_id"], {}).get("name", "")
            e["muscle_group"]  = ex_map.get(e["exercise_id"], {}).get("muscle_group", "")
        result.append({**s, "exercises": s_exs})
    return result

class SessionCreate(BaseModel):
    program_id: str
    name: str
    order: int
    notes: Optional[str] = None

@app.post("/programas/{program_id}/fichas")
async def create_ficha(program_id: str, body: SessionCreate, _=Depends(check_api_key)):
    data = await sb_post("training_sessions", {
        "program_id": program_id,
        "name": body.name,
        "order": body.order,
        "notes": body.notes
    })
    return data

class ExerciseInSession(BaseModel):
    exercise_id: str
    sets: int
    reps: str
    rest_seconds: Optional[int] = 60
    order: int
    observation: Optional[str] = None

@app.post("/fichas/{session_id}/exercicios")
async def add_exercise_to_ficha(session_id: str, body: ExerciseInSession, _=Depends(check_api_key)):
    data = await sb_post("training_exercises", {
        "session_id": session_id,
        "exercise_id": body.exercise_id,
        "sets": body.sets,
        "reps": body.reps,
        "rest_seconds": body.rest_seconds,
        "order": body.order,
        "observation": body.observation
    })
    return data

@app.delete("/fichas/exercicios/{training_exercise_id}")
async def remove_exercise_from_ficha(training_exercise_id: str, _=Depends(check_api_key)):
    await sb_delete("training_exercises", f"id=eq.{training_exercise_id}")
    return {"deleted": training_exercise_id}

# ════════════════════════════════════════
# SAVE PROGRAMA COMPLETO (batch)
# usado pelo painel Vanessa ao salvar fichas
# ════════════════════════════════════════

class FichaExercicio(BaseModel):
    exercise_name: str
    muscle_group: Optional[str] = ""
    sets: int = 3
    reps: str = "12"
    rest_seconds: int = 60
    observation: Optional[str] = ""
    metodologia: Optional[str] = "Individual"  # Individual | Dupla | Trio
    carga_ref: Optional[float] = None

class FichaData(BaseModel):
    letra: str
    nome: str
    nota: Optional[str] = ""
    exercicios: List[FichaExercicio]

class SaveProgramaBody(BaseModel):
    student_id: str
    programa_nome: str
    fichas: List[FichaData]

@app.post("/programas/salvar")
async def save_programa(body: SaveProgramaBody, _=Depends(check_api_key)):
    """Cria ou substitui o programa ativo de um aluno com todas as fichas"""
    # 1. Cria programa
    prog = await sb_post("training_programs", {
        "student_id": body.student_id,
        "name": body.programa_nome,
        "active": True,
        "notes": ""
    })
    if isinstance(prog, list): prog = prog[0]
    prog_id = prog["id"]

    # 2. Para cada ficha, cria sessão + exercícios
    for i, ficha in enumerate(body.fichas):
        sess = await sb_post("training_sessions", {
            "program_id": prog_id,
            "order": i + 1,
            "name": f"Treino {ficha.letra}",
            "notes": ficha.nota or ""
        })
        if isinstance(sess, list): sess = sess[0]
        sess_id = sess["id"]

        for j, ex in enumerate(ficha.exercicios):
            # Find exercise by name
            ex_rows = await sb_get("exercises", f"name=eq.{ex.exercise_name.replace(' ', '%20')}&select=id")
            if ex_rows:
                ex_id = ex_rows[0]["id"]
            else:
                # Create new exercise
                new_ex = await sb_post("exercises", {
                    "name": ex.exercise_name.upper(),
                    "muscle_group": (ex.muscle_group or "").upper()
                })
                if isinstance(new_ex, list): new_ex = new_ex[0]
                ex_id = new_ex["id"]

            await sb_post("training_exercises", {
                "session_id": sess_id,
                "exercise_id": ex_id,
                "sets": ex.sets,
                "reps": ex.reps,
                "rest_seconds": ex.rest_seconds,
                "order": j + 1,
                "observation": ex.observation or ""
            })

    # 3. Atualiza current_program_id do aluno
    await sb_patch("students", f"id=eq.{body.student_id}",
                   {"current_program_id": prog_id})

    return {"ok": True, "program_id": prog_id, "fichas": len(body.fichas)}

# ════════════════════════════════════════
# AVALIAÇÕES FÍSICAS
# ════════════════════════════════════════

@app.get("/alunos/{student_id}/avaliacoes")
async def get_avaliacoes(student_id: str, _=Depends(check_api_key)):
    data = await sb_get("physical_assessments",
        f"student_id=eq.{student_id}&order=assessed_at.desc")
    return data

class AvaliacaoCreate(BaseModel):
    student_id: str
    assessed_at: str
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    lean_mass_kg: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    arm_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    notes: Optional[str] = None

@app.post("/avaliacoes")
async def create_avaliacao(body: AvaliacaoCreate, _=Depends(check_api_key)):
    data = await sb_post("physical_assessments", body.model_dump(exclude_none=True))
    return data

# ══════════════════════════════════════════════════════
# QUESTIONÁRIOS
# ══════════════════════════════════════════════════════

class QuestToken(BaseModel):
    token: str
    aluno_id: str = ""
    aluno_nm: str
    aluno_phone: str = ""
    tipo: str  # 'entrada' | 'mudanca'

class QuestResposta(BaseModel):
    token: str
    tipo: str = ""
    freq: str = ""
    objetivo: str = ""
    treino_atual: str = ""
    novo_treino: str = ""
    prioridade: str = ""
    regioes: list = []
    patologias: dict = {}
    prob_saude: list = []
    dor: str = ""
    dor_local: str = ""
    med: str = ""
    med_nome: str = ""
    obs: str = ""

# ── Criar token (painel admin) ──
@app.post("/quest/tokens")
async def criar_token(body: QuestToken, _=Depends(check_api_key)):
    data = await sb_post("quest_tokens", body.model_dump())
    return data

# ── Listar tokens (painel admin) ──
@app.get("/quest/tokens")
async def listar_tokens(_=Depends(check_api_key)):
    return await sb_get("quest_tokens", "order=criado_em.desc")

# ── Marcar token como visto (painel admin) ──
@app.patch("/quest/tokens/{token}")
async def marcar_visto(token: str, _=Depends(check_api_key)):
    return await sb_patch("quest_tokens", f"token=eq.{token}", {"visto": True, "status": "respondido"})

# ── Listar respostas (painel admin) ──
@app.get("/quest/respostas")
async def listar_respostas(_=Depends(check_api_key)):
    return await sb_get("quest_respostas", "order=respondido_em.desc")

# ── Salvar resposta (aluno — sem autenticação) ──
@app.post("/quest/responder")
async def salvar_resposta(body: QuestResposta):
    # Verify token exists
    tokens = await sb_get("quest_tokens", f"token=eq.{body.token}")
    if not tokens:
        raise HTTPException(status_code=404, detail="Token inválido ou expirado")
    # Upsert resposta
    data = body.model_dump()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/quest_respostas",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
            json=data
        )
    # Mark token as respondido
    await sb_patch("quest_tokens", f"token=eq.{body.token}", {"status": "respondido"})
    return {"ok": True}


# ════════════════════════════════════════
# RELATÓRIO DE AULA — Professor confirma presença
# Fluxo: professor fecha aula → cria workout_log →
#   enrollment.status = attended
#   next_training_session + 1 (loop ao terminar ciclo)
#   treinos_realizados + 1 (contador para vencimento)
#   exercise_history atualizado para cada carga alterada
# ════════════════════════════════════════

class CargaLog(BaseModel):
    exercise_id: str
    weight_kg: float
    sets_done: int
    reps_done: str
    changed_from_previous: bool = True
    notes: Optional[str] = None

class ConfirmarAulaBody(BaseModel):
    enrollment_id: str          # class_enrollment sendo confirmado
    student_id: str
    training_session_id: str    # ficha executada (A, B, C ou D)
    instructor_id: str
    class_date: str             # YYYY-MM-DD
    presentes: List[str]        # lista de student_ids presentes
    ausentes: List[str]         # lista de student_ids ausentes
    cargas: List[CargaLog] = [] # cargas alteradas nesta aula
    notes: Optional[str] = None

@app.post("/aulas/confirmar")
async def confirmar_aula(body: ConfirmarAulaBody, _=Depends(check_api_key)):
    """
    Professor confirma o relatório de aula.
    Para cada aluno presente:
      - enrollment.status = 'attended'
      - students.next_training_session avança (loop)
      - students.treinos_realizados + 1
    Para cada aluno ausente:
      - enrollment.status = 'missed'
      - next_training_session NÃO avança
    Para cargas alteradas:
      - cria exercise_log
      - atualiza exercise_history (upsert)
    Cria workout_log para o professor.
    """
    results = {"presentes": [], "ausentes": [], "workout_log_id": None}

    # 1. Criar workout_log
    wlog_data = {
        "student_id":          body.student_id,
        "enrollment_id":       body.enrollment_id,
        "training_session_id": body.training_session_id,
        "instructor_id":       body.instructor_id,
        "class_date":          body.class_date,
        "notes":               body.notes,
    }
    wlog = await sb_post("workout_logs", wlog_data)
    if isinstance(wlog, list): wlog = wlog[0]
    wlog_id = wlog.get("id")
    results["workout_log_id"] = wlog_id

    # 2. Processar alunos presentes
    for sid in body.presentes:
        try:
            # a. Marcar enrollment como attended
            await sb_patch(
                "class_enrollments",
                f"student_id=eq.{sid}&class_date=eq.{body.class_date}&status=eq.confirmed",
                {"status": "attended", "checked_in_at": "now()"}
            )

            # b. Buscar dados atuais do aluno
            student_rows = await sb_get("students",
                f"id=eq.{sid}&select=id,next_training_session,treinos_realizados,current_program_id")
            if not student_rows:
                continue
            st = student_rows[0]

            # c. Contar quantas fichas tem o programa atual (para o loop)
            n_fichas = 4  # default
            if st.get("current_program_id"):
                fichas = await sb_get("training_sessions",
                    f"program_id=eq.{st['current_program_id']}&select=id")
                n_fichas = len(fichas) or 4

            # d. Avançar next_training_session (loop ao terminar)
            cur = st.get("next_training_session", 1) or 1
            next_ts = (cur % n_fichas) + 1   # ex: 4 fichas → 1→2→3→4→1

            # e. Incrementar treinos_realizados
            cur_realizados = st.get("treinos_realizados") or 0
            new_realizados = cur_realizados + 1

            await sb_patch("students", f"id=eq.{sid}", {
                "next_training_session": next_ts,
                "treinos_realizados":    new_realizados,
            })

            results["presentes"].append({
                "student_id": sid,
                "next_training_session": next_ts,
                "treinos_realizados": new_realizados,
            })

        except Exception as e:
            results["presentes"].append({"student_id": sid, "error": str(e)})

    # 3. Processar ausentes (só marca missed, NÃO avança treinos)
    for sid in body.ausentes:
        try:
            await sb_patch(
                "class_enrollments",
                f"student_id=eq.{sid}&class_date=eq.{body.class_date}&status=eq.confirmed",
                {"status": "missed"}
            )
            results["ausentes"].append({"student_id": sid, "status": "missed"})
        except Exception as e:
            results["ausentes"].append({"student_id": sid, "error": str(e)})

    # 4. Registrar cargas alteradas
    for carga in body.cargas:
        try:
            # exercise_log
            await sb_post("exercise_logs", {
                "workout_log_id":        wlog_id,
                "exercise_id":           carga.exercise_id,
                "weight_kg":             carga.weight_kg,
                "sets_done":             carga.sets_done,
                "reps_done":             carga.reps_done,
                "changed_from_previous": carga.changed_from_previous,
                "notes":                 carga.notes,
            })

            # exercise_history (upsert — última carga por aluno/exercício)
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{SUPABASE_URL}/rest/v1/exercise_history",
                    headers={**SB_HEADERS,
                             "Prefer": "resolution=merge-duplicates,return=minimal"},
                    json={
                        "student_id":      body.student_id,
                        "exercise_id":     carga.exercise_id,
                        "last_weight_kg":  carga.weight_kg,
                        "last_recorded_at": f"{body.class_date}T12:00:00",
                        "workout_log_id":  wlog_id,
                    },
                    timeout=20
                )
        except Exception as e:
            results.setdefault("carga_errors", []).append(str(e))

    return {"ok": True, **results}


# ── Endpoint simples para o professor ver seus alunos do dia ──
@app.get("/professor/{instructor_id}/aulas/{data}")
async def aulas_professor(instructor_id: str, data: str, _=Depends(check_api_key)):
    """
    Retorna os enrollments escalados para o professor em determinada data.
    Professor só vê alunos atribuídos a ele (instructor_id).
    """
    enrollments = await sb_get(
        "class_enrollments",
        f"instructor_id=eq.{instructor_id}&class_date=eq.{data}"
        f"&select=id,student_id,class_slot_id,status,training_session_id"
        f"&status=neq.cancelled"
    )
    if not enrollments:
        return []

    # Buscar nomes dos alunos
    sids = ",".join({e["student_id"] for e in enrollments})
    profiles = await sb_get("profiles", f"id=in.({sids})&select=id,full_name,phone")
    prof_map  = {p["id"]: p for p in profiles}

    # Buscar dados de treino de cada aluno (próxima ficha + última carga)
    for e in enrollments:
        sid = e["student_id"]
        e["aluno_nome"] = prof_map.get(sid, {}).get("full_name", "")

        # next_training_session
        st_rows = await sb_get("students",
            f"id=eq.{sid}&select=next_training_session,current_program_id,treinos_realizados")
        if st_rows:
            st = st_rows[0]
            e["next_training_session"] = st.get("next_training_session", 1)
            e["treinos_realizados"]    = st.get("treinos_realizados", 0)
            e["current_program_id"]    = st.get("current_program_id")

    return enrollments


# ════════════════════════════════════════════════════════
# IMPRESSÃO DE FICHAS DE TREINO
# Fluxo: 5 min antes da aula →
#   1. Busca enrollments confirmados do horário
#   2. Para cada aluno: monta ficha (exercícios + última carga)
#   3. Marca printed_at no enrollment
#   4. Retorna HTML/dados para o serviço local imprimir
# ════════════════════════════════════════════════════════

@app.get("/impressao/aula/{class_slot_id}/{data}")
async def dados_impressao_aula(class_slot_id: str, data: str, _=Depends(check_api_key)):
    """
    Retorna dados completos para impressão das fichas de treino
    de todos os alunos confirmados naquele horário/data.
    Usado pelo serviço local de impressão.
    """
    # 1. Buscar enrollments confirmados não impressos
    enrollments = await sb_get("class_enrollments",
        f"class_slot_id=eq.{class_slot_id}&class_date=eq.{data}"
        f"&status=in.(confirmed,attended)&select=id,student_id,training_session_id,printed_at"
    )
    if not enrollments:
        return {"fichas": [], "slot_id": class_slot_id, "data": data}

    fichas = []
    for enroll in enrollments:
        sid = enroll["student_id"]

        # 2. Dados do aluno
        profile_rows = await sb_get("profiles", f"id=eq.{sid}&select=full_name,phone")
        st_rows      = await sb_get("students",
            f"id=eq.{sid}&select=next_training_session,current_program_id,treinos_realizados")

        if not profile_rows or not st_rows:
            continue

        profile = profile_rows[0]
        st      = st_rows[0]

        # 3. Determinar a ficha a ser impressa (next_training_session)
        session_id = enroll.get("training_session_id")
        if not session_id and st.get("current_program_id"):
            # Buscar a sessão pela posição next_training_session
            sessions = await sb_get("training_sessions",
                f"program_id=eq.{st['current_program_id']}&order=order")
            n = st.get("next_training_session", 1) or 1
            idx = (n - 1) % max(len(sessions), 1)
            session_id = sessions[idx]["id"] if sessions else None

        if not session_id:
            continue

        # 4. Buscar exercícios da sessão
        session_rows = await sb_get("training_sessions",
            f"id=eq.{session_id}&select=id,name,order,notes")
        if not session_rows:
            continue
        session = session_rows[0]

        ex_rows = await sb_get("training_exercises",
            f"session_id=eq.{session_id}&select=id,exercise_id,sets,reps,rest_seconds,order,observation,superset_group_id&order=order")

        # 5. Buscar nomes dos exercícios
        if ex_rows:
            ex_ids = ",".join({e["exercise_id"] for e in ex_rows})
            ex_data = await sb_get("exercises", f"id=in.({ex_ids})&select=id,name,muscle_group")
            ex_map  = {e["id"]: e for e in ex_data}
        else:
            ex_map = {}

        # 6. Buscar última carga de cada exercício (exercise_history)
        carga_map = {}
        if ex_rows:
            ex_ids_list = list({e["exercise_id"] for e in ex_rows})
            for eid in ex_ids_list:
                hist = await sb_get("exercise_history",
                    f"student_id=eq.{sid}&exercise_id=eq.{eid}&select=last_weight_kg,last_recorded_at")
                if hist:
                    carga_map[eid] = hist[0]["last_weight_kg"]

        # 7. Montar exercícios com última carga
        exercicios = []
        for ex in ex_rows:
            eid   = ex["exercise_id"]
            ex_info = ex_map.get(eid, {})
            exercicios.append({
                "id":           ex["id"],
                "nome":         ex_info.get("name", ""),
                "grupo":        ex_info.get("muscle_group", ""),
                "series":       ex["sets"],
                "reps":         ex["reps"],
                "descanso":     ex["rest_seconds"],
                "ordem":        ex["order"],
                "obs":          ex["observation"] or "",
                "ultima_carga": carga_map.get(eid),
                "superset_id":  ex.get("superset_group_id"),
            })

        fichas.append({
            "enrollment_id": enroll["id"],
            "student_id":    sid,
            "nome":          profile["full_name"],
            "ficha_nome":    session["name"],
            "ficha_ordem":   session["order"],
            "data":          data,
            "ja_impressa":   bool(enroll.get("printed_at")),
            "exercicios":    exercicios,
        })

    return {
        "fichas": fichas,
        "slot_id": class_slot_id,
        "data": data,
        "total": len(fichas),
    }


@app.post("/impressao/marcar/{enrollment_id}")
async def marcar_impresso(enrollment_id: str, _=Depends(check_api_key)):
    """Marca printed_at no enrollment para evitar reimpressão."""
    from datetime import datetime, timezone
    await sb_patch("class_enrollments", f"id=eq.{enrollment_id}",
        {"printed_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "enrollment_id": enrollment_id}


@app.get("/impressao/horarios/{data}")
async def horarios_com_alunos(data: str, _=Depends(check_api_key)):
    """
    Retorna os horários que têm alunos confirmados em uma data.
    Usado pelo serviço local para saber quais fichas imprimir.
    """
    wd = __import__('datetime').date.fromisoformat(data).weekday()
    # Supabase weekday: 0=dom...6=sab. Python weekday: 0=seg...6=dom
    # Convert: python 0(seg)→supa 1, python 6(dom)→supa 0
    supa_wd = (wd + 1) % 7

    slots = await sb_get("class_slots",
        f"active=eq.true&weekday=eq.{supa_wd}&order=start_time")

    result = []
    for slot in slots:
        count = await sb_get("class_enrollments",
            f"class_slot_id=eq.{slot['id']}&class_date=eq.{data}"
            f"&status=in.(confirmed,attended)&select=id")
        if count:
            result.append({
                "slot_id":    slot["id"],
                "horario":    slot["start_time"][:5],
                "capacidade": slot["capacity"],
                "confirmados": len(count),
            })

    return {"data": data, "horarios": result}


# ════════════════════════════════════════════════════════
# INTEGRAÇÃO TECNOFIT
# Puxa dados em tempo real do Tecnofit (check-ins, agenda)
# Igual ao sistema do Bubble — mesma lógica, mesma API
# ════════════════════════════════════════════════════════

TECNOFIT_EMAIL    = os.getenv("TECNOFIT_EMAIL",    "matheusdgs@hotmail.com")
TECNOFIT_PASSWORD = os.getenv("TECNOFIT_PASSWORD", "Estudio7@")
TECNOFIT_BASE     = "https://app.tecnofit.com.br"
TECNOFIT_EMPRESA  = "103025"

_tf_token = None
_tf_token_ts = 0

async def tf_login():
    """Autentica no Tecnofit e retorna o token JWT."""
    global _tf_token, _tf_token_ts
    import time
    if _tf_token and (time.time() - _tf_token_ts) < 43200:
        return _tf_token
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{TECNOFIT_BASE}/api-core/auth",
            json={"email": TECNOFIT_EMAIL, "password": TECNOFIT_PASSWORD},
            timeout=15
        )
        r.raise_for_status()
        _tf_token = r.json().get("token")
        _tf_token_ts = time.time()
        return _tf_token

async def tf_get(path: str):
    """GET no Tecnofit API com autenticação."""
    token = await tf_login()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{TECNOFIT_BASE}/api-core/{TECNOFIT_EMPRESA}/{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=20
        )
        r.raise_for_status()
        return r.json()

async def tf_post(path: str, data=None):
    """POST no Tecnofit API com autenticação."""
    token = await tf_login()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{TECNOFIT_BASE}/api-core/{TECNOFIT_EMPRESA}/{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"},
            json=data,
            timeout=20
        )
        r.raise_for_status()
        return r.json()

async def tf_get_agenda_dia(data: str):
    """Busca agenda completa do dia via POST /agenda/grade/{data}/{data}.
    Retorna lista de eventos com IDs, quorum e staff."""
    result = await tf_post(f"agenda/grade/{data}/{data}")
    grid = result.get("grid", [])
    if not grid:
        return []
    return grid[0].get("events", [])


@app.get("/tecnofit/status")
async def tecnofit_status(_=Depends(check_api_key)):
    """Verifica se a integração Tecnofit está funcionando."""
    try:
        token = await tf_login()
        return {"status": "ok", "authenticated": bool(token), "empresa": TECNOFIT_EMPRESA}
    except Exception as e:
        return {"status": "error", "authenticated": False, "message": str(e)}


@app.get("/tecnofit/grids/{data}")
async def tecnofit_grids(data: str, _=Depends(check_api_key)):
    """Lista horários do dia no Tecnofit."""
    result = await tf_get(f"agenda/grids?date={data}")
    grids = result.get("grids", [])
    personal = [g for g in grids if "PERSONAL" in g.get("name", "")]
    from collections import defaultdict
    by_time = defaultdict(list)
    for g in personal:
        by_time[g["startTime"]].append(g)
    horarios = []
    for t in sorted(by_time.keys()):
        gl = by_time[t]
        horarios.append({"horario": t, "capacidade": gl[0].get("capacity", 9),
                         "grids": [{"id": g["id"], "day": g["day"]} for g in gl]})
    return {"data": data, "horarios": horarios}


@app.post("/tecnofit/sync-fixed-slots")
async def sync_fixed_slots(_=Depends(check_api_key)):
    """Busca membros fixos de cada grid no Tecnofit e sincroniza com fixed_slots no Supabase."""
    from datetime import date as dt_date
    import httpx as hx

    today = dt_date.today().isoformat()

    # 1. Get all grids
    result = await tf_get(f"agenda/grids?date={today}")
    grids = result.get("grids", [])
    personal = [g for g in grids if "PERSONAL" in g.get("name", "")]

    # 2. For each grid, get members
    grid_members = []
    for g in personal:
        grid_id = g["id"]
        day = g.get("day", 0)  # 1=seg ... 5=sex
        start_time = g.get("startTime", "")
        try:
            members_data = await tf_get(f"agenda/grids/{grid_id}/members")
            members = members_data if isinstance(members_data, list) else members_data.get("members", members_data.get("data", []))
            for m in members:
                code = m.get("code") or m.get("memberCode")
                name = m.get("name") or m.get("memberName", "")
                if code:
                    grid_members.append({
                        "code": code, "name": name,
                        "weekday": day, "horario": start_time,
                        "grid_id": grid_id
                    })
        except Exception as e:
            grid_members.append({"error": str(e), "grid_id": grid_id})

    # 3. Build student → slots mapping
    from collections import defaultdict
    student_slots = defaultdict(set)
    for m in grid_members:
        if "error" in m:
            continue
        student_slots[m["code"]].add((m["weekday"], m["horario"]))

    # 4. Get Supabase data
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

    async with hx.AsyncClient() as client:
        # Students: matricula → id
        r = await client.get(f"{SUPABASE_URL}/rest/v1/students?select=id,matricula",
                             headers=headers, timeout=15)
        students = r.json()
        mat_to_uuid = {s["matricula"]: s["id"] for s in students if s.get("matricula")}

        # Class slots: (weekday, start_time) → id
        r = await client.get(f"{SUPABASE_URL}/rest/v1/class_slots?select=id,weekday,start_time",
                             headers=headers, timeout=15)
        slots = r.json()
        slot_lookup = {(s["weekday"], s["start_time"][:5]): s["id"] for s in slots}

        # Active contracts
        r = await client.get(f"{SUPABASE_URL}/rest/v1/contracts?status=eq.active&has_fixed_schedule=eq.true&select=id,student_id,start_date,end_date",
                             headers=headers, timeout=15)
        contracts = r.json()
        student_contract = {c["student_id"]: c for c in contracts}

        # Existing fixed_slots
        r = await client.get(f"{SUPABASE_URL}/rest/v1/fixed_slots?active=eq.true&select=student_id,class_slot_id",
                             headers=headers, timeout=15)
        existing = r.json()
        existing_set = set((e["student_id"], e["class_slot_id"]) for e in existing)

    # 5. Build inserts
    inserts = []
    stats = {"total_grid_members": len(grid_members), "matched": 0, "already": 0,
             "no_student": 0, "no_contract": 0, "no_slot": 0}

    for code, slots_set in student_slots.items():
        uuid = mat_to_uuid.get(code)
        if not uuid:
            stats["no_student"] += 1
            continue
        contract = student_contract.get(uuid)
        if not contract:
            stats["no_contract"] += 1
            continue
        for wd, hr in slots_set:
            slot_id = slot_lookup.get((wd, hr))
            if not slot_id:
                stats["no_slot"] += 1
                continue
            if (uuid, slot_id) in existing_set:
                stats["already"] += 1
                continue
            inserts.append({
                "student_id": uuid, "contract_id": contract["id"],
                "class_slot_id": slot_id, "start_date": contract["start_date"],
                "end_date": contract["end_date"], "active": True
            })
            stats["matched"] += 1

    # 6. Insert
    inserted = 0
    if inserts:
        async with hx.AsyncClient() as client:
            for i in range(0, len(inserts), 50):
                batch = inserts[i:i+50]
                r = await client.post(f"{SUPABASE_URL}/rest/v1/fixed_slots",
                    headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=batch, timeout=15)
                if r.status_code in (200, 201):
                    inserted += len(batch)

    stats["inserted"] = inserted
    stats["total_fixed_slots"] = len(existing_set) + inserted
    return stats


@app.get("/tecnofit/aula/{data}/{horario}")
async def tecnofit_aula(data: str, horario: str, _=Depends(check_api_key)):
    """Busca alunos de um horário no Tecnofit. Ex: /tecnofit/aula/2026-03-27/16:30"""
    events = await tf_get_agenda_dia(data)
    evt = next((e for e in events if e.get("start") == horario), None)
    if not evt:
        raise HTTPException(404, f"Horário {horario} não encontrado para {data}")

    evt_id = evt["id"]
    quorum = evt.get("quorum", {})
    checkins = (await tf_get(f"agenda/eventos/{evt_id}/checkins")).get("checkins", [])
    origin_map = {0: "agenda_fixa", 1: "avulsa", 2: "reposicao", 3: "reagendamento"}

    return {
        "data": data, "horario": horario, "event_id": evt_id,
        "capacidade": quorum.get("capacity", 9),
        "alunos": [{"code": c.get("code"), "name": c.get("name"), "photo": c.get("photo"),
                     "contract": c.get("contract"), "tipo": origin_map.get(c.get("origin"), "?"),
                     "checkin": c.get("checkin"), "phone": c.get("cellphone")} for c in checkins],
        "total": len(checkins), "fixos": quorum.get("fixed", 0),
        "reposicoes": quorum.get("replacements", 0),
    }


@app.get("/tecnofit/dia/{data}")
async def tecnofit_dia(data: str, _=Depends(check_api_key)):
    """Agenda completa do dia — todos os horários com alunos. 24/7."""
    from datetime import date as dt_date
    d = dt_date.fromisoformat(data)

    events = await tf_get_agenda_dia(data)
    # Filter only PERSONAL (skip MANUTENCAO etc)
    personal = [e for e in events if "PERSONAL" in e.get("name", "")]

    origin_map = {0: "agenda_fixa", 1: "avulsa", 2: "reposicao", 3: "reagendamento"}
    horarios = []

    for evt in sorted(personal, key=lambda x: x.get("start", "")):
        evt_id = evt["id"]
        quorum = evt.get("quorum", {})
        try:
            checkins = (await tf_get(f"agenda/eventos/{evt_id}/checkins")).get("checkins", [])
        except:
            checkins = []

        horarios.append({
            "horario": evt.get("start", ""),
            "event_id": evt_id,
            "capacidade": quorum.get("capacity", 9),
            "alunos": [{"code": c.get("code"), "name": c.get("name"),
                        "photo": c.get("photo"),
                        "tipo": origin_map.get(c.get("origin"), "?"),
                        "checkin": c.get("checkin")} for c in checkins],
            "total": quorum.get("total", len(checkins)),
            "fixos": quorum.get("fixed", 0),
            "reposicoes": quorum.get("replacements", 0),
        })

    return {
        "data": data,
        "dia_semana": ["dom","seg","ter","qua","qui","sex","sab"][(d.weekday()+1)%7],
        "horarios": horarios,
        "total_horarios": len(horarios),
        "total_alunos": sum(h["total"] for h in horarios),
    }
