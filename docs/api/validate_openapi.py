import yaml, re, sys
from jsonschema import Draft202012Validator
spec = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
E = []
def err(m): E.append(m)
# --- estrutura OpenAPI 3.1 (campos obrigatórios e permitidos)
if spec.get("openapi") != "3.1.0": err("openapi != 3.1.0")
for k in ("title", "version"):
    if k not in spec.get("info", {}): err(f"info.{k} ausente")
TOP = {"openapi","info","jsonSchemaDialect","servers","paths","webhooks","components","security","tags","externalDocs"}
for k in spec:
    if k not in TOP and not k.startswith("x-"): err(f"campo de topo inválido: {k}")
METHODS = {"get","put","post","delete","options","head","patch","trace"}
OPF = {"tags","summary","description","externalDocs","operationId","parameters","requestBody","responses","callbacks","deprecated","security","servers"}
seen=set(); ids=[]
comp = spec["components"]
def deref(o):
    while isinstance(o, dict) and "$ref" in o:
        _,_,sec,name = o["$ref"].split("/")
        o = comp[sec][name]
    return o
for path, item in spec["paths"].items():
    if not path.startswith("/"): err(f"path sem '/': {path}")
    tmpl = set(re.findall(r"{(\w+)}", path))
    norm = re.sub(r"{\w+}", "{}", path)
    for m, op in item.items():
        if m not in METHODS: err(f"método inválido {m} {path}"); continue
        if (m, norm) in seen: err(f"rota equivalente duplicada {m} {path}")
        seen.add((m, norm))
        for k in op:
            if k not in OPF and not k.startswith("x-"): err(f"campo inválido {k} em {m} {path}")
        ids.append(op.get("operationId"))
        if not op.get("summary") or not op.get("description"): err(f"sem summary/description {m} {path}")
        if not op.get("tags"): err(f"sem tag {m} {path}")
        if not op.get("x-requirements"): err(f"sem requisito {m} {path}")
        if not op.get("responses"): err(f"sem responses {m} {path}")
        for code in op["responses"]:
            if not re.fullmatch(r"[1-5]\d\d|[1-5]XX|default", str(code)): err(f"código inválido {code}")
        names = set(); 
        for p in op.get("parameters", []):
            p = deref(p)
            if p["in"] not in ("path","query","header","cookie"): err("in inválido")
            if p["in"] == "path":
                names.add(p["name"])
                if p.get("required") is not True: err(f"path param não obrigatório {p['name']}")
        if names != tmpl: err(f"parâmetros de rota divergentes {m} {path}: {tmpl} x {names}")
        if m in ("get","delete") and "requestBody" in op: err(f"requestBody em {m} {path}")
        if "requestBody" in op and "content" not in op["requestBody"]: err("requestBody sem content")
        if op.get("security") == [] and "bearerAuth" in str(op.get("security")): err(f"rota pública exigindo token {m} {path}")
dups = {i for i in ids if ids.count(i) > 1}
if None in ids: err("operação sem operationId")
if dups: err(f"operationId duplicado: {dups}")
# --- $ref
txt = open(sys.argv[1], encoding="utf-8").read()
refs = re.findall(r"#/components/(\w+)/(\w+)", txt)
for sec, name in set(refs):
    if name not in comp.get(sec, {}): err(f"$ref quebrado: {sec}/{name}")
used = {n for s, n in refs}
unused = [s for sec in ("schemas","parameters","responses") for s in comp[sec] if s not in used]
# --- segurança
for p, item in spec["paths"].items():
    for m, op in item.items():
        for req in op.get("security", spec["security"]):
            for scheme in req:
                if scheme not in comp["securitySchemes"]: err(f"securityScheme inexistente {scheme}")
# --- cada schema é JSON Schema 2020-12 válido
meta = Draft202012Validator(Draft202012Validator.META_SCHEMA)
for name, s in comp["schemas"].items():
    for e in Draft202012Validator(Draft202012Validator.META_SCHEMA).iter_errors(s):
        err(f"schema {name} inválido: {e.message[:120]}")
# --- exemplos validados contra os schemas
def check(schema, ex, where):
    s = dict(schema); s["components"] = comp
    for e in Draft202012Validator(s, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(ex):
        err(f"exemplo inválido em {where}: {e.message[:150]}")
n = 0
for p, item in spec["paths"].items():
    for m, op in item.items():
        media = op.get("requestBody", {}).get("content", {}).get("application/json")
        if media and "example" in media: n += 1; check(media["schema"], media["example"], f"{m} {p} request")
        for c, r in op["responses"].items():
            r = deref(r)
            for med in r.get("content", {}).values():
                if "example" in med: n += 1; check(med["schema"], med["example"], f"{m} {p} {c}")
                for k, v in med.get("examples", {}).items(): n += 1; check(med["schema"], v["value"], f"{m} {p} {c}/{k}")
print(f"operações: {len(ids)} | caminhos: {len(spec['paths'])} | schemas: {len(comp['schemas'])} | $refs distintos: {len(set(refs))} | exemplos verificados: {n}")
print("componentes não usados:", unused or "nenhum")
print("ERROS:", len(E)); [print(" -", e) for e in E[:60]]
sys.exit(1 if E else 0)
