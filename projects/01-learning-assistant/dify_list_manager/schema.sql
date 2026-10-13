CREATE TABLE IF NOT EXISTS task_state(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0);
INSERT OR IGNORE INTO task_state(id,revision) VALUES(1,0);
CREATE TABLE IF NOT EXISTS task_commands(
 id TEXT PRIMARY KEY NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('create','append','update','delete_tasks','delete_list')),
 payload TEXT NOT NULL CHECK(json_valid(payload)),
 expected_revision INTEGER NOT NULL,
 result_list_id INTEGER,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TRIGGER IF NOT EXISTS task_revision_insert AFTER INSERT ON tasks BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS task_revision_update AFTER UPDATE ON tasks BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS task_revision_delete AFTER DELETE ON tasks BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS list_revision_insert AFTER INSERT ON task_lists BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS list_revision_update AFTER UPDATE ON task_lists BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS list_revision_delete AFTER DELETE ON task_lists BEGIN UPDATE task_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS task_command_validate BEFORE INSERT ON task_commands BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM task_commands WHERE id=NEW.id AND action=NEW.action AND payload=NEW.payload) THEN RAISE(IGNORE) END;
 SELECT CASE WHEN NEW.expected_revision<>(SELECT revision FROM task_state WHERE id=1) THEN RAISE(ABORT,'stale proposal: query and confirm again') END;
 SELECT CASE WHEN length(NEW.id)<8 OR length(NEW.id)>100 THEN RAISE(ABORT,'invalid command id') END;
 SELECT CASE WHEN json_type(NEW.payload,'$.items') IS NOT 'array' OR json_type(NEW.payload,'$.task_ids') IS NOT 'array' THEN RAISE(ABORT,'invalid arrays') END;
 SELECT CASE WHEN NEW.action='create' AND (json_type(NEW.payload,'$.list_name') IS NOT 'text' OR length(trim(json_extract(NEW.payload,'$.list_name')))=0 OR length(json_extract(NEW.payload,'$.list_name'))>100) THEN RAISE(ABORT,'invalid list name') END;
 SELECT CASE WHEN NEW.action<>'create' AND NOT EXISTS(SELECT 1 FROM task_lists WHERE id=json_extract(NEW.payload,'$.list_id')) THEN RAISE(ABORT,'list no longer exists') END;
 SELECT CASE WHEN NEW.action IN ('create','append') AND (
   json_array_length(NEW.payload,'$.items')>100 OR EXISTS(SELECT 1 FROM json_each(NEW.payload,'$.items') WHERE type<>'text' OR length(trim(value))=0 OR length(value)>500)
 ) THEN RAISE(ABORT,'invalid task titles') END;
 SELECT CASE WHEN NEW.action='append' AND json_array_length(NEW.payload,'$.items')=0 THEN RAISE(ABORT,'empty task batch') END;
 SELECT CASE WHEN NEW.action IN ('update','delete_tasks') AND (
  json_array_length(NEW.payload,'$.task_ids')=0 OR
  EXISTS(SELECT 1 FROM json_each(NEW.payload,'$.task_ids') WHERE type<>'integer' OR value<=0) OR
  (SELECT COUNT(*) FROM tasks WHERE list_id=json_extract(NEW.payload,'$.list_id') AND id IN (SELECT value FROM json_each(NEW.payload,'$.task_ids')))<>json_array_length(NEW.payload,'$.task_ids')
 ) THEN RAISE(ABORT,'task missing or belongs to another list') END;
 SELECT CASE WHEN NEW.action='update' AND coalesce(json_extract(NEW.payload,'$.status'),'') NOT IN ('todo','in_progress','done') THEN RAISE(ABORT,'invalid status') END;
END;
CREATE TRIGGER IF NOT EXISTS task_command_apply AFTER INSERT ON task_commands BEGIN
 INSERT INTO task_lists(name) SELECT json_extract(NEW.payload,'$.list_name') WHERE NEW.action='create';
 UPDATE task_commands SET result_list_id=CASE WHEN NEW.action='create' THEN (SELECT id FROM task_lists WHERE name=json_extract(NEW.payload,'$.list_name')) ELSE json_extract(NEW.payload,'$.list_id') END WHERE id=NEW.id;
 INSERT INTO tasks(title,status,source,list_id)
 SELECT value,'todo','用户通过 Dify 确认新增',(SELECT result_list_id FROM task_commands WHERE id=NEW.id)
 FROM json_each(NEW.payload,'$.items') WHERE NEW.action IN ('create','append');
 UPDATE tasks SET status=json_extract(NEW.payload,'$.status'),source='用户通过 Dify 确认更新',updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
 WHERE NEW.action='update' AND list_id=json_extract(NEW.payload,'$.list_id') AND id IN (SELECT value FROM json_each(NEW.payload,'$.task_ids'));
 DELETE FROM tasks WHERE NEW.action='delete_tasks' AND list_id=json_extract(NEW.payload,'$.list_id') AND id IN (SELECT value FROM json_each(NEW.payload,'$.task_ids'));
 DELETE FROM tasks WHERE NEW.action='delete_list' AND list_id=json_extract(NEW.payload,'$.list_id');
 DELETE FROM task_lists WHERE NEW.action='delete_list' AND id=json_extract(NEW.payload,'$.list_id');
END;
