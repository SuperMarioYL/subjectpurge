Output assets/demo.gif
Require subjectpurge
Require python

Set FontSize 14
Set Width 1100
Set Height 680
Set Padding 24
Set Theme { "background": "#1D1D1F" }
Set TypingSpeed 12ms

# 1. seed a 3-store agent-memory fixture (7 residues: SQLite x3 + Chroma x2 + trace x2)
Type "python examples/seed_demo.py /tmp/sp-demo"
Enter
Sleep 4s

# 2. scan — locate every PII residue of the subject across the registered stores
Type "subjectpurge scan --subject 13800138000 --config /tmp/sp-demo/stores.yaml --out /tmp/sp-demo/residue_map.json"
Enter
Sleep 4s

# 3. peek at the residue map (first hit only — the rest scroll past)
Type "python examples/show_map.py /tmp/sp-demo/residue_map.json"
Enter
Sleep 3s

# 4. m2/m3 — reverse-delete + signed 等保2.0 audit (scaffolded, not in this m1 build)
Type "subjectpurge purge --subject 13800138000 --config /tmp/sp-demo/stores.yaml --confirm"
Enter
Sleep 2s

Type "subjectpurge audit --subject 13800138000"
Enter
Sleep 2s

Type "subjectpurge verify audit_proof.json"
Enter
Sleep 3s
