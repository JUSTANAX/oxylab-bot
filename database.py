import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                mode        TEXT,
                username    TEXT,
                full_name   TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                user_id  INTEGER,
                key      TEXT,
                enabled  INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, key)
            );

            CREATE TABLE IF NOT EXISTS pet_snapshots (
                user_id     INTEGER,
                pet_name    TEXT,
                amount      INTEGER,
                recorded_at TEXT,
                PRIMARY KEY (user_id, pet_name, recorded_at)
            );

            CREATE TABLE IF NOT EXISTS ao_pet_snapshots (
                user_id     INTEGER,
                pet_kind    TEXT,
                amount      INTEGER,
                recorded_at TEXT,
                PRIMARY KEY (user_id, pet_kind, recorded_at)
            );

            CREATE TABLE IF NOT EXISTS panels (
                user_id     INTEGER,
                type        TEXT,
                api_key     TEXT,
                connected_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, type),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS alert_thresholds (
                user_id       INTEGER,
                panel         TEXT,
                threshold     INTEGER,
                enabled       INTEGER DEFAULT 1,
                last_notified TEXT,
                PRIMARY KEY (user_id, panel)
            );
        """)
        for col in ("username TEXT", "full_name TEXT", "subscription TEXT DEFAULT 'Test'"):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except Exception:
                pass

        # Пересоздаём user_settings если схема старая (нет колонки key)
        try:
            conn.execute("SELECT key FROM user_settings LIMIT 1")
        except Exception:
            conn.execute("DROP TABLE IF EXISTS user_settings")
            conn.execute("""
                CREATE TABLE user_settings (
                    user_id  INTEGER,
                    key      TEXT,
                    enabled  INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, key)
                )
            """)

def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT mode FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

def get_user_profile(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT mode, username, full_name, created_at, subscription FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

def set_subscription(user_id: int, sub: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET subscription = ? WHERE user_id = ?",
            (sub, user_id)
        )

def save_user(user_id: int, mode: str, username: str = None, full_name: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, mode, username, full_name) VALUES (?, ?, ?, ?)",
            (user_id, mode, username, full_name)
        )

def update_user_info(user_id: int, username: str = None, full_name: str = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id)
        )

def get_panel(user_id: int, panel_type: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT api_key FROM panels WHERE user_id = ? AND type = ?",
            (user_id, panel_type)
        ).fetchone()

def save_panel(user_id: int, panel_type: str, api_key: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO panels (user_id, type, api_key) VALUES (?, ?, ?)",
            (user_id, panel_type, api_key)
        )

def get_setting(user_id: int, key: str, default: bool = True) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT enabled FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key)
        ).fetchone()
        return bool(row[0]) if row is not None else default

def save_setting(user_id: int, key: str, value: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (user_id, key, enabled) VALUES (?, ?, ?)",
            (user_id, key, int(value))
        )

def setting_exists(user_id: int, key: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key)
        ).fetchone() is not None

def get_tracked_pets(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, enabled FROM user_settings WHERE user_id = ? AND key LIKE 'pet:%' ORDER BY key",
            (user_id,)
        ).fetchall()
        return [(row[0][len("pet:"):], bool(row[1])) for row in rows]

def get_tracked_ao_pets(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, enabled FROM user_settings WHERE user_id = ? AND key LIKE 'ao_pet:%' ORDER BY key",
            (user_id,)
        ).fetchall()
        return [(row[0][len("ao_pet:"):], bool(row[1])) for row in rows]

def toggle_setting(user_id: int, key: str) -> bool:
    current = get_setting(user_id, key)
    new_val = not current
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (user_id, key, enabled) VALUES (?, ?, ?)",
            (user_id, key, int(new_val))
        )
    return new_val

def get_admin_stats() -> dict:
    with get_conn() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        fs      = conn.execute("SELECT COUNT(*) FROM panels WHERE type = 'farmsync'").fetchone()[0]
        ao      = conn.execute("SELECT COUNT(*) FROM panels WHERE type = 'accountsops'").fetchone()[0]
        return {"total_users": total, "farmsync_panels": fs, "accountsops_panels": ao}

def get_all_users(limit: int = 20) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, full_name, username, mode, created_at FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

def save_pet_snapshot(user_id: int, pets: dict):
    # Минутная точность — дедуплицирует повторные вызовы в одну минуту
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:00")
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM pet_snapshots WHERE user_id = ? AND recorded_at < ?",
            (user_id, (datetime.utcnow() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:00"))
        )
        for name, data in pets.items():
            conn.execute(
                "INSERT OR REPLACE INTO pet_snapshots (user_id, pet_name, amount, recorded_at) VALUES (?, ?, ?, ?)",
                (user_id, name, data["amount"], now)
            )

def save_ao_pet_snapshot(user_id: int, pets: dict):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:00")
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM ao_pet_snapshots WHERE user_id = ? AND recorded_at < ?",
            (user_id, (datetime.utcnow() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:00"))
        )
        for kind, data in pets.items():
            conn.execute(
                "INSERT OR REPLACE INTO ao_pet_snapshots (user_id, pet_kind, amount, recorded_at) VALUES (?, ?, ?, ?)",
                (user_id, kind, data["quantity"], now)
            )

def get_ao_pets_farmed_detail(user_id: int, current_pets: dict, hours: float) -> dict | None:
    """Возвращает {pet_kind: кол-во_выбитых} за период. None если нет данных."""
    target = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT recorded_at FROM ao_pet_snapshots WHERE user_id = ? AND recorded_at <= ? ORDER BY recorded_at DESC LIMIT 1",
            (user_id, target)
        ).fetchone()
        if not row:
            return None
        rows = conn.execute(
            "SELECT pet_kind, amount FROM ao_pet_snapshots WHERE user_id = ? AND recorded_at = ?",
            (user_id, row[0])
        ).fetchall()
    past = {kind: amount for kind, amount in rows}
    return {kind: max(0, data["quantity"] - past.get(kind, 0)) for kind, data in current_pets.items()}

def get_pets_farmed_detail(user_id: int, current_pets: dict, hours: float) -> dict | None:
    """Возвращает {pet_name: кол-во_выбитых} за период. None если нет данных."""
    target = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:00")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT recorded_at FROM pet_snapshots WHERE user_id = ? AND recorded_at <= ? ORDER BY recorded_at DESC LIMIT 1",
            (user_id, target)
        ).fetchone()
        if not row:
            return None
        rows = conn.execute(
            "SELECT pet_name, amount FROM pet_snapshots WHERE user_id = ? AND recorded_at = ?",
            (user_id, row[0])
        ).fetchall()
    past = {name: amount for name, amount in rows}
    return {name: max(0, data["amount"] - past.get(name, 0)) for name, data in current_pets.items()}

def delete_panel(user_id: int, panel_type: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM panels WHERE user_id = ? AND type = ?",
            (user_id, panel_type)
        )

def get_alert_threshold(user_id: int, panel: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT threshold, enabled, last_notified FROM alert_thresholds WHERE user_id = ? AND panel = ?",
            (user_id, panel)
        ).fetchone()

def set_alert_threshold(user_id: int, panel: str, threshold: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_thresholds (user_id, panel, threshold, enabled) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(user_id, panel) DO UPDATE SET threshold = excluded.threshold, enabled = 1",
            (user_id, panel, threshold)
        )

def toggle_alert(user_id: int, panel: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE alert_thresholds SET enabled = 1 - enabled WHERE user_id = ? AND panel = ?",
            (user_id, panel)
        )

def get_users_with_alerts() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, panel, threshold, last_notified FROM alert_thresholds WHERE enabled = 1 AND threshold IS NOT NULL"
        ).fetchall()

def update_alert_notified(user_id: int, panel: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE alert_thresholds SET last_notified = ? WHERE user_id = ? AND panel = ?",
            (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), user_id, panel)
        )
