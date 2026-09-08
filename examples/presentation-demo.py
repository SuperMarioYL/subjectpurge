import json,sqlite3,tempfile
from pathlib import Path
from subjectpurge.config import SubjectPurgeConfig
from subjectpurge.scanner import Scanner
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);db=root/'memory.db';trace=root/'trace.log'
 with sqlite3.connect(db) as c:
  c.execute('CREATE TABLE memories (content TEXT)')
  c.executemany('INSERT INTO memories VALUES (?)',[('Contact demo@example.com',),('Unrelated note',)])
 trace.write_text('Read contact demo@example.com\nUnrelated event\n')
 config=SubjectPurgeConfig.from_dict({'operator':'demo','stores':[{'id':'notes','kind':'sqlite','path':str(db),'table':'memories','text_columns':['content']},{'id':'traces','kind':'trace_text','glob':str(trace)}]})
 residue=Scanner(config).locate('demo@example.com')
 print(json.dumps({'subject':residue.subject_id,'hits':[{'store':h.store_id,'adapter':h.adapter,'kind':h.residue_kind} for h in residue.hits]},indent=2))
 with sqlite3.connect(db) as c:print('database rows after scan:',c.execute('SELECT COUNT(*) FROM memories').fetchone()[0])
