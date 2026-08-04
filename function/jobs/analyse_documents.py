"""
Drain the document queue.

    python3 -m function.jobs.analyse_documents

Spawned detached by the upload endpoint, and safe to run from cron as a
backstop. Exits when the queue is empty.

Two things keep it from tripping over itself:

* A Postgres advisory lock means one drainer at a time. A second start while
  one is running exits immediately, which is what makes "spawn on every upload"
  cheap -- the running drainer picks up the new rows itself.
* Rows are claimed with FOR UPDATE SKIP LOCKED, so even if the lock is somehow
  bypassed, two drainers take different documents rather than the same one.

Concurrency is capped at four. Each document is one API call of a couple of
seconds; four keeps a fifty-file batch moving without opening fifty
simultaneous connections to OpenAI.
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from models import db

from ..services.documents import MAX_CONCURRENT, WORKER_LOCK_KEY


def _analyse_one(app, document_id, api_key, model):
    """
    One document, in its own app context.

    Each thread needs its own session: SQLAlchemy sessions are not safe to
    share across threads, and sharing one here would interleave commits from
    four documents into whatever transaction happened to be open.
    """
    with app.app_context():
        try:
            app.extensions["documents"].analyse(document_id, api_key=api_key, model=model)
        except Exception as error:  # noqa: BLE001 - one bad file must not stop the queue
            print(f"[analyse_documents] {document_id} failed: "
                  f"{type(error).__name__}: {error}", file=sys.stderr)
        finally:
            db.session.remove()


def run():
    from function import create_app

    app = create_app()
    with app.app_context():
        api_key = app.config.get("OPENAI_API_KEY") or ""
        model = app.config.get("OPENAI_VISION_MODEL") or "gpt-4o"
        if not api_key:
            print("[analyse_documents] no OPENAI_API_KEY; nothing to do.", file=sys.stderr)
            return 0

        store = app.extensions["documents"]
        done = 0

        # The outer loop closes a race at the end of the queue. An upload that
        # commits after the last claim comes back empty spawns a drainer that
        # dies on the lock -- and this one is about to exit, so its row would
        # sit there until the next upload. Releasing the lock and looking once
        # more means whichever process is still alive picks it up.
        while True:
            got_lock = db.session.execute(
                db.text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKER_LOCK_KEY}
            ).scalar()
            if not got_lock:
                break

            try:
                while True:
                    batch = store.claim_batch(MAX_CONCURRENT)
                    if not batch:
                        break
                    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
                        for document_id in batch:
                            pool.submit(_analyse_one, app, document_id, api_key, model)
                    done += len(batch)
            finally:
                db.session.execute(db.text("SELECT pg_advisory_unlock(:k)"), {"k": WORKER_LOCK_KEY})
                db.session.commit()

            if not store.pending_count():
                break

        if done:
            print(f"[analyse_documents] read {done} document(s).")
        return done


if __name__ == "__main__":
    run()
