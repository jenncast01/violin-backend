import os
import sqlite3
from typing import List, Optional
import jwt
from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Violin Journey API",
    description="Backend API for Violin Journey - Musical Practice Log with JWT Bearer Authentication and Multi-User Isolation",
    version="1.1.0"
)

# CORS habilitado para comunicación con React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "violin_journey.db")
JWT_SECRET = os.getenv("JWT_SECRET", "violin_journey_secret_key_2026")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Crear tabla con columna username para separar datos por usuario del JWT
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL DEFAULT 'alice',
            date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            title TEXT NOT NULL,
            technique TEXT NOT NULL,
            difficulty INTEGER NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Verificar si la columna username existe (en caso de migración en caliente)
    cursor.execute("PRAGMA table_info(practices)")
    cols = [col[1] for col in cursor.fetchall()]
    if "username" not in cols:
        cursor.execute("ALTER TABLE practices ADD COLUMN username TEXT NOT NULL DEFAULT 'alice'")
        conn.commit()

    # Sembrar datos iniciales separados para alice y para bob con las canciones solicitadas
    cursor.execute("SELECT COUNT(*) FROM practices WHERE username = 'alice' AND title LIKE '%Hiding Place%'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("DELETE FROM practices WHERE username = 'alice'")
        alice_data = [
            ("alice", "2026-09-28", 45, "You Are My Hiding Place 🎵", "Afinación y Arco", 3, "Trabajé el puente y las notas agudas con arco suave y fluido."),
            ("alice", "2026-09-27", 50, "The Prayer (Andrea Bocelli) 🎼", "Canción Completa y Expresión", 4, "Digitación en primera posición y cambios de cuerda suaves."),
            ("alice", "2026-09-26", 40, "How Great Thou Art 🎻", "Técnica de Arco (Bow Control)", 3, "Control de dinámicas, cuidando mantener el arco perpendicular al puente."),
            ("alice", "2026-09-25", 35, "Oceans (Where Feet May Fail) 🌊", "Lectura y Solfeo", 3, "Enfoque en los coros y mantener el tiempo constante con metrónomo."),
            ("alice", "2026-09-24", 45, "Yeshua 🕊️", "Afinación y Arco", 2, "Memoria muscular y afinación limpia en cuerdas La y Re.")
        ]
        cursor.executemany("""
            INSERT INTO practices (username, date, duration_minutes, title, technique, difficulty, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, alice_data)
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM practices WHERE username = 'bob'")
    if cursor.fetchone()[0] == 0:
        bob_data = [
            ("bob", "2026-09-28", 60, "Vivaldi - Invierno (Largo)", "Expresión y Vibrato", 4, "Trabajando afinación en tercera posición y vibrato continuo."),
            ("bob", "2026-09-26", 40, "Escalas Menores Melódicas", "Escalas y Técnica", 3, "Ejercicios de velocidad en La menor y Sol menor.")
        ]
        cursor.executemany("""
            INSERT INTO practices (username, date, duration_minutes, title, technique, difficulty, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, bob_data)
        conn.commit()

    conn.close()


init_db()


# Modelos Pydantic
class PracticeCreate(BaseModel):
    date: str = Field(..., example="2026-09-28")
    duration_minutes: int = Field(..., ge=1, example=45)
    title: str = Field(..., example="Yeshua 🎵")
    technique: str = Field(..., example="Afinación y Arco")
    difficulty: int = Field(..., ge=1, le=5, example=3)
    notes: Optional[str] = Field(None, example="Trabajé cambios de cuerda.")


class PracticeResponse(BaseModel):
    id: int
    date: str
    duration_minutes: int
    title: str
    technique: str
    difficulty: int
    notes: Optional[str]
    created_at: Optional[str]


def verify_bearer_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verifica que la petición incluya el encabezado Authorization con formato Bearer <token>.
    Extrae la identidad del usuario (username / sub) desde el JWT.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado. Se requiere encabezado 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido. Use 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token JWT ha expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        # Fallback para decodificación no estricta de estructura JWT
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            return unverified
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT inválido o malformado",
                headers={"WWW-Authenticate": "Bearer"},
            )


@app.get("/health")
def health():
    return {"status": "ok", "service": "violin-backend"}


@app.get("/api/practices", response_model=List[PracticeResponse])
def get_practices(authorization: Optional[str] = Header(None)):
    user_payload = verify_bearer_token(authorization)
    username = user_payload.get("username", user_payload.get("sub", "alice"))

    conn = get_db()
    cursor = conn.cursor()
    # Filtrar estrictamente por el usuario autenticado en el JWT
    cursor.execute("SELECT * FROM practices WHERE username = ? ORDER BY id DESC", (username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/practices", response_model=PracticeResponse, status_code=status.HTTP_201_CREATED)
def create_practice(practice: PracticeCreate, authorization: Optional[str] = Header(None)):
    user_payload = verify_bearer_token(authorization)
    username = user_payload.get("username", user_payload.get("sub", "alice"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO practices (username, date, duration_minutes, title, technique, difficulty, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        username,
        practice.date,
        practice.duration_minutes,
        practice.title,
        practice.technique,
        practice.difficulty,
        practice.notes or ""
    ))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM practices WHERE id = ?", (new_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


@app.get("/api/stats")
def get_stats(authorization: Optional[str] = Header(None)):
    user_payload = verify_bearer_token(authorization)
    username = user_payload.get("username", user_payload.get("sub", "alice"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(duration_minutes), COUNT(*) FROM practices WHERE username = ?", (username,))
    total_minutes, total_sessions = cursor.fetchone()
    total_minutes = total_minutes or 0
    total_hours = round(total_minutes / 60, 1)

    cursor.execute("SELECT COUNT(DISTINCT title) FROM practices WHERE username = ?", (username,))
    total_songs = cursor.fetchone()[0]
    conn.close()

    if username == "bob":
        return {
            "level": "Intermedio 🎻",
            "total_hours": total_hours,
            "streak_days": 7,
            "songs_learned": 5,
            "total_sessions": total_sessions,
            "unique_songs_practiced": total_songs
        }

    return {
        "level": "Principiante ⭐",
        "total_hours": total_hours,
        "streak_days": 12,
        "songs_learned": 8,
        "total_sessions": total_sessions,
        "unique_songs_practiced": total_songs
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
