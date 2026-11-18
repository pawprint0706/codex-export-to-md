import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import codex_export as export


class ExportRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "sessions"
        self.root.mkdir()

    def rollout(self, filename, thread_id, session_id, records=()):
        path = self.root / filename
        meta = {"id": thread_id, "session_id": session_id, "cwd": "D:/project"}
        data = [{"type": "session_meta", "payload": meta}] + list(records)
        path.write_text("\n".join(json.dumps(r) for r in data), encoding="utf-8")
        return path

    def test_child_threads_are_not_deduplicated_as_parent(self):
        self.rollout("rollout-parent.jsonl", "parent", "parent")
        self.rollout("rollout-child.jsonl", "child", "parent")
        sessions = export.load_all_sessions([self.root])
        self.assertEqual({s["meta"]["session_id"] for s in sessions}, {"parent", "child"})

    def test_duplicate_copies_remain_available_for_backup(self):
        self.rollout("rollout-one.jsonl", "parent", "parent")
        self.rollout("rollout-two.jsonl", "parent", "parent")
        sessions = export.load_all_sessions([self.root])
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0]["source_paths"]), 2)

    def test_sqlite_only_messages_and_resume_title(self):
        self.rollout("rollout-one.jsonl", "parent", "parent", [{"type": "response_item", "payload": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "existing"}]}}])
        with closing(sqlite3.connect(self.home / "state_5.sqlite")) as db, db:
            db.execute("CREATE TABLE threads (id TEXT,title TEXT,name TEXT)")
            db.execute("INSERT INTO threads VALUES ('parent','Original prompt','Resume title')")
        with closing(sqlite3.connect(self.home / "thread_history_1.sqlite")) as db, db:
            db.execute("CREATE TABLE thread_items(thread_id TEXT,rollout_ordinal INT,created_at_ms INT,item_json TEXT)")
            for ordinal, text in enumerate(("existing", "missing", "missing")):
                db.execute("INSERT INTO thread_items VALUES (?,?,?,?)", ("parent", ordinal, 1000,
                    json.dumps({"type": "agentMessage", "text": text})))
        sessions = export.load_all_sessions([self.root])
        export.supplement_history(sessions)
        self.assertEqual(sessions[0]["history_supplement_count"], 1)
        self.assertEqual(sessions[0]["meta"]["title"], "Resume title")

    def test_backup_includes_committed_wal_data(self):
        self.rollout("rollout-one.jsonl", "parent", "parent")
        source = sqlite3.connect(self.home / "state_5.sqlite")
        self.addCleanup(source.close)
        source.execute("PRAGMA journal_mode=WAL")
        source.execute("CREATE TABLE marker (value TEXT)")
        source.execute("INSERT INTO marker VALUES ('committed in WAL')")
        source.commit()
        out = self.home / "backup"
        export.backup_raw(export.load_all_sessions([self.root]), out)
        snapshot = next((out / "raw").rglob("state_5.sqlite"))
        with closing(sqlite3.connect(snapshot)) as db:
            self.assertEqual(db.execute("SELECT value FROM marker").fetchone()[0], "committed in WAL")

    def test_tool_arguments_and_unlimited_output(self):
        command, _ = export.tool_command_text({"type": "function_call", "arguments": '{"query":"keep me"}'})
        self.assertIn("keep me", command)
        session = {"meta": {}, "events": [{"kind": "tool", "name": "test", "call_id": "a"}],
                   "outputs": {"a": "x" * 31000 + "TAIL"}}
        self.assertIn("TAIL", export.render_session_markdown(session, "source", True, 0))
        self.assertNotIn("TAIL", export.render_session_markdown(session, "source", True))

    def test_windows_extended_path_matches_resume_cwd(self):
        self.assertEqual(export.normalized_cwd(r"\\?\D:\DEV\WEB\suho-kakao-relay"),
                         export.normalized_cwd("d:/dev/web/suho-kakao-relay/"))


if __name__ == "__main__":
    unittest.main()
