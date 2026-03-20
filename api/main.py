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
