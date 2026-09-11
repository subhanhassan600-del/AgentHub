import sqlite3
import threading
import uuid

class DatabaseManager:
    def __init__(self, db_name="agent_builder.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self.create_tables()
        self._migrate()

    def create_tables(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    system_prompt TEXT
                )
            ''')
            # history references agents(id) — ON DELETE CASCADE handles cleanup automatically
            cur.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    user_message TEXT,
                    ai_response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
                )
            ''')
            self.conn.commit()

    def _migrate(self):
        """Add agent_id FK column to history if upgrading from old schema."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(history)")
            columns = {row[1] for row in cur.fetchall()}

            if "agent_id" not in columns:
                cur.execute("ALTER TABLE history ADD COLUMN agent_id TEXT")
                # Best-effort backfill from agent_name → agents.id
                cur.execute('''
                    UPDATE history SET agent_id = (
                        SELECT id FROM agents WHERE agents.name = history.agent_name
                    ) WHERE agent_name IS NOT NULL
                ''')
                # Drop rows that had no matching agent
                cur.execute("DELETE FROM history WHERE agent_id IS NULL")
                self.conn.commit()

    # ── Agents ──────────────────────────────────────────────────────────
    def save_agent(self, name, prompt):
        try:
            new_id = str(uuid.uuid4())
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    'INSERT INTO agents (id, name, system_prompt) VALUES (?, ?, ?)',
                    (new_id, name, prompt)
                )
                self.conn.commit()
            return new_id
        except Exception as e:
            print(f"Error saving agent: {e}")
            return None

    def update_agent(self, agent_id, name, prompt):
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    'UPDATE agents SET name = ?, system_prompt = ? WHERE id = ?',
                    (name, prompt, agent_id)
                )
                self.conn.commit()
            return True
        except Exception as e:
            print(f"Update Error: {e}")
            return False

    def get_agent_prompt(self, agent_id):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT system_prompt FROM agents WHERE id = ?', (agent_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def get_agent_details(self, agent_id):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT id, name, system_prompt FROM agents WHERE id = ?', (agent_id,))
            row = cur.fetchone()
        if row:
            return {"id": row[0], "name": row[1], "prompt": row[2]}
        return None

    def fetch_all_agents(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT id, name FROM agents')
            rows = cur.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]

    def delete_agent(self, agent_id):
        try:
            with self._lock:
                cur = self.conn.cursor()
                # CASCADE handles history deletion automatically
                cur.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
                self.conn.commit()
            return True
        except Exception as e:
            print(f"Delete Error: {e}")
            return False

    # ── History ─────────────────────────────────────────────────────────
    def add_history(self, agent_id, user_message, ai_response):
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    'INSERT INTO history (id, agent_id, user_message, ai_response) VALUES (?, ?, ?, ?)',
                    (str(uuid.uuid4()), agent_id, user_message, ai_response)
                )
                self.conn.commit()
        except Exception as e:
            print(f"History Error: {e}")

    def get_history(self, agent_id):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                'SELECT user_message, ai_response, timestamp FROM history WHERE agent_id = ? ORDER BY timestamp ASC',
                (agent_id,)
            )
            rows = cur.fetchall()
        return [
            {"user_message": row[0], "ai_response": row[1], "timestamp": row[2]}
            for row in rows
        ]
