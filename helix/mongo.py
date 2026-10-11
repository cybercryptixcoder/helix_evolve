"""Optional: mirror each run into MongoDB as it happens.

Turned on by setting MONGODB_URI (and optionally MONGODB_DB, default "helix") on
the dashboard or in helix/.env. The run folder stays the source of truth;
MongoDB gets a live copy of every program, hypothesis and generation plus the
run's config and status, so runs can be queried and compared from anywhere.

Writes go through a background thread, so a slow or unreachable database never
slows the search down. If the database can't be reached, the run carries on and
the error shows up in the status.

Collections (every document carries run_id):
  runs          one document per run: config and live status
  programs      every program, keyed by run_id + id
  hypotheses    the research log, keyed by run_id + id
  generations   one per generation, keyed by run_id + generation
"""
import os
import queue
import threading
import time

from .llm import load_env_file


class Mirror:
    def __init__(self, run_id, uri=None, db_name=None, client=None):
        load_env_file()
        self.run_id = run_id
        self.uri = uri or os.environ.get("MONGODB_URI", "").strip()
        self.db_name = db_name or os.environ.get("MONGODB_DB", "").strip() or "helix"
        self.status = {"enabled": False, "written": 0, "dropped": 0, "error": None}
        self.enabled = False
        if not (self.uri or client):
            return
        if client is None:
            try:
                import pymongo
            except ImportError:
                self.status["error"] = "pymongo isn't installed (pip install pymongo)"
                return
            client = pymongo.MongoClient(self.uri, serverSelectionTimeoutMS=5000, appname="helix")
        self.db = client[self.db_name]
        self.q = queue.Queue()
        self.enabled = self.status["enabled"] = True
        self._thread = threading.Thread(target=self._work, name="mongo-mirror", daemon=True)
        self._thread.start()

    def put(self, collection, doc, key):
        """Queue one document. `key` is the field that identifies it within this run."""
        if self.enabled:
            self.q.put((collection, {**doc, "run_id": self.run_id}, key))

    def close(self, timeout=15.0):
        """Give queued writes a chance to finish before the process exits."""
        if not self.enabled:
            return
        deadline = time.time() + timeout
        while self.q.unfinished_tasks and time.time() < deadline:
            time.sleep(0.1)

    def _work(self):
        while True:
            collection, doc, key = self.q.get()
            try:
                if not self.enabled:
                    self.status["dropped"] += 1
                    continue
                coll = self.db[collection]
                if collection == "runs":
                    coll.update_one({"run_id": self.run_id}, {"$set": doc}, upsert=True)
                else:
                    coll.replace_one({"run_id": self.run_id, key: doc[key]}, doc, upsert=True)
                self.status["written"] += 1
                self.status["error"] = None
            except Exception as exc:
                self.status["dropped"] += 1
                self.status["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                if _is_connection_error(exc):   # don't keep timing out on every queued document
                    self.enabled = self.status["enabled"] = False
                    self.status["error"] = "MongoDB unreachable, mirroring turned off for this run. " + self.status["error"]
            finally:
                self.q.task_done()


def _is_connection_error(exc):
    try:
        from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure
    except ImportError:
        return False
    # OperationFailure covers bad credentials; ConfigurationError covers a malformed URI or DNS failure.
    return isinstance(exc, (ConnectionFailure, ConfigurationError)) or (
        isinstance(exc, OperationFailure) and exc.code in (13, 18))


def check(uri=None, db_name=None):
    """Connect and ping. Returns {"ok": bool, "detail": str} and never raises."""
    load_env_file()
    uri = uri or os.environ.get("MONGODB_URI", "").strip()
    db_name = db_name or os.environ.get("MONGODB_DB", "").strip() or "helix"
    if not uri:
        return {"ok": False, "detail": "MONGODB_URI is empty, so MongoDB is off (optional)"}
    try:
        import pymongo
    except ImportError:
        return {"ok": False, "detail": "pymongo isn't installed: pip install pymongo"}
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000, appname="helix")
        client.admin.command("ping")
        runs = client[db_name]["runs"].count_documents({})
        return {"ok": True, "detail": f"connected; database '{db_name}' has {runs} run(s)"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:300]}"}
