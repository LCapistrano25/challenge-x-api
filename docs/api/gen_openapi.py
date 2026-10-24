#!/usr/bin/env python3
"""Gera openapi.yaml do Projeto X (scratch: o entregável é o YAML)."""
import yaml

SC = {}
PATHS = {}
OPIDS = set()

# ---------------------------------------------------------------- helpers
def ref(n): return {"$ref": "#/components/schemas/" + n}
def arr(items, **kw):
    d = {"type": "array", "items": items}; d.update(kw); return d
def nul(s):
    if "$ref" in s or "oneOf" in s:
        return {"oneOf": [s, {"type": "null"}]}
    s = dict(s); s["type"] = [s["type"], "null"]
    if "examples" not in s: s["examples"] = [None]
    return s
def P(t, desc=None, ex=None, **kw):
    d = {"type": t}
    if desc: d["description"] = desc
    d.update(kw)
    if ex is not None: d["examples"] = [ex]
    return d
def INT(desc=None, ex=None, **kw): return P("integer", desc, ex, **kw)
def STR(desc=None, ex=None, **kw): return P("string", desc, ex, **kw)
def TXT(desc=None, ex=None, **kw): return P("string", desc, ex, **kw)
def BOOL(desc=None, ex=None, **kw): return P("boolean", desc, ex, **kw)
def UUID(desc=None, ex="3f6c2a9e-8b1d-4c5e-9a7f-2d1e0b4c6a8f", **kw): return P("string", desc, ex, format="uuid", **kw)
def DT(desc=None, ex="2026-10-22T16:00:00Z", **kw): return P("string", desc, ex, format="date-time", **kw)
def DEC(desc=None, ex="2.50", **kw): return P("string", desc, ex, format="decimal", pattern=r"^\d{1,2}(\.\d{1,2})?$", **kw)
def EMAIL(desc=None, ex="maria.souza@a.catolica-to.edu.br", **kw): return P("string", desc, ex, format="email", maxLength=254, **kw)
def URL(desc=None, ex="https://storage.projetox.edu.br/arquivos/exemplo.pdf", **kw): return P("string", desc, ex, format="uri", **kw)
def obj(props, required=(), desc=None, strict=False, **kw):
    d = {"type": "object"}
    if desc: d["description"] = desc
    d["properties"] = props
    if required: d["required"] = list(required)
    if strict: d["additionalProperties"] = False
    d.update(kw)
    return d
def enum(name, values, desc):
    SC[name] = {"type": "string", "enum": values, "description": desc}
def paginated(name):
    pn = "Paginated" + name
    SC[pn] = obj({
        "count": INT("Total de registros.", 1),
        "next": nul(URL("URL da próxima página.", None)),
        "previous": nul(URL("URL da página anterior.", None)),
        "results": arr(ref(name)),
    }, ["count", "next", "previous", "results"], f"Página de resultados de {name}.")
    return ref(pn)

def resolve(s):
    while "$ref" in s:
        s = SC[s["$ref"].split("/")[-1]]
    return s
def example(s):
    s = resolve(s)
    if "examples" in s: return s["examples"][0]
    if "const" in s: return s["const"]
    if "allOf" in s:
        out = {}
        for part in s["allOf"]: out.update(example(part))
        return out
    if "oneOf" in s:
        for o in s["oneOf"]:
            if resolve(o).get("type") != "null":
                return example(o)
        return None
    if "enum" in s: return s["enum"][0]
    t = s.get("type")
    if isinstance(t, list): t = [x for x in t if x != "null"][0]
    if t == "object": return {k: example(v) for k, v in s.get("properties", {}).items()}
    if t == "array": return [example(s["items"])]
    if t == "integer": return 1
    if t == "boolean": return True
    if t == "number": return 1
    fmt = s.get("format")
    return {"uuid": "3f6c2a9e-8b1d-4c5e-9a7f-2d1e0b4c6a8f", "date-time": "2026-10-22T16:00:00Z",
            "email": "usuario@a.catolica-to.edu.br", "uri": "https://storage.projetox.edu.br/arquivo.pdf",
            "decimal": "2.50", "binary": None}.get(fmt, "texto")

STD = {"400": "BadRequest", "401": "Unauthorized", "403": "Forbidden", "404": "NotFound"}
ALL = ["STUDENT", "TEACHER", "EXTERNAL_EVALUATOR", "ADMIN"]

def op(method, path, opid, tag, summary, rf, roles, desc, *, authz=None, rules=(), params=(),
       body=None, ct="application/json", req_ex=None, ok=None, ok_code="200",
       ok_desc="Operação concluída.", errs=(), conflicts=(), pend=(), public=False, more=None):
    assert opid not in OPIDS, opid
    OPIDS.add(opid)
    lines = [desc, "", "**Requisitos:** " + ", ".join(rf), ""]
    lines.append("**Autenticação:** " + ("pública (não exige token)." if public else "obrigatória (Bearer JWT)."))
    lines += ["", "**Perfis permitidos:** " + (", ".join(roles) if roles else "qualquer visitante")]
    if authz: lines += ["", "**Autorização adicional:** " + authz]
    if rules: lines += ["", "**Regras de negócio:**"] + ["- " + r for r in rules]
    if pend: lines += ["", "**Pendências relacionadas (api-pendencias.md):** " + ", ".join(pend)]
    HIGH = {"P-01", "P-04", "P-06", "P-19", "P-21", "P-23", "P-25", "P-29", "P-30", "P-31"}
    blocking = sorted(set(pend) & HIGH)
    status = "proposed" if blocking else "confirmed"
    if blocking:
        lines = ["**Status: PROPOSTO** — o contrato depende da decisão de " + ", ".join(blocking) + " e pode mudar.", ""] + lines
    o = {"tags": [tag], "operationId": opid, "summary": summary, "description": "\n".join(lines),
         "x-status": status, "x-requirements": list(rf), "x-roles": list(roles)}
    if pend: o["x-pendencias"] = list(pend)
    if public: o["security"] = []
    if params: o["parameters"] = [{"$ref": "#/components/parameters/" + p} for p in params]
    if body is not None:
        media = {"schema": body}
        if ct == "application/json":
            media["example"] = req_ex if req_ex is not None else example(body)
        o["requestBody"] = {"required": True, "content": {ct: media}}
    resp = {}
    if ok is None:
        resp[ok_code] = {"description": ok_desc}
    else:
        resp[ok_code] = {"description": ok_desc, "content": {"application/json": {"schema": ok, "example": example(ok)}}}
    if more: resp.update(more)
    codes = set(errs)
    if body is not None: codes.add("400")
    if not public:
        codes.add("401")
        if set(roles) != set(ALL): codes.add("403")
    for c in codes:
        if c in STD: resp[c] = {"$ref": "#/components/responses/" + STD[c]}
    if conflicts:
        exs = {code: {"summary": msg, "value": {"error": {"code": code, "message": msg, "details": None}}}
               for code, msg in conflicts}
        resp["409"] = {"description": "Conflito com uma regra de negócio.",
                       "content": {"application/json": {"schema": ref("Error"), "examples": exs}}}
    o["responses"] = dict(sorted(resp.items()))
    PATHS.setdefault(path, {})[method] = o

# ---------------------------------------------------------------- enums (DBML)
enum("UserRole", ["STUDENT", "TEACHER", "EXTERNAL_EVALUATOR", "ADMIN"], "Perfil do usuário (enum user_role).")
enum("EditionStatus", ["SETUP", "PUBLISHED", "IN_PROGRESS", "CLOSED"], "Situação da edição (enum edition_status).")
enum("TeamStatus", ["ACTIVE", "DISQUALIFIED"], "Situação disciplinar da equipe (enum team_status).")
enum("TeamQualification", ["QUALIFIED", "NOT_QUALIFIED"], "Resultado da verificação da equipe ao fim da formação (enum team_qualification). Semântica pendente (P-23).")
enum("MemberRole", ["LEADER", "MEMBER"], "Papel do integrante na equipe (enum member_role).")
enum("ProjectStatus", ["IN_PROGRESS", "SUBMITTED", "UNDER_EVALUATION", "APPROVED", "REJECTED"], "Situação do projeto (enum project_status). Transições pendentes (P-26).")
enum("StageType", ["FORMATION", "EVALUATION", "FINAL"], "Tipo da etapa (enum stage_type).")
enum("FieldType", ["LINK", "FILE"], "Tipo do campo de entrega (enum field_type).")
enum("InvitationStatus", ["PENDING", "ACCEPTED", "DECLINED", "CANCELLED"], "Situação do convite (enum invitation_status).")
enum("RequestStatus", ["PENDING", "APPROVED", "REJECTED", "CANCELLED"], "Situação de solicitação (enum request_status).")
enum("EvaluationStatus", ["DRAFT", "FINALIZED"], "Situação da avaliação do professor (enum evaluation_status).")
enum("ScoreStatus", ["PENDING", "PARTIAL", "FINALIZED"], "Situação da nota consolidada da etapa (enum score_status).")
enum("QuestionType", ["SCORE", "TEXT"], "Tipo de pergunta do formulário final (enum question_type).")
enum("FinalEvaluationStatus", ["PENDING", "IN_PROGRESS", "FINALIZED"], "Situação da avaliação final (enum final_evaluation_status).")
enum("CertificateType", ["PARTICIPATION", "FINALIST", "AWARD"], "Tipo de certificado (enum certificate_type). Incompleto em relação ao RF17 (P-34).")
enum("SupportTicketStatus", ["OPEN", "IN_PROGRESS", "WAITING_USER", "RESOLVED", "CLOSED"], "Situação do chamado (enum support_ticket_status). Mapeamento com os requisitos pendente (P-06).")
enum("SupportTicketPriority", ["LOW", "MEDIUM", "HIGH", "URGENT"], "Prioridade do chamado (enum support_ticket_priority).")
enum("NotificationType", ["SYSTEM", "TEAM", "PROJECT", "DELIVERABLE", "EVALUATION", "RESULT", "CERTIFICATE"], "Tipo da notificação (enum notification_type).")
# derivados (não persistidos)
enum("DeliverableStatus", ["NOT_SUBMITTED", "SUBMITTED", "NOT_DELIVERED"], "Status derivado da entrega (RF31): Não enviada, Enviada, Não entregue. Não persistido (P-27).")
enum("PhaseStatus", ["UPCOMING", "OPEN", "FINISHED"], "Status derivado da etapa a partir das datas (RF44).")
enum("MyEvaluationStatus", ["NOT_STARTED", "DRAFT", "FINALIZED"], "Situação derivada da avaliação do professor autenticado para o projeto na etapa (RF37).")
enum("PendingActionKind", ["INVITATION_RECEIVED", "JOIN_REQUEST_TO_REVIEW", "PROJECT_DATA_PENDING", "CHALLENGE_RESELECTION_REQUIRED", "DELIVERABLE_PENDING"], "Tipo de pendência que depende de ação do acadêmico (RF20).")
enum("IncompleteRequirement", ["MIN_MEMBERS", "CHALLENGE_NOT_SELECTED", "PROJECT_DATA_MISSING"], "Requisito não atendido na verificação de fim de formação (RF51). Persistência pendente (P-23).")

# ---------------------------------------------------------------- erros
SC["Error"] = obj({
    "error": obj({
        "code": STR("Código estável do erro, em snake_case.", "validation_error"),
        "message": STR("Mensagem legível para o usuário.", "Dados inválidos."),
        "details": nul(obj({}, desc="Detalhes adicionais. Em erros de validação: campo -> lista de mensagens.", additionalProperties=True)),
    }, ["code", "message", "details"]),
}, ["error"], "Formato padrão de erro proposto (P-37).")

# ---------------------------------------------------------------- refs compactas
SC["CourseSummary"] = obj({"id": INT(ex=1), "name": STR(ex="Engenharia de Software"), "slug": STR(ex="ES")}, ["id", "name", "slug"])
SC["SdgSummary"] = obj({"id": INT(ex=9), "number": INT(ex=9, minimum=1, maximum=17), "title": STR(ex="Indústria, Inovação e Infraestrutura")}, ["id", "number", "title"])
SC["EditionSummary"] = obj({"id": INT(ex=3), "year": INT(ex=2026), "semester": INT(ex=1, enum=[1, 2]),
                            "name": nul(STR(ex="Desafio X 2026/1")), "status": ref("EditionStatus")},
                           ["id", "year", "semester", "name", "status"])
SC["UserSummary"] = obj({"user_id": UUID(), "name": STR(ex="Maria Souza")}, ["user_id", "name"])
SC["TeamRef"] = obj({"id": INT(ex=12), "name": STR(ex="Equipe Aurora"), "code": STR(ex="DXA7K2")}, ["id", "name", "code"])
SC["ProjectRef"] = obj({"id": INT(ex=40), "title": STR(ex="Monitoramento inteligente do consumo de água")}, ["id", "title"])
SC["StageRef"] = obj({"id": INT(ex=7), "name": STR(ex="Entrega Preliminar"), "position": INT(ex=3)}, ["id", "name", "position"])
SC["CriterionRef"] = obj({"id": INT(ex=21), "name": STR(ex="Inovação")}, ["id", "name"])
SC["CategoryRef"] = obj({"id": INT(ex=2), "name": STR(ex="Protótipos e Artefatos")}, ["id", "name"])
SC["ChallengeSummary"] = obj({"id": INT(ex=15), "title": STR(ex="Uso eficiente de recursos hídricos no campus"),
                              "course": ref("CourseSummary"), "sdg": ref("SdgSummary")},
                             ["id", "title", "course", "sdg"])

# ---------------------------------------------------------------- auth
SC["MicrosoftSessionRequest"] = obj({"code": STR("Authorization code recebido da Microsoft pelo frontend.", "0.AQ8A3x...")}, ["code"], strict=True)
SC["MicrosoftSessionResponse"] = obj({
    "token": STR("JWT da aplicação.", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."),
    "role": ref("UserRole"),
    "profile_completed": BOOL("Indica se o perfil acadêmico (student) ou docente (teacher) já foi configurado. Proposta (P-42).", False),
}, ["token", "role", "profile_completed"])
SC["PasswordSessionRequest"] = obj({"email": EMAIL(ex="avaliador@instituicao.com"), "password": STR(ex="********", format="password")}, ["email", "password"], strict=True)
SC["SessionResponse"] = obj({"token": STR("JWT da aplicação.", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")}, ["token"])
SC["StudentProfileCreate"] = obj({
    "course_id": INT("Curso ativo do aluno.", 1),
    "registration_number": STR("Matrícula (única).", "202600123", maxLength=50),
    "term": INT("Período do aluno (1..term_count do curso).", 4, minimum=1),
}, ["course_id", "registration_number", "term"], strict=True)
SC["StudentProfileCreated"] = obj({"student": obj({"user_id": UUID()}, ["user_id"])}, ["student"])
SC["TeacherProfileCreate"] = obj({"course_ids": arr(INT(ex=1), description="Cursos aos quais o professor declara vínculo.", uniqueItems=True, minItems=1)}, ["course_ids"], strict=True)
SC["TeacherProfileCreated"] = obj({"teacher": obj({"user_id": UUID()}, ["user_id"])}, ["teacher"])

# ---------------------------------------------------------------- accounts
SC["UserStatusUpdate"] = obj({"active": BOOL("Novo status de acesso (explícito, sem alternância automática).", False)}, ["active"], strict=True)
SC["UserStatus"] = obj({"user_id": UUID(), "active": BOOL(ex=False)}, ["user_id", "active"])
SC["StudentAdmin"] = obj({
    "user_id": UUID(), "name": STR(ex="Maria Souza"), "email": EMAIL(), "active": BOOL(ex=True),
    "registration_number": STR(ex="202600123"), "course": ref("CourseSummary"), "term": INT(ex=4),
    "created_at": DT(), "updated_at": DT(),
}, ["user_id", "name", "email", "active", "registration_number", "course", "term", "created_at", "updated_at"])
SC["StudentAdminUpdate"] = obj({
    "name": STR(ex="Maria Souza Lima", maxLength=150),
    "registration_number": STR(ex="202600124", maxLength=50),
    "course_id": INT(ex=1), "term": INT(ex=5, minimum=1),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["TeacherCourseLink"] = obj({"course": ref("CourseSummary"), "active": BOOL(ex=True)}, ["course", "active"])
SC["TeacherAdmin"] = obj({
    "user_id": UUID(), "name": STR(ex="João Pereira"), "email": EMAIL(ex="joao.pereira@p.catolica-to.edu.br"),
    "active": BOOL(ex=True), "courses": arr(ref("TeacherCourseLink")), "created_at": DT(), "updated_at": DT(),
}, ["user_id", "name", "email", "active", "courses", "created_at", "updated_at"])
SC["TeacherCourseLinkWrite"] = obj({"course_id": INT(ex=1), "active": BOOL(ex=True)}, ["course_id", "active"], strict=True)
SC["TeacherAdminUpdate"] = obj({
    "name": STR(ex="João Pereira", maxLength=150),
    "courses": arr(ref("TeacherCourseLinkWrite"), description="Vínculos a criar ou atualizar. Vínculos não listados permanecem inalterados (inativação explícita com active=false)."),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["ExternalEvaluatorEditionLink"] = obj({"edition": ref("EditionSummary"), "course": nul(ref("CourseSummary"))}, ["edition", "course"])
SC["ExternalEvaluatorAdmin"] = obj({
    "user_id": UUID(), "name": STR(ex="Ana Ribeiro"), "email": EMAIL(ex="avaliador@instituicao.com"),
    "active": BOOL(ex=True), "institution": nul(STR(ex="Instituto Tecnológico do Tocantins")),
    "editions": arr(ref("ExternalEvaluatorEditionLink")), "created_at": DT(), "updated_at": DT(),
}, ["user_id", "name", "email", "active", "institution", "editions", "created_at", "updated_at"])
SC["ExternalEvaluatorAdminUpdate"] = obj({
    "name": STR(ex="Ana Ribeiro", maxLength=150), "institution": nul(STR(ex="Instituto Tecnológico do Tocantins", maxLength=200)),
}, desc="Ao menos um campo deve ser informado. A abrangência por edição é alterada em /api/admin/editions/{edition_id}/evaluators.", strict=True, minProperties=1)
SC["ExternalEvaluatorCreate"] = obj({
    "name": STR(ex="Ana Ribeiro", maxLength=150), "email": EMAIL(ex="avaliador@instituicao.com"),
    "password": STR("Senha inicial; armazenada apenas como hash.", "SenhaInicial#2026", format="password"),
    "institution": nul(STR(ex="Instituto Tecnológico do Tocantins", maxLength=200)),
}, ["name", "email", "password"], strict=True)
SC["ExternalEvaluatorCreated"] = obj({"external_evaluator": obj({"user_id": UUID(), "email": EMAIL(ex="avaliador@instituicao.com")}, ["user_id", "email"])}, ["external_evaluator"])

# ---------------------------------------------------------------- core
SC["Course"] = obj({
    "id": INT(ex=1), "name": STR(ex="Engenharia de Software"), "slug": STR("Código/sigla do curso (P-17).", "ES"),
    "term_count": INT(ex=8, minimum=1), "active": BOOL(ex=True), "created_at": DT(), "updated_at": DT(),
}, ["id", "name", "slug", "term_count", "active", "created_at", "updated_at"])
SC["CourseCreate"] = obj({
    "name": STR(ex="Engenharia de Software", maxLength=150), "slug": STR(ex="ES", maxLength=255),
    "term_count": INT(ex=8, minimum=1), "active": BOOL(ex=True, default=True),
}, ["name", "slug", "term_count"], strict=True)
SC["CourseUpdate"] = obj({
    "name": STR(ex="Engenharia de Software", maxLength=150), "slug": STR(ex="ES", maxLength=255),
    "term_count": INT(ex=10, minimum=1), "active": BOOL(ex=False),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["Sdg"] = obj({
    "id": INT(ex=9), "number": INT(ex=9, minimum=1, maximum=17), "title": STR(ex="Indústria, Inovação e Infraestrutura"),
    "description": nul(TXT(ex="Construir infraestruturas resilientes, promover a industrialização inclusiva e sustentável e fomentar a inovação.")),
    "icon": nul(STR(ex="ods-09.svg")), "active": BOOL(ex=True), "created_at": DT(), "updated_at": DT(),
}, ["id", "number", "title", "description", "icon", "active", "created_at", "updated_at"])
SC["SdgCreate"] = obj({
    "number": INT(ex=9, minimum=1, maximum=17), "title": STR(ex="Indústria, Inovação e Infraestrutura", maxLength=200),
    "description": nul(TXT(ex="Construir infraestruturas resilientes, promover a industrialização inclusiva e sustentável e fomentar a inovação.")),
    "icon": nul(STR(ex="ods-09.svg", maxLength=100)), "active": BOOL(ex=True, default=True),
}, ["number", "title"], strict=True)
SC["SdgUpdate"] = obj({
    "title": STR(ex="Indústria, Inovação e Infraestrutura", maxLength=200), "description": nul(TXT(ex="Texto oficial atualizado.")),
    "icon": nul(STR(ex="ods-09.svg", maxLength=100)), "active": BOOL(ex=False),
}, desc="O número da ODS não é editável. Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["PublicSdg"] = obj({"id": INT(ex=9), "number": INT(ex=9), "title": STR(ex="Indústria, Inovação e Infraestrutura"),
                       "description": nul(TXT(ex="Construir infraestruturas resilientes...")), "icon": nul(STR(ex="ods-09.svg"))},
                      ["id", "number", "title", "description", "icon"])

# ---------------------------------------------------------------- editions
SC["Edition"] = obj({
    "id": INT(ex=3), "year": INT(ex=2026), "semester": INT(ex=1, enum=[1, 2]), "name": nul(STR(ex="Desafio X 2026/1")),
    "status": ref("EditionStatus"), "notice_url": nul(URL("URL do PDF do edital.", "https://storage.projetox.edu.br/editais/2026-1.pdf")),
    "min_members": INT(ex=3, minimum=1), "max_members": INT(ex=5, minimum=1),
    "published_at": nul(DT(ex=None)), "closed_at": nul(DT(ex=None)), "created_at": DT(), "updated_at": DT(),
}, ["id", "year", "semester", "name", "status", "notice_url", "min_members", "max_members", "published_at", "closed_at", "created_at", "updated_at"])
SC["EditionCreate"] = obj({"year": INT(ex=2026), "semester": INT(ex=1, enum=[1, 2]), "name": nul(STR(ex="Desafio X 2026/1", maxLength=100))},
                          ["year", "semester"], strict=True)
SC["EditionUpdate"] = obj({"name": nul(STR(ex="Desafio X 2026/1", maxLength=100)), "min_members": INT(ex=3, minimum=1), "max_members": INT(ex=5, minimum=1)},
                          desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["EditionPublish"] = obj({"notice_file": STR("PDF do edital oficial.", contentMediaType="application/pdf", format="binary")}, ["notice_file"])
SC["EditionClose"] = obj({"confirm": {"type": "boolean", "const": True, "description": "Confirmação explícita do encerramento irreversível (P-45).", "examples": [True]}}, ["confirm"], strict=True)
SC["EditionSdgsUpdate"] = obj({"sdg_ids": arr(INT(ex=9), uniqueItems=True, description="Conjunto completo de ODS habilitadas na edição.")}, ["sdg_ids"], strict=True)
SC["Challenge"] = obj({
    "id": INT(ex=15), "edition_id": INT(ex=3), "course": ref("CourseSummary"), "sdg": ref("SdgSummary"),
    "title": STR(ex="Uso eficiente de recursos hídricos no campus"),
    "description": TXT(ex="Propor uma solução para reduzir o desperdício de água nas instalações da universidade."),
    "active": BOOL(ex=True), "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "course", "sdg", "title", "description", "active", "created_at", "updated_at"])
SC["ChallengeCreate"] = obj({
    "course_id": INT(ex=1), "sdg_id": INT(ex=9), "title": STR(ex="Uso eficiente de recursos hídricos no campus", maxLength=200),
    "description": TXT(ex="Propor uma solução para reduzir o desperdício de água nas instalações da universidade."),
    "active": BOOL(ex=True, default=True),
}, ["course_id", "sdg_id", "title", "description"], strict=True)
SC["ChallengeUpdate"] = obj({
    "course_id": INT(ex=1), "sdg_id": INT(ex=9), "title": STR(ex="Uso eficiente de recursos hídricos", maxLength=200),
    "description": TXT(ex="Texto revisado do desafio."), "active": BOOL(ex=False),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["Category"] = obj({
    "id": INT(ex=2), "edition_id": INT(ex=3), "name": STR(ex="Protótipos e Artefatos"),
    "description": nul(TXT(ex="Categoria A do Art. 2 do regulamento.")), "active": BOOL(ex=True), "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "name", "description", "active", "created_at", "updated_at"])
SC["CategoryCreate"] = obj({"name": STR(ex="Protótipos e Artefatos", maxLength=150), "description": nul(TXT(ex="Categoria A do Art. 2 do regulamento.")),
                            "active": BOOL(ex=True, default=True)}, ["name"], strict=True)
SC["CategoryUpdate"] = obj({"name": STR(ex="Protótipos e Artefatos", maxLength=150), "description": nul(TXT(ex="Descrição revisada.")), "active": BOOL(ex=False)},
                           desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["Criterion"] = obj({
    "id": INT(ex=21), "edition_id": INT(ex=3), "name": STR(ex="Inovação"),
    "description": nul(TXT("Descrição do critério e das faixas de desempenho.", "Avalia o grau de originalidade da solução...")),
    "tiebreak_order": nul(INT("Ordem no desempate; nulo quando não participa.", 1, minimum=1)),
    "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "name", "description", "tiebreak_order", "created_at", "updated_at"])
SC["CriterionCreate"] = obj({"name": STR(ex="Inovação", maxLength=150), "description": nul(TXT(ex="Avalia o grau de originalidade da solução...")),
                             "tiebreak_order": nul(INT(ex=1, minimum=1))}, ["name"], strict=True)
SC["CriterionUpdate"] = obj({"name": STR(ex="Inovação", maxLength=150), "description": nul(TXT(ex="Faixas revisadas.")), "tiebreak_order": nul(INT(ex=None, minimum=1))},
                            desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["DeliverableField"] = obj({
    "id": INT(ex=31), "type": ref("FieldType"), "label": STR(ex="Relatório técnico (PDF)"), "required": BOOL(ex=True),
    "formats": nul(STR("Formatos permitidos (somente FILE).", "pdf")), "max_size_mb": nul(INT(ex=10, minimum=1)),
}, ["id", "type", "label", "required", "formats", "max_size_mb"])
SC["DeliverableFieldWrite"] = obj({
    "id": INT("Informe para atualizar um campo existente; omita para criar.", 31),
    "type": ref("FieldType"), "label": STR(ex="Relatório técnico (PDF)", maxLength=150), "required": BOOL(ex=True, default=True),
    "formats": nul(STR(ex="pdf", maxLength=200)), "max_size_mb": nul(INT(ex=10, minimum=1)),
}, ["type", "label"], strict=True)
SC["Stage"] = obj({
    "id": INT(ex=7), "edition_id": INT(ex=3), "position": INT(ex=3), "name": STR(ex="Entrega Preliminar"), "type": ref("StageType"),
    "starts_at": DT(ex="2026-04-01T00:00:00Z"), "ends_at": DT(ex="2026-04-20T23:59:00Z"), "scored": BOOL(ex=True),
    "points_value": nul(DEC(ex="3.00")), "min_evaluators": INT(ex=2, minimum=1),
    "deliverable_fields": arr(ref("DeliverableField")), "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "position", "name", "type", "starts_at", "ends_at", "scored", "points_value", "min_evaluators", "deliverable_fields", "created_at", "updated_at"])
SC["StageCreate"] = obj({
    "position": INT(ex=3, minimum=1), "name": STR(ex="Entrega Preliminar", maxLength=100), "type": ref("StageType"),
    "starts_at": DT(ex="2026-04-01T00:00:00Z"), "ends_at": DT(ex="2026-04-20T23:59:00Z"), "scored": BOOL(ex=True, default=True),
    "points_value": nul(DEC(ex="3.00")), "min_evaluators": INT(ex=2, minimum=1, default=1),
    "deliverable_fields": arr(ref("DeliverableFieldWrite")),
}, ["position", "name", "type", "starts_at", "ends_at"], strict=True)
SC["StageUpdate"] = obj({
    "position": INT(ex=3, minimum=1), "name": STR(ex="Entrega Preliminar", maxLength=100), "type": ref("StageType"),
    "starts_at": DT(ex="2026-04-01T00:00:00Z"), "ends_at": DT(ex="2026-04-22T23:59:00Z"), "scored": BOOL(ex=True),
    "points_value": nul(DEC(ex="3.00")), "min_evaluators": INT(ex=2, minimum=1),
    "deliverable_fields": arr(ref("DeliverableFieldWrite"), description="Quando informado, substitui o conjunto de campos da etapa."),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)
SC["StageCriterion"] = obj({"id": INT(ex=51), "criterion": obj({"id": INT(ex=21), "name": STR(ex="Inovação")}, ["id", "name"]), "max_score": DEC(ex="1.50")},
                           ["id", "criterion", "max_score"])
SC["StageCriteriaUpdate"] = obj({"items": arr(obj({"criterion_id": INT(ex=21), "max_score": DEC(ex="1.50")}, ["criterion_id", "max_score"], strict=True),
                                              description="Conjunto completo de critérios da etapa.")}, ["items"], strict=True)
SC["FinalQuestion"] = obj({"id": INT(ex=61), "position": INT(ex=1), "prompt": TXT(ex="Clareza e qualidade do pitch"), "type": ref("QuestionType"),
                           "max_score": nul(DEC(ex="10.00"))}, ["id", "position", "prompt", "type", "max_score"])
SC["FinalForm"] = obj({"id": INT(ex=4), "edition_id": INT(ex=3), "title": nul(STR(ex="Avaliação da Apresentação Final")), "published": BOOL(ex=False),
                       "questions": arr(ref("FinalQuestion")), "created_at": DT(), "updated_at": DT()},
                      ["id", "edition_id", "title", "published", "questions", "created_at", "updated_at"])
SC["FinalQuestionWrite"] = obj({"position": INT(ex=1, minimum=1), "prompt": TXT(ex="Clareza e qualidade do pitch"), "type": ref("QuestionType"),
                                "max_score": nul(DEC("Obrigatória e positiva para SCORE; nula para TEXT.", "10.00"))},
                               ["position", "prompt", "type"], strict=True)
SC["FinalFormWrite"] = obj({"title": nul(STR(ex="Avaliação da Apresentação Final", maxLength=150)),
                            "questions": arr(ref("FinalQuestionWrite"), minItems=1, description="Conjunto completo de perguntas.")},
                           ["questions"], strict=True)
SC["EditionEvaluator"] = obj({
    "id": INT(ex=5), "edition_id": INT(ex=3),
    "evaluator": obj({"user_id": UUID(), "name": STR(ex="Ana Ribeiro"), "email": EMAIL(ex="avaliador@instituicao.com"),
                      "institution": nul(STR(ex="Instituto Tecnológico do Tocantins"))}, ["user_id", "name", "email", "institution"]),
    "course": nul(ref("CourseSummary")), "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "evaluator", "course", "created_at", "updated_at"], desc="course nulo = abrangência em todos os cursos da edição.")
SC["EditionEvaluatorCreate"] = obj({"evaluator_id": UUID(), "course_id": nul(INT("Nulo = todos os cursos.", None))}, ["evaluator_id", "course_id"], strict=True)
SC["EditionEvaluatorUpdate"] = obj({"course_id": nul(INT("Nulo = todos os cursos.", 1))}, ["course_id"], strict=True)

# ---------------------------------------------------------------- public
SC["StageSchedule"] = obj({
    "id": INT(ex=7), "position": INT(ex=3), "name": STR(ex="Entrega Preliminar"), "type": ref("StageType"),
    "starts_at": DT(ex="2026-04-01T00:00:00Z"), "ends_at": DT(ex="2026-04-20T23:59:00Z"),
    "scored": BOOL(ex=True), "points_value": nul(DEC(ex="3.00")), "phase_status": ref("PhaseStatus"),
}, ["id", "position", "name", "type", "starts_at", "ends_at", "scored", "points_value", "phase_status"])
SC["PublicChallenge"] = obj({"id": INT(ex=15), "title": STR(ex="Uso eficiente de recursos hídricos no campus"),
                             "description": TXT(ex="Propor uma solução para reduzir o desperdício de água nas instalações da universidade."),
                             "course": ref("CourseSummary"), "sdg": ref("SdgSummary")}, ["id", "title", "description", "course", "sdg"])
SC["PublicEdition"] = obj({
    "edition": ref("EditionSummary"), "notice_url": nul(URL(ex="https://storage.projetox.edu.br/editais/2026-1.pdf")),
    "stages": arr(ref("StageSchedule")), "sdgs": arr(ref("PublicSdg")), "challenges": arr(ref("PublicChallenge")),
}, ["edition", "notice_url", "stages", "sdgs", "challenges"])
SC["PublicEditionListItem"] = obj({"edition": ref("EditionSummary"), "closed_at": nul(DT(ex="2026-07-10T18:00:00Z"))}, ["edition", "closed_at"])
SC["PublicProject"] = obj({
    "id": INT(ex=40), "edition": ref("EditionSummary"), "title": STR(ex="Monitoramento inteligente do consumo de água"),
    "summary": TXT(ex="Sensores de baixo custo e um painel web para identificar vazamentos no campus."),
    "course": ref("CourseSummary"), "sdg": ref("SdgSummary"), "category": nul(ref("CategoryRef")),
    "members": arr(obj({"name": STR(ex="Maria Souza")}, ["name"])),
}, ["id", "edition", "title", "summary", "course", "sdg", "category", "members"],
    desc="Identidade pública do projeto. course é o curso do desafio. Nunca inclui entregas, notas, feedbacks ou observações.")
SC["Winner"] = obj({"award_place": INT(ex=1, enum=[1, 2, 3]), "course": ref("CourseSummary"), "category": ref("CategoryRef"), "project": ref("PublicProject")},
                   ["award_place", "course", "category", "project"])

# ---------------------------------------------------------------- teams
SC["TeamMember"] = obj({"id": INT("Identificador do vínculo (team_member).", 101),
                        "student": obj({"user_id": UUID(), "name": STR(ex="Maria Souza"), "course": ref("CourseSummary")}, ["user_id", "name", "course"]),
                        "role": ref("MemberRole"), "joined_at": DT()}, ["id", "student", "role", "joined_at"])
SC["Team"] = obj({
    "id": INT(ex=12), "edition_id": INT(ex=3), "name": STR(ex="Equipe Aurora"), "code": STR("Código de identificação da equipe.", "DXA7K2"),
    "status": ref("TeamStatus"), "qualification": nul(ref("TeamQualification")),
    "disqualification_reason": nul(TXT(ex=None)), "members": arr(ref("TeamMember"), description="Somente vínculos ativos."),
    "created_at": DT(), "updated_at": DT(),
}, ["id", "edition_id", "name", "code", "status", "qualification", "disqualification_reason", "members", "created_at", "updated_at"])
SC["TeamCreate"] = obj({"name": STR(ex="Equipe Aurora", maxLength=150)}, ["name"], strict=True)
SC["TeamListing"] = obj({"id": INT(ex=12), "name": STR(ex="Equipe Aurora"), "code": STR(ex="DXA7K2"), "member_count": INT(ex=3),
                         "available_slots": INT(ex=2), "courses": arr(ref("CourseSummary"))},
                        ["id", "name", "code", "member_count", "available_slots", "courses"])
SC["AdminTeamListItem"] = obj({"id": INT(ex=12), "edition_id": INT(ex=3), "name": STR(ex="Equipe Aurora"), "code": STR(ex="DXA7K2"),
                               "status": ref("TeamStatus"), "qualification": nul(ref("TeamQualification")), "member_count": INT(ex=4),
                               "project": nul(ref("ProjectRef"))},
                              ["id", "edition_id", "name", "code", "status", "qualification", "member_count", "project"])
SC["TeamDisqualify"] = obj({"reason": TXT("Justificativa obrigatória.", "Plágio comprovado na entrega preliminar.", minLength=1)}, ["reason"], strict=True)
SC["InvitationCreate"] = {
    "oneOf": [
        obj({"student_id": UUID()}, ["student_id"], strict=True),
        obj({"email": EMAIL(ex="joao.lima@a.catolica-to.edu.br")}, ["email"], strict=True),
    ],
    "description": "Informe exatamente um entre student_id e email institucional.",
}
SC["Invitation"] = obj({"id": INT(ex=88), "team": ref("TeamRef"), "student": nul(ref("UserSummary")), "invited_email": nul(EMAIL(ex=None)),
                        "status": ref("InvitationStatus"), "created_at": DT(), "responded_at": nul(DT(ex=None))},
                       ["id", "team", "student", "invited_email", "status", "created_at", "responded_at"])
SC["InvitationResponse"] = obj({"status": STR(ex="ACCEPTED", enum=["ACCEPTED", "DECLINED"])}, ["status"], strict=True)
SC["JoinRequest"] = obj({"id": INT(ex=45), "team": ref("TeamRef"),
                         "student": obj({"user_id": UUID(), "name": STR(ex="Pedro Alves"), "course": ref("CourseSummary")}, ["user_id", "name", "course"]),
                         "status": ref("RequestStatus"), "created_at": DT(), "responded_at": nul(DT(ex=None))},
                        ["id", "team", "student", "status", "created_at", "responded_at"])
SC["JoinRequestDecision"] = obj({"status": STR(ex="APPROVED", enum=["APPROVED", "REJECTED"])}, ["status"], strict=True)
SC["LeadershipTransfer"] = obj({"member_id": INT("Vínculo (team_member) ativo que receberá a liderança.", 102)}, ["member_id"], strict=True)
SC["LeadershipRequestCreate"] = obj({"justification": TXT(ex="O líder anterior deixou a instituição sem transferir a liderança.", minLength=1)}, ["justification"], strict=True)
SC["LeadershipRequest"] = obj({
    "id": INT(ex=9), "team": ref("TeamRef"), "requester": ref("UserSummary"), "justification": TXT(ex="O líder anterior deixou a instituição sem transferir a liderança."),
    "status": ref("RequestStatus"), "teacher": nul(ref("UserSummary")), "decision_justification": nul(TXT(ex=None)),
    "created_at": DT(), "decided_at": nul(DT(ex=None)),
}, ["id", "team", "requester", "justification", "status", "teacher", "decision_justification", "created_at", "decided_at"])
SC["LeadershipDecision"] = obj({"status": STR(ex="APPROVED", enum=["APPROVED", "REJECTED"]),
                                "decision_justification": TXT(ex="Integrante ativo e com participação regular.", minLength=1)},
                               ["status", "decision_justification"], strict=True)
SC["MemberNoteCreate"] = obj({"member_id": INT("Vínculo (team_member) observado.", 103), "content": TXT(ex="Não participou das duas últimas reuniões.", minLength=1)},
                             ["member_id", "content"], strict=True)
SC["MemberNoteCreated"] = obj({"id": INT(ex=17), "created_at": DT()}, ["id", "created_at"], desc="Não retorna o conteúdo: o líder não pode visualizá-lo (RF33).")
SC["MemberNote"] = obj({"id": INT(ex=17), "member": ref("UserSummary"), "author": ref("UserSummary"),
                        "content": TXT(ex="Não participou das duas últimas reuniões."), "created_at": DT()},
                       ["id", "member", "author", "content", "created_at"])

# ---------------------------------------------------------------- projects
SC["Project"] = obj({
    "id": INT(ex=40), "team_id": INT(ex=12), "edition_id": INT(ex=3), "challenge": ref("ChallengeSummary"), "category": nul(ref("CategoryRef")),
    "title": STR(ex="Monitoramento inteligente do consumo de água"),
    "summary": TXT(ex="Sensores de baixo custo e um painel web para identificar vazamentos no campus."),
    "objective": nul(TXT(ex="Reduzir em 20% o desperdício de água no campus.")), "status": ref("ProjectStatus"),
    "courses": arr(ref("CourseSummary"), description="Cursos participantes (derivados dos integrantes ativos)."),
    "created_at": DT(), "updated_at": DT(),
}, ["id", "team_id", "edition_id", "challenge", "category", "title", "summary", "objective", "status", "courses", "created_at", "updated_at"])
SC["ProjectWrite"] = obj({
    "challenge_id": INT(ex=15), "category_id": INT(ex=2),
    "title": STR(ex="Monitoramento inteligente do consumo de água", maxLength=200, minLength=1),
    "summary": TXT(ex="Sensores de baixo custo e um painel web para identificar vazamentos no campus.", minLength=1),
    "objective": nul(TXT(ex="Reduzir em 20% o desperdício de água no campus.")),
}, ["challenge_id", "category_id", "title", "summary"], strict=True)
SC["ProjectOptions"] = obj({"challenges": arr(ref("PublicChallenge"), description="Desafios ativos dos cursos dos integrantes ativos."),
                            "categories": arr(obj({"id": INT(ex=2), "name": STR(ex="Protótipos e Artefatos"), "description": nul(TXT(ex="Categoria A do Art. 2."))},
                                                  ["id", "name", "description"]), description="Categorias ativas da edição.")},
                           ["challenges", "categories"])
SC["DeliverableItem"] = obj({"id": INT(ex=301), "field_id": INT(ex=31), "type": ref("FieldType"), "link": nul(URL(ex=None)),
                             "file_url": nul(URL(ex="https://storage.projetox.edu.br/entregas/40/7/relatorio.pdf")),
                             "file_name": nul(STR(ex="relatorio.pdf")), "size_bytes": nul(INT(ex=1048576, minimum=1, format="int64"))},
                            ["id", "field_id", "type", "link", "file_url", "file_name", "size_bytes"])
SC["ReceiptSummary"] = obj({"verification_code": STR(ex="DX-2026-1-7F3K9Q"), "file_url": nul(URL(ex="https://storage.projetox.edu.br/comprovantes/DX-2026-1-7F3K9Q.pdf")),
                            "generated_at": DT()}, ["verification_code", "file_url", "generated_at"])
SC["DeliverableVersion"] = obj({"id": INT(ex=77), "version_number": INT(ex=2, minimum=1), "submitted_by": ref("UserSummary"), "submitted_at": DT(),
                                "notes": nul(TXT(ex="Correção do relatório.")), "items": arr(ref("DeliverableItem")), "receipt": nul(ref("ReceiptSummary"))},
                               ["id", "version_number", "submitted_by", "submitted_at", "notes", "items", "receipt"])
SC["StageDeliverable"] = obj({
    "stage": ref("StageSchedule"), "fields": arr(ref("DeliverableField")), "status": ref("DeliverableStatus"),
    "official_version_id": nul(INT("Versão vigente no encerramento do prazo (nula enquanto aberto ou sem envio).", None)),
    "versions": arr(ref("DeliverableVersion"), description="Histórico completo, da mais recente para a mais antiga."),
}, ["stage", "fields", "status", "official_version_id", "versions"])
SC["DeliverableSubmission"] = obj({
    "items": STR("JSON (string) com a lista de itens: [{\"field_id\": int, \"link\": string}] para LINK e [{\"field_id\": int, \"file_index\": int}] para FILE, onde file_index aponta para a posição em files.",
                 '[{"field_id":31,"file_index":0},{"field_id":32,"link":"https://youtu.be/abc123"}]', contentMediaType="application/json"),
    "files": arr(STR(format="binary", contentMediaType="application/octet-stream"), description="Arquivos referenciados por file_index."),
    "notes": STR(ex="Correção do relatório."),
}, ["items"], desc="Formato multipart proposto (P-43).")
SC["Receipt"] = obj({
    "id": INT(ex=55), "version_id": INT(ex=77), "version_number": INT(ex=2), "verification_code": STR(ex="DX-2026-1-7F3K9Q"),
    "file_url": nul(URL(ex="https://storage.projetox.edu.br/comprovantes/DX-2026-1-7F3K9Q.pdf")), "generated_at": DT(),
    "team": ref("TeamRef"), "project": ref("ProjectRef"), "stage": ref("StageRef"), "submitted_at": DT(),
}, ["id", "version_id", "version_number", "verification_code", "file_url", "generated_at", "team", "project", "stage", "submitted_at"])

# ---------------------------------------------------------------- dashboard
SC["ScoreSummary"] = obj({"status": ref("ScoreStatus"), "value": nul(DEC(ex="2.40"))}, ["status", "value"])
SC["DashboardStage"] = obj({"stage": ref("StageSchedule"), "deliverable_status": nul(ref("DeliverableStatus")), "score": nul(ref("ScoreSummary"))},
                           ["stage", "deliverable_status", "score"])
SC["PendingAction"] = obj({"kind": ref("PendingActionKind"), "description": STR(ex="Você recebeu um convite da Equipe Aurora."),
                           "reference_id": nul(INT("Identificador do recurso relacionado (convite, solicitação, etapa).", 88))},
                          ["kind", "description", "reference_id"])
SC["StudentDashboard"] = obj({
    "edition": nul(ref("EditionSummary")), "team": nul(ref("Team")), "is_leader": BOOL(ex=True),
    "incomplete_requirements": arr(ref("IncompleteRequirement"), description="Vazio quando a equipe não foi marcada como incompleta (P-23)."),
    "project": nul(ref("Project")), "stages": arr(ref("DashboardStage")), "pending_actions": arr(ref("PendingAction")),
}, ["edition", "team", "is_leader", "incomplete_requirements", "project", "stages", "pending_actions"])

# ---------------------------------------------------------------- evaluations
SC["TeacherProjectRow"] = obj({
    "project": ref("ProjectRef"), "team": ref("TeamRef"), "challenge_course": ref("CourseSummary"), "stage": ref("StageRef"),
    "deliverable_status": ref("DeliverableStatus"), "evaluation_count": INT("Avaliações finalizadas na etapa.", 1),
    "min_evaluators": INT(ex=2), "my_evaluation_status": ref("MyEvaluationStatus"),
}, ["project", "team", "challenge_course", "stage", "deliverable_status", "evaluation_count", "min_evaluators", "my_evaluation_status"])
SC["EvaluationItem"] = obj({"stage_criterion_id": INT(ex=51), "points": DEC(ex="1.25"), "comment": nul(TXT(ex="Boa fundamentação."))},
                           ["stage_criterion_id", "points", "comment"])
SC["Evaluation"] = obj({"id": INT(ex=201), "project_id": INT(ex=40), "stage_id": INT(ex=7), "status": ref("EvaluationStatus"),
                        "comment": nul(TXT(ex="Projeto bem estruturado; detalhar custos.")), "items": arr(ref("EvaluationItem")),
                        "total": DEC("Soma dos pontos dos itens.", "2.40"), "created_at": DT(), "finalized_at": nul(DT(ex=None))},
                       ["id", "project_id", "stage_id", "status", "comment", "items", "total", "created_at", "finalized_at"])
SC["EvaluationForm"] = obj({
    "project": ref("ProjectRef"), "stage": obj({"id": INT(ex=7), "name": STR(ex="Entrega Preliminar"), "points_value": DEC(ex="3.00")}, ["id", "name", "points_value"]),
    "criteria": arr(obj({"stage_criterion_id": INT(ex=51), "criterion": obj({"id": INT(ex=21), "name": STR(ex="Inovação"),
                                                                             "description": nul(TXT(ex="Avalia o grau de originalidade..."))}, ["id", "name", "description"]),
                         "max_score": DEC(ex="1.50")}, ["stage_criterion_id", "criterion", "max_score"])),
    "evaluation": nul(ref("Evaluation")),
}, ["project", "stage", "criteria", "evaluation"])
SC["EvaluationItemWrite"] = obj({"stage_criterion_id": INT(ex=51), "points": DEC(ex="1.25"), "comment": nul(TXT(ex="Boa fundamentação."))},
                                ["stage_criterion_id", "points"], strict=True)
SC["EvaluationWrite"] = obj({"status": STR("DRAFT salva rascunho; FINALIZED conclui e torna a avaliação imutável.", "FINALIZED", enum=["DRAFT", "FINALIZED"]),
                             "comment": nul(TXT(ex="Projeto bem estruturado; detalhar custos.")),
                             "items": arr(ref("EvaluationItemWrite"), description="Um item por critério da etapa (todos obrigatórios para FINALIZED).")},
                            ["status", "items"], strict=True)
SC["StageScoreDetail"] = obj({
    "stage": ref("StageRef"), "points_value": DEC(ex="3.00"), "status": ref("ScoreStatus"),
    "value": nul(DEC("Média aritmética das avaliações finalizadas; exibida quando FINALIZED. Zero quando a entrega não foi realizada.", "2.40")),
    "evaluation_count": INT(ex=2), "min_evaluators": INT(ex=2), "deliverable_status": ref("DeliverableStatus"),
    "criteria": arr(obj({"criterion": ref("CriterionRef"), "max_score": DEC(ex="1.50"), "average": nul(DEC(ex="1.20"))}, ["criterion", "max_score", "average"]),
                    description="Média por critério entre as avaliações finalizadas."),
    "feedback": arr(obj({"comment": nul(TXT(ex="Projeto bem estruturado; detalhar custos.")),
                         "items": arr(obj({"criterion_name": STR(ex="Inovação"), "points": DEC(ex="1.25"), "comment": nul(TXT(ex="Boa fundamentação."))},
                                          ["criterion_name", "points", "comment"]))}, ["comment", "items"]),
                    description="Feedbacks das avaliações finalizadas, sem identificar o professor (P-44)."),
}, ["stage", "points_value", "status", "value", "evaluation_count", "min_evaluators", "deliverable_status", "criteria", "feedback"])
SC["ProjectScores"] = obj({"project": ref("ProjectRef"), "stages": arr(ref("StageScoreDetail"))}, ["project", "stages"])
SC["FinalistRow"] = obj({"project": ref("PublicProject"), "team": ref("TeamRef"), "my_evaluation_status": ref("FinalEvaluationStatus")},
                        ["project", "team", "my_evaluation_status"])
SC["FinalAnswer"] = obj({"question_id": INT(ex=61), "type": ref("QuestionType"), "value": nul(DEC(ex="8.50")), "answer_text": nul(TXT(ex=None))},
                        ["question_id", "type", "value", "answer_text"])
SC["FinalEvaluation"] = obj({"id": INT(ex=301), "status": ref("FinalEvaluationStatus"), "comment": nul(TXT(ex="Apresentação objetiva.")),
                             "answers": arr(ref("FinalAnswer")), "finalized_at": nul(DT(ex=None)), "created_at": DT(), "updated_at": DT()},
                            ["id", "status", "comment", "answers", "finalized_at", "created_at", "updated_at"])
SC["FinalEvaluationForm"] = obj({"project": ref("PublicProject"), "form": ref("FinalForm"), "evaluation": nul(ref("FinalEvaluation"))},
                                ["project", "form", "evaluation"])
SC["FinalAnswerWrite"] = obj({"question_id": INT(ex=61), "value": nul(DEC("Obrigatório para SCORE (0..max_score).", "8.50")),
                              "answer_text": nul(TXT("Obrigatório para TEXT.", None))}, ["question_id"], strict=True)
SC["FinalEvaluationWrite"] = obj({"status": STR(ex="FINALIZED", enum=["IN_PROGRESS", "FINALIZED"]), "comment": nul(TXT(ex="Apresentação objetiva.")),
                                  "answers": arr(ref("FinalAnswerWrite"))}, ["status", "answers"], strict=True)

# ---------------------------------------------------------------- results
SC["CertificateTemplate"] = obj({"id": INT(ex=6), "edition_id": INT(ex=3), "type": ref("CertificateType"),
                                 "template_url": nul(URL(ex="https://storage.projetox.edu.br/certificados/modelos/participacao-2026-1.pdf")),
                                 "signatures": nul(TXT(ex="Reitoria; Coordenação do Desafio X")), "created_at": DT(), "updated_at": DT()},
                                ["id", "edition_id", "type", "template_url", "signatures", "created_at", "updated_at"])
SC["CertificateTemplateWrite"] = obj({"template_file": STR("Arquivo do modelo.", format="binary", contentMediaType="application/octet-stream"),
                                      "signatures": STR("Dados ou referências das assinaturas digitais.", "Reitoria; Coordenação do Desafio X")},
                                     desc="Ao menos um campo deve ser informado.")
SC["Certificate"] = obj({"id": INT(ex=901), "type": ref("CertificateType"), "edition": ref("EditionSummary"), "project": nul(ref("ProjectRef")),
                         "workload_hours": nul(INT(ex=40, minimum=1)), "verification_code": STR(ex="CERT-2026-1-Q8W2E4"),
                         "file_url": nul(URL(ex="https://storage.projetox.edu.br/certificados/CERT-2026-1-Q8W2E4.pdf")), "issued_at": DT()},
                        ["id", "type", "edition", "project", "workload_hours", "verification_code", "file_url", "issued_at"])

# ---------------------------------------------------------------- support
SC["SupportTicketCreate"] = obj({"title": STR(ex="Correção de matrícula", maxLength=150, minLength=1),
                                 "description": TXT(ex="Minha matrícula foi cadastrada incorretamente.", minLength=1)},
                                ["title", "description"], strict=True)
SC["SupportTicket"] = obj({"id": UUID(ex="b7e1c2d4-5f6a-4b8c-9d0e-1f2a3b4c5d6e"), "title": STR(ex="Correção de matrícula"),
                           "description": TXT(ex="Minha matrícula foi cadastrada incorretamente."), "status": ref("SupportTicketStatus"),
                           "priority": ref("SupportTicketPriority"), "support_response": nul(TXT(ex=None)),
                           "created_at": DT(), "updated_at": DT(), "resolved_at": nul(DT(ex=None))},
                          ["id", "title", "description", "status", "priority", "support_response", "created_at", "updated_at", "resolved_at"])
SC["SupportTicketAdmin"] = {"allOf": [ref("SupportTicket"), obj({
    "requester": obj({"user_id": UUID(), "name": STR(ex="Maria Souza"), "email": EMAIL(), "role": ref("UserRole")}, ["user_id", "name", "email", "role"]),
    "assigned_to": nul(ref("UserSummary")),
}, ["requester", "assigned_to"])]}
SC["SupportTicketAdminUpdate"] = obj({
    "status": ref("SupportTicketStatus"), "priority": ref("SupportTicketPriority"),
    "support_response": nul(TXT(ex="A matrícula foi corrigida conforme solicitado.")),
    "assigned_to": nul(UUID("Usuário ADMIN responsável (P-10).")),
}, desc="Ao menos um campo deve ser informado.", strict=True, minProperties=1)

# ---------------------------------------------------------------- notifications
SC["Notification"] = obj({"id": UUID(ex="c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f"), "type": ref("NotificationType"),
                          "title": STR(ex="Novo convite de equipe"), "message": TXT(ex="Você foi convidado para a Equipe Aurora."),
                          "link": nul(STR("Destino relacionado (formato pendente, P-14).", "/convites/88")),
                          "read_at": nul(DT(ex=None)), "created_at": DT()},
                         ["id", "type", "title", "message", "link", "read_at", "created_at"])

# ---------------------------------------------------------------- paginated
PStudent = paginated("StudentAdmin"); PTeacher = paginated("TeacherAdmin"); PEval = paginated("ExternalEvaluatorAdmin")
PPublicProject = paginated("PublicProject"); PTeamListing = paginated("TeamListing"); PAdminTeam = paginated("AdminTeamListItem")
PTeacherRow = paginated("TeacherProjectRow"); PFinalist = paginated("FinalistRow"); PLeader = paginated("LeadershipRequest")
PTicket = paginated("SupportTicket"); PTicketAdmin = paginated("SupportTicketAdmin"); PNotif = paginated("Notification")

# ---------------------------------------------------------------- parameters
def pp(name, schema, desc):
    return {"name": name, "in": "path", "required": True, "description": desc, "schema": schema}
def qp(name, schema, desc):
    return {"name": name, "in": "query", "required": False, "description": desc, "schema": schema}
PARAMS = {
    "UserId": pp("user_id", {"type": "string", "format": "uuid"}, "Identificador do usuário."),
    "CourseId": pp("course_id", {"type": "integer"}, "Identificador do curso."),
    "SdgId": pp("sdg_id", {"type": "integer"}, "Identificador da ODS."),
    "EditionId": pp("edition_id", {"type": "integer"}, "Identificador da edição."),
    "ChallengeId": pp("challenge_id", {"type": "integer"}, "Identificador do desafio."),
    "CategoryId": pp("category_id", {"type": "integer"}, "Identificador da categoria."),
    "CriterionId": pp("criterion_id", {"type": "integer"}, "Identificador do critério."),
    "StageId": pp("stage_id", {"type": "integer"}, "Identificador da etapa."),
    "EvaluatorId": pp("evaluator_id", {"type": "string", "format": "uuid"}, "Identificador do avaliador externo (user_id)."),
    "TeamId": pp("team_id", {"type": "integer"}, "Identificador da equipe."),
    "InvitationId": pp("invitation_id", {"type": "integer"}, "Identificador do convite."),
    "JoinRequestId": pp("join_request_id", {"type": "integer"}, "Identificador da solicitação de entrada."),
    "LeadershipRequestId": pp("leadership_request_id", {"type": "integer"}, "Identificador da solicitação de liderança."),
    "ProjectId": pp("project_id", {"type": "integer"}, "Identificador do projeto."),
    "VersionId": pp("version_id", {"type": "integer"}, "Identificador da versão da entrega."),
    "TicketId": pp("ticket_id", {"type": "string", "format": "uuid"}, "Identificador do chamado."),
    "NotificationId": pp("notification_id", {"type": "string", "format": "uuid"}, "Identificador da notificação."),
    "CertificateTypePath": pp("certificate_type", ref("CertificateType"), "Tipo de certificado."),
    "Page": qp("page", {"type": "integer", "minimum": 1, "default": 1}, "Número da página (P-38)."),
    "PageSize": qp("page_size", {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}, "Itens por página (P-38)."),
    "Search": qp("search", {"type": "string"}, "Busca textual."),
    "ActiveFilter": qp("active", {"type": "boolean"}, "Filtra pelo status de ativação."),
    "CourseFilter": qp("course_id", {"type": "integer"}, "Filtra por curso."),
    "SdgFilter": qp("sdg_id", {"type": "integer"}, "Filtra por ODS."),
    "EditionFilter": qp("edition_id", {"type": "integer"}, "Filtra por edição."),
    "CategoryFilter": qp("category_id", {"type": "integer"}, "Filtra por categoria."),
    "StageFilter": qp("stage_id", {"type": "integer"}, "Filtra por etapa."),
    "TeamStatusFilter": qp("status", ref("TeamStatus"), "Filtra pela situação da equipe."),
    "RequestStatusFilter": qp("status", ref("RequestStatus"), "Filtra pela situação da solicitação."),
    "InvitationStatusFilter": qp("status", ref("InvitationStatus"), "Filtra pela situação do convite."),
    "TicketStatusFilter": qp("status", ref("SupportTicketStatus"), "Filtra pela situação do chamado."),
    "TicketPriorityFilter": qp("priority", ref("SupportTicketPriority"), "Filtra pela prioridade."),
    "AssignedToFilter": qp("assigned_to", {"type": "string", "format": "uuid"}, "Filtra pelo responsável."),
    "PendingOnly": qp("pending_only", {"type": "boolean", "default": False}, "Somente entregas que aguardam a avaliação do professor autenticado."),
    "UnreadOnly": qp("unread", {"type": "boolean", "default": False}, "Somente notificações não lidas."),
}
PAGE = ["Page", "PageSize"]

# ============================================================== OPERATIONS
EV = "A edição vigente é a edição com status PUBLISHED ou IN_PROGRESS (P-41)."

# ---------- auth
op("post", "/api/auth/sessions/microsoft", "authCreateMicrosoftSession", "auth", "Autenticar aluno ou professor com a Microsoft",
   ["RF18", "RF36"], [], "Troca o authorization code da Microsoft por um JWT da aplicação. A troca do código e a consulta ao Microsoft Graph ocorrem no backend.",
   public=True, body=ref("MicrosoftSessionRequest"), ok=ref("MicrosoftSessionResponse"), ok_desc="Sessão criada.",
   rules=["Domínio @a.catolica-to.edu.br define o perfil STUDENT; @p.catolica-to.edu.br define TEACHER. Outros domínios são rejeitados (403).",
          "No primeiro acesso, cria users e accounts (provider MICROSOFT, provider_account_id = identidade Microsoft), sem criar student/teacher.",
          "Se o e-mail já estiver vinculado a outra identidade Microsoft, a autenticação é recusada (409).",
          "Usuários inativos não recebem sessão (403).",
          "profile_completed=false indica que o frontend deve conduzir ao autocadastro (RF19) ou à configuração do professor (RF36.1).",
          "Expiração do token pendente (P-03)."],
   errs=["403"], conflicts=[("microsoft_identity_mismatch", "O e-mail já está vinculado a outra identidade Microsoft.")],
   pend=["P-02", "P-03", "P-42"])
op("post", "/api/auth/sessions/password", "authCreatePasswordSession", "auth", "Autenticar administrador ou avaliador externo com e-mail e senha",
   ["RF01", "RF41"], [], "Autentica contas com senha local (ADMIN e EXTERNAL_EVALUATOR).", public=True,
   body=ref("PasswordSessionRequest"), ok=ref("SessionResponse"), ok_desc="Sessão criada.",
   rules=["Credenciais inválidas, conta inexistente, conta inativa ou conta sem senha (somente Microsoft) retornam o mesmo erro 401, sem indicar o campo incorreto.",
          "Somente perfis ADMIN e EXTERNAL_EVALUATOR autenticam por senha.",
          "EXTERNAL_EVALUATOR só autentica se vinculado à edição vigente e se ela não estiver encerrada (RF41).",
          "Expiração por inatividade pendente (P-03)."],
   errs=["401"], pend=["P-01", "P-03", "P-05"])
op("post", "/api/auth/students", "authCompleteStudentProfile", "auth", "Concluir autocadastro do aluno",
   ["RF19"], ["STUDENT"], "Cria o perfil acadêmico (student) do usuário autenticado pela Microsoft.",
   authz="Somente o próprio usuário autenticado; o user_id vem do token, nunca do corpo.",
   body=ref("StudentProfileCreate"), ok=ref("StudentProfileCreated"), ok_code="201", ok_desc="Perfil criado.",
   rules=["O curso deve existir e estar ativo.", "registration_number é única.", "term deve estar entre 1 e course.term_count.",
          "Operação transacional; não retorna senha nem tokens do provedor."],
   conflicts=[("student_profile_exists", "O perfil de aluno já foi configurado."), ("registration_number_taken", "Matrícula já cadastrada.")],
   pend=["P-02"])
op("post", "/api/auth/teachers", "authCompleteTeacherProfile", "auth", "Configurar perfil do professor",
   ["RF36.1"], ["TEACHER"], "Cria o perfil de professor (teacher) e os vínculos teacher_course com os cursos informados.",
   authz="Somente o próprio usuário autenticado.",
   body=ref("TeacherProfileCreate"), ok=ref("TeacherProfileCreated"), ok_code="201", ok_desc="Perfil criado.",
   rules=["Todos os cursos devem existir e estar ativos; não há vínculos duplicados.", "Operação transacional.",
          "Se o vínculo criado concede escopo de avaliação imediatamente ou depende de aprovação do ADMIN está pendente (P-04)."],
   conflicts=[("teacher_profile_exists", "O perfil de professor já foi configurado.")], pend=["P-02", "P-04"])

# ---------- accounts
op("post", "/api/auth/external-evaluators", "accountsCreateExternalEvaluator", "accounts", "Cadastrar avaliador externo",
   ["RF11"], ["ADMIN"], "Cria o usuário (role EXTERNAL_EVALUATOR, senha com hash) e o perfil external_evaluator.",
   body=ref("ExternalEvaluatorCreate"), ok=ref("ExternalEvaluatorCreated"), ok_code="201", ok_desc="Avaliador criado.",
   rules=["E-mail sem restrição de domínio e único no sistema.", "Criação atômica de users + external_evaluator.", "A senha nunca é retornada.",
          "O vínculo com a edição é feito em POST /api/admin/editions/{edition_id}/evaluators (P-05)."],
   conflicts=[("email_taken", "E-mail já cadastrado.")], pend=["P-05"])

for kind, plural, sch, upd, ptype, rfname, extra_rules in [
    ("aluno", "students", "StudentAdmin", "StudentAdminUpdate", PStudent, "RFXX — Atualizar cadastro de aluno",
     ["registration_number continua única.", "term entre 1 e term_count do curso informado ou atual.", "Preserva vínculos com equipes, projetos, entregas e avaliações."]),
    ("professor", "teachers", "TeacherAdmin", "TeacherAdminUpdate", PTeacher, "RFXX — Atualizar cadastro de professor",
     ["Cursos devem existir; vínculos duplicados não são criados.", "Inativar um vínculo (active=false) remove o escopo de avaliação naquele curso, preservando o histórico."]),
    ("avaliador externo", "external-evaluators", "ExternalEvaluatorAdmin", "ExternalEvaluatorAdminUpdate", PEval, "RFXX — Atualizar cadastro de avaliador externo",
     ["Preserva avaliações já realizadas.", "Não existe exclusão física de avaliador; usa-se a desativação."]),
]:
    cap = "".join(w.capitalize() for w in plural.split("-"))
    filters = ["Search", "ActiveFilter"] + (["CourseFilter"] if plural != "external-evaluators" else []) + PAGE
    label = {"students": "alunos", "teachers": "professores", "external-evaluators": "avaliadores externos"}[plural]
    op("get", f"/api/admin/{plural}", f"accountsList{cap}", "accounts", f"Listar {label}",
       [rfname.split(" —")[0]], ["ADMIN"], f"Lista paginada de {label} com filtros. search busca por nome, e-mail" + (" ou matrícula." if plural == "students" else "."),
       params=filters, ok=ptype)
    op("get", f"/api/admin/{plural}/{{user_id}}", f"accountsGet{cap[:-1]}", "accounts", f"Consultar {kind}",
       [rfname.split(" —")[0]], ["ADMIN"], f"Retorna os dados de um {kind}.", params=["UserId"], ok=ref(sch), errs=["404"])
    op("patch", f"/api/admin/{plural}/{{user_id}}", f"accountsUpdate{cap[:-1]}", "accounts", f"Atualizar cadastro de {kind}",
       ["RFXX"], ["ADMIN"], f"{rfname}. Atualiza somente os campos informados, sem criar novo usuário. O e-mail não é editável.",
       params=["UserId"], body=ref(upd), ok=ref(sch), errs=["404"], rules=extra_rules,
       conflicts=[("registration_number_taken", "Matrícula já cadastrada.")] if plural == "students" else ())
    op("patch", f"/api/admin/{plural}/{{user_id}}/status", f"accountsSet{cap[:-1]}Status", "accounts", f"Ativar ou desativar {kind}",
       ["RFXX"], ["ADMIN"], "RFXX — Desativar usuário da plataforma. Recebe o status explícito.",
       params=["UserId"], body=ref("UserStatusUpdate"), ok=ref("UserStatus"), errs=["404"],
       rules=["A desativação impede novas autenticações e invalida o acesso de sessões abertas (verificação de active a cada requisição).",
              "Nunca exclui o cadastro nem registros históricos.", "Contas ADMIN não são alteradas por esta rota."])

# ---------- core
op("get", "/api/courses", "coreListCourses", "core", "Listar cursos ativos", ["RF03", "RF19", "RF36.1", "RF45"], [],
   "Lista os cursos ativos para seleção (autocadastro, configuração do professor e filtros públicos).", public=True,
   ok=arr(ref("CourseSummary")))
op("get", "/api/admin/courses", "coreAdminListCourses", "core", "Listar cursos (administração)", ["RF03"], ["ADMIN"],
   "Lista todos os cursos, inclusive inativos.", params=["Search", "ActiveFilter"], ok=arr(ref("Course")))
op("post", "/api/admin/courses", "coreCreateCourse", "core", "Cadastrar curso", ["RF03"], ["ADMIN"], "Cadastra um curso de graduação.",
   body=ref("CourseCreate"), ok=ref("Course"), ok_code="201", ok_desc="Curso criado.",
   rules=["term_count > 0.", "Nome e slug (código/sigla) únicos."],
   conflicts=[("course_name_taken", "Já existe curso com este nome."), ("course_slug_taken", "Já existe curso com esta sigla.")], pend=["P-17"])
op("patch", "/api/admin/courses/{course_id}", "coreUpdateCourse", "core", "Atualizar curso", ["RF03"], ["ADMIN"],
   "Edita dados e status de ativação do curso.", params=["CourseId"], body=ref("CourseUpdate"), ok=ref("Course"), errs=["404"],
   rules=["Reduzir term_count abaixo do período de alunos vinculados é recusado (400)."],
   conflicts=[("course_name_taken", "Já existe curso com este nome."), ("course_slug_taken", "Já existe curso com esta sigla.")])
op("delete", "/api/admin/courses/{course_id}", "coreDeleteCourse", "core", "Excluir curso sem vínculos", ["RF03"], ["ADMIN"],
   "Exclui fisicamente um curso apenas quando não há alunos, professores, desafios ou projetos vinculados em nenhuma edição.",
   params=["CourseId"], ok_code="204", ok_desc="Curso excluído.", errs=["404"],
   conflicts=[("course_in_use", "O curso possui vínculos e só pode ser inativado.")])
op("get", "/api/sdgs", "coreListSdgs", "core", "Listar ODS ativas", ["RF04", "RF45"], [], "Lista o catálogo de ODS ativas.", public=True,
   ok=arr(ref("PublicSdg")))
op("get", "/api/admin/sdgs", "coreAdminListSdgs", "core", "Listar ODS (administração)", ["RF04"], ["ADMIN"], "Lista o catálogo completo de ODS.",
   params=["ActiveFilter"], ok=arr(ref("Sdg")))
op("post", "/api/admin/sdgs", "coreCreateSdg", "core", "Cadastrar ODS", ["RF04"], ["ADMIN"], "Cadastra uma ODS no catálogo.",
   body=ref("SdgCreate"), ok=ref("Sdg"), ok_code="201", ok_desc="ODS criada.", rules=["number entre 1 e 17 e único."],
   conflicts=[("sdg_number_taken", "Já existe ODS com este número.")])
op("patch", "/api/admin/sdgs/{sdg_id}", "coreUpdateSdg", "core", "Atualizar ODS", ["RF04"], ["ADMIN"],
   "Edita título, descrição, ícone e status da ODS.", params=["SdgId"], body=ref("SdgUpdate"), ok=ref("Sdg"), errs=["404"])
op("delete", "/api/admin/sdgs/{sdg_id}", "coreDeleteSdg", "core", "Excluir ODS sem uso", ["RF04"], ["ADMIN"],
   "Exclui a ODS somente se não estiver habilitada em edição nem vinculada a desafio.", params=["SdgId"], ok_code="204", ok_desc="ODS excluída.",
   errs=["404"], conflicts=[("sdg_in_use", "A ODS está em uso e só pode ser inativada.")])

# ---------- editions
CLOSED = ("edition_closed", "A edição está encerrada e não pode ser alterada.")
FROZEN = ("edition_published", "A configuração está congelada após a publicação do edital.")
op("get", "/api/admin/editions", "editionsList", "editions", "Listar edições", ["RF47"], ["ADMIN"], "Lista as edições e suas situações.", ok=arr(ref("Edition")))
op("post", "/api/admin/editions", "editionsCreate", "editions", "Cadastrar edição", ["RF47", "RF06", "RF48", "RF49"], ["ADMIN"],
   "Cria a edição com status SETUP e pré-carrega critérios padrão (Quadro 1), categorias padrão (Art. 2) e limites 3–5, todos editáveis.",
   body=ref("EditionCreate"), ok=ref("Edition"), ok_code="201", ok_desc="Edição criada.",
   rules=["(year, semester) único.", "semester ∈ {1, 2}."], conflicts=[("edition_exists", "Já existe edição para este ano e semestre.")], pend=["P-18"])
op("get", "/api/admin/editions/{edition_id}", "editionsGet", "editions", "Consultar edição", ["RF47"], ["ADMIN"], "Retorna a edição.",
   params=["EditionId"], ok=ref("Edition"), errs=["404"])
op("patch", "/api/admin/editions/{edition_id}", "editionsUpdate", "editions", "Atualizar edição e limites de equipe", ["RF47", "RF48"], ["ADMIN"],
   "Atualiza o nome e os limites mínimo e máximo de integrantes.", params=["EditionId"], body=ref("EditionUpdate"), ok=ref("Edition"), errs=["404"],
   rules=["min_members ≥ 1 e ≤ max_members.", "Limites não podem ser alterados após a publicação (RF48).", "Nenhum dado é alterável após o encerramento."],
   conflicts=[FROZEN, CLOSED])
op("post", "/api/admin/editions/{edition_id}/publish", "editionsPublish", "editions", "Publicar edital da edição", ["RF09"], ["ADMIN"],
   "Valida as parametrizações obrigatórias, armazena o PDF do edital e muda o status para PUBLISHED.",
   params=["EditionId"], body=ref("EditionPublish"), ct="multipart/form-data", ok=ref("Edition"), errs=["404"],
   rules=["Pré-condições: cursos ativos, ODS habilitadas, desafios, categorias, limites, critérios, etapas pontuadas somando 10,00 e critérios por etapa somando o valor de cada etapa.",
          "Após publicar, congela etapas, pontuação, critérios por etapa e limites de equipe."],
   conflicts=[("edition_not_in_setup", "Somente edições em configuração podem ser publicadas."),
              ("publication_requirements_not_met", "Há parametrizações obrigatórias pendentes; ver details.")], pend=["P-16", "P-43"])
op("post", "/api/admin/editions/{edition_id}/close", "editionsClose", "editions", "Encerrar edição", ["RF47"], ["ADMIN"],
   "Encerra a edição de forma irreversível.", params=["EditionId"], body=ref("EditionClose"), ok=ref("Edition"), errs=["404"],
   rules=["Bloqueia novas entregas, avaliações e alterações (inclusive do ADMIN), exceto emissão de certificados.", "O acesso dos avaliadores externos expira."],
   conflicts=[("edition_not_published", "Somente edições publicadas podem ser encerradas."), ("edition_already_closed", "A edição já está encerrada.")],
   pend=["P-16", "P-45"])
op("get", "/api/admin/editions/{edition_id}/sdgs", "editionsListSdgs", "editions", "Listar ODS habilitadas na edição", ["RF04"], ["ADMIN"],
   "Lista as ODS habilitadas.", params=["EditionId"], ok=arr(ref("Sdg")), errs=["404"])
op("put", "/api/admin/editions/{edition_id}/sdgs", "editionsSetSdgs", "editions", "Definir ODS habilitadas na edição", ["RF04"], ["ADMIN"],
   "Substitui o conjunto de ODS habilitadas.", params=["EditionId"], body=ref("EditionSdgsUpdate"), ok=arr(ref("Sdg")), errs=["404"],
   rules=["Somente ODS ativas.", "Uma ODS usada por desafio da edição não pode ser removida."],
   conflicts=[("sdg_in_use", "A ODS está vinculada a desafios da edição."), CLOSED])
op("get", "/api/admin/editions/{edition_id}/challenges", "editionsListChallenges", "editions", "Listar desafios da edição", ["RF05"], ["ADMIN"],
   "Lista os desafios da edição.", params=["EditionId", "CourseFilter", "SdgFilter", "ActiveFilter"], ok=arr(ref("Challenge")), errs=["404"])
op("post", "/api/admin/editions/{edition_id}/challenges", "editionsCreateChallenge", "editions", "Cadastrar desafio", ["RF05"], ["ADMIN"],
   "Cadastra um desafio vinculado a exatamente um curso e uma ODS.", params=["EditionId"], body=ref("ChallengeCreate"), ok=ref("Challenge"),
   ok_code="201", ok_desc="Desafio criado.", errs=["404"],
   rules=["Curso ativo; ODS ativa e habilitada na edição (400 caso contrário).", "Permite vários desafios para o mesmo par curso/ODS."], conflicts=[CLOSED])
op("patch", "/api/admin/challenges/{challenge_id}", "editionsUpdateChallenge", "editions", "Atualizar desafio", ["RF05"], ["ADMIN"],
   "Edita dados e status do desafio.", params=["ChallengeId"], body=ref("ChallengeUpdate"), ok=ref("Challenge"), errs=["404"],
   rules=["Mesmas validações do cadastro."], conflicts=[CLOSED])
op("get", "/api/admin/editions/{edition_id}/categories", "editionsListCategories", "editions", "Listar categorias da edição", ["RF49"], ["ADMIN"],
   "Lista as categorias.", params=["EditionId"], ok=arr(ref("Category")), errs=["404"])
op("post", "/api/admin/editions/{edition_id}/categories", "editionsCreateCategory", "editions", "Cadastrar categoria", ["RF49"], ["ADMIN"],
   "Cadastra categoria da edição.", params=["EditionId"], body=ref("CategoryCreate"), ok=ref("Category"), ok_code="201", ok_desc="Categoria criada.",
   errs=["404"], conflicts=[("category_name_taken", "Já existe categoria com este nome na edição."), CLOSED])
op("patch", "/api/admin/categories/{category_id}", "editionsUpdateCategory", "editions", "Atualizar categoria", ["RF49"], ["ADMIN"],
   "Edita ou desativa a categoria.", params=["CategoryId"], body=ref("CategoryUpdate"), ok=ref("Category"), errs=["404"],
   conflicts=[("category_name_taken", "Já existe categoria com este nome na edição."), CLOSED])
op("delete", "/api/admin/categories/{category_id}", "editionsDeleteCategory", "editions", "Excluir categoria sem uso", ["RF49"], ["ADMIN"],
   "Exclui categoria não utilizada por projetos.", params=["CategoryId"], ok_code="204", ok_desc="Categoria excluída.", errs=["404"],
   conflicts=[("category_in_use", "A categoria é usada por projetos e só pode ser desativada."), CLOSED])
op("get", "/api/admin/editions/{edition_id}/criteria", "editionsListCriteria", "editions", "Listar critérios de avaliação", ["RF06"], ["ADMIN"],
   "Lista critérios e rubricas da edição.", params=["EditionId"], ok=arr(ref("Criterion")), errs=["404"])
op("post", "/api/admin/editions/{edition_id}/criteria", "editionsCreateCriterion", "editions", "Cadastrar critério", ["RF06"], ["ADMIN"],
   "Cadastra critério adicional.", params=["EditionId"], body=ref("CriterionCreate"), ok=ref("Criterion"), ok_code="201", ok_desc="Critério criado.",
   errs=["404"], rules=["Nome único na edição.", "tiebreak_order único na edição quando informado."],
   conflicts=[("criterion_name_taken", "Já existe critério com este nome."), ("tiebreak_order_taken", "Já existe critério nesta posição de desempate."), CLOSED])
op("patch", "/api/admin/criteria/{criterion_id}", "editionsUpdateCriterion", "editions", "Atualizar critério", ["RF06"], ["ADMIN"],
   "Edita nome, descrição/faixas e posição de desempate.", params=["CriterionId"], body=ref("CriterionUpdate"), ok=ref("Criterion"), errs=["404"],
   rules=["Bloqueado enquanto houver avaliações em etapa que use o critério."],
   conflicts=[("criterion_in_use_by_evaluations", "Há avaliações iniciadas em etapa que usa o critério."),
              ("criterion_name_taken", "Já existe critério com este nome."), ("tiebreak_order_taken", "Já existe critério nesta posição de desempate."), CLOSED])
op("delete", "/api/admin/criteria/{criterion_id}", "editionsDeleteCriterion", "editions", "Excluir critério sem vínculo com etapa", ["RF06"], ["ADMIN"],
   "Exclui critério não vinculado a nenhuma etapa.", params=["CriterionId"], ok_code="204", ok_desc="Critério excluído.", errs=["404"],
   conflicts=[("criterion_linked_to_stage", "O critério está vinculado a uma etapa."), CLOSED])
op("get", "/api/admin/editions/{edition_id}/stages", "editionsListStages", "editions", "Listar etapas da edição", ["RF07"], ["ADMIN"],
   "Lista o cronograma com campos de entrega.", params=["EditionId"], ok=arr(ref("Stage")), errs=["404"])
op("post", "/api/admin/editions/{edition_id}/stages", "editionsCreateStage", "editions", "Cadastrar etapa", ["RF07"], ["ADMIN"],
   "Cadastra etapa e seus campos de entrega.", params=["EditionId"], body=ref("StageCreate"), ok=ref("Stage"), ok_code="201", ok_desc="Etapa criada.",
   errs=["404"],
   rules=["ends_at > starts_at; position única na edição; min_evaluators ≥ 1.", "points_value obrigatório e > 0 quando scored; nulo quando não pontuada.",
          "A soma de 10,00 pontos é exigida na publicação (RF09), não a cada gravação.", "max_size_mb > 0; formats e max_size_mb apenas para FILE.",
          "Etapa FINAL não compõe a nota acadêmica (P-20)."],
   conflicts=[("stage_position_taken", "Já existe etapa nesta posição."), FROZEN, CLOSED], pend=["P-19", "P-20"])
op("get", "/api/admin/stages/{stage_id}", "editionsGetStage", "editions", "Consultar etapa", ["RF07"], ["ADMIN"], "Retorna a etapa.",
   params=["StageId"], ok=ref("Stage"), errs=["404"])
op("patch", "/api/admin/stages/{stage_id}", "editionsUpdateStage", "editions", "Atualizar etapa", ["RF07"], ["ADMIN"],
   "Atualiza a etapa e, opcionalmente, substitui seus campos de entrega.", params=["StageId"], body=ref("StageUpdate"), ok=ref("Stage"), errs=["404"],
   rules=["Mesmas validações do cadastro.", "Congelada após a publicação; prorrogação individual é escopo do RF14 (P-21)."],
   conflicts=[("stage_position_taken", "Já existe etapa nesta posição."), FROZEN, CLOSED], pend=["P-21"])
op("get", "/api/admin/stages/{stage_id}/criteria", "editionsListStageCriteria", "editions", "Listar critérios da etapa", ["RF08"], ["ADMIN"],
   "Lista a matriz de avaliação da etapa.", params=["StageId"], ok=arr(ref("StageCriterion")), errs=["404"])
op("put", "/api/admin/stages/{stage_id}/criteria", "editionsSetStageCriteria", "editions", "Definir critérios e pontuações da etapa", ["RF08"], ["ADMIN"],
   "Substitui os critérios vinculados à etapa pontuada e suas pontuações máximas.", params=["StageId"], body=ref("StageCriteriaUpdate"),
   ok=arr(ref("StageCriterion")), errs=["404"],
   rules=["Somente etapas pontuadas.", "max_score > 0.", "Soma dos max_score igual a points_value da etapa (400 stage_criteria_sum_mismatch).",
          "Critério e etapa da mesma edição."], conflicts=[FROZEN, CLOSED])
op("get", "/api/admin/editions/{edition_id}/final-form", "editionsGetFinalForm", "editions", "Consultar formulário da etapa final", ["RF12"], ["ADMIN"],
   "Retorna o formulário de avaliação dos avaliadores externos.", params=["EditionId"], ok=ref("FinalForm"), errs=["404"])
op("put", "/api/admin/editions/{edition_id}/final-form", "editionsSaveFinalForm", "editions", "Estruturar formulário da etapa final", ["RF12"], ["ADMIN"],
   "Cria ou substitui título e perguntas do formulário único da edição.", params=["EditionId"], body=ref("FinalFormWrite"), ok=ref("FinalForm"), errs=["404"],
   rules=["position única no formulário.", "SCORE exige max_score > 0; TEXT exige max_score nulo.", "Proibido alterar formulário publicado que já tenha respostas."],
   conflicts=[("final_form_has_answers", "O formulário já possui respostas."), CLOSED])
op("post", "/api/admin/editions/{edition_id}/final-form/publish", "editionsPublishFinalForm", "editions", "Publicar formulário da etapa final", ["RF12"], ["ADMIN"],
   "Publica o formulário, liberando a etapa final para lançamentos.", params=["EditionId"], ok=ref("FinalForm"), errs=["404"],
   conflicts=[("final_form_empty", "O formulário não possui perguntas."), ("final_form_already_published", "O formulário já está publicado."), CLOSED])

# ---------- evaluations: vínculo de avaliadores (RF11)
op("get", "/api/admin/editions/{edition_id}/evaluators", "evaluationsListEditionEvaluators", "evaluations", "Listar avaliadores externos da edição",
   ["RF11"], ["ADMIN"], "Lista os avaliadores vinculados e suas abrangências.", params=["EditionId"], ok=arr(ref("EditionEvaluator")), errs=["404"])
op("post", "/api/admin/editions/{edition_id}/evaluators", "evaluationsLinkEditionEvaluator", "evaluations", "Vincular avaliador externo à edição",
   ["RF11"], ["ADMIN"], "Vincula um avaliador externo à edição com abrangência em todos os cursos (course_id nulo) ou em um curso.",
   params=["EditionId"], body=ref("EditionEvaluatorCreate"), ok=ref("EditionEvaluator"), ok_code="201", ok_desc="Vínculo criado.", errs=["404"],
   rules=["Uma única abrangência por avaliador em cada edição.", "A permissão expira com o encerramento da edição."],
   conflicts=[("evaluator_already_linked", "O avaliador já está vinculado a esta edição."), CLOSED], pend=["P-05"])
op("patch", "/api/admin/editions/{edition_id}/evaluators/{evaluator_id}", "evaluationsUpdateEditionEvaluator", "evaluations",
   "Alterar abrangência do avaliador na edição", ["RF11", "RFXX"], ["ADMIN"], "Altera a abrangência (curso) do avaliador na edição.",
   params=["EditionId", "EvaluatorId"], body=ref("EditionEvaluatorUpdate"), ok=ref("EditionEvaluator"), errs=["404"], conflicts=[CLOSED])

# ---------- public
op("get", "/api/public/editions/current", "publicGetCurrentEdition", "public", "Informações gerais da edição vigente", ["RF44"], [],
   "Cronograma com status de cada fase, edital, ODS habilitadas e desafios da edição vigente.", public=True, ok=ref("PublicEdition"), errs=["404"],
   rules=[EV, "phase_status é derivado das datas da etapa.", "Notícias e canal de dúvidas não estão modelados (P-35)."], pend=["P-35", "P-41"])
op("get", "/api/public/editions", "publicListClosedEditions", "public", "Listar edições encerradas", ["RF35", "RF46"], [],
   "Lista as edições encerradas para consulta do acervo.", public=True, ok=arr(ref("PublicEditionListItem")))
op("get", "/api/public/projects", "publicListProjects", "public", "Vitrine e acervo de projetos", ["RF34", "RF35", "RF45", "RF46"], [],
   "Lista a identidade pública dos projetos da edição informada (padrão: edição vigente).", public=True,
   params=["EditionFilter", "CourseFilter", "SdgFilter", "CategoryFilter", "Search"] + PAGE, ok=PPublicProject,
   rules=["Exclui equipes desclassificadas.", "Nunca retorna entregas, notas, feedbacks ou observações.",
          "Para edições encerradas, retorna apenas projetos considerados públicos (P-28)."], pend=["P-28"])
op("get", "/api/public/projects/{project_id}", "publicGetProject", "public", "Detalhe público do projeto", ["RF34", "RF45"], [],
   "Retorna a identidade pública de um projeto.", public=True, params=["ProjectId"], ok=ref("PublicProject"), errs=["404"],
   rules=["Projeto de equipe desclassificada retorna 404."])
op("get", "/api/public/editions/{edition_id}/winners", "publicListWinners", "public", "Galeria de vencedores da edição", ["RF35", "RF46"], [],
   "Pódio (1º a 3º) por curso e categoria de uma edição encerrada e homologada.", public=True, params=["EditionId"], ok=arr(ref("Winner")),
   errs=["404"], rules=["Somente edições CLOSED com resultados homologados."], pend=["P-28", "P-30"])

# ---------- teams
LEADER = "O usuário deve ser o LEADER ativo da equipe."
FORM_CLOSED = ("formation_closed", "O prazo de formação de equipes está encerrado.")
TEAM_FULL = ("team_full", "A equipe atingiu o limite máximo de integrantes.")
IN_TEAM = ("student_already_in_team", "O aluno já participa de uma equipe nesta edição.")
op("get", "/api/me/dashboard", "teamsGetStudentDashboard", "teams", "Painel do acadêmico", ["RF20", "RF51"], ["STUDENT"],
   "Informações da participação do aluno na edição vigente: equipe, projeto, cronograma, status das entregas, notas e pendências.",
   authz="Somente os dados do próprio aluno.", ok=ref("StudentDashboard"),
   rules=[EV, "incomplete_requirements reflete a verificação de fim de formação (RF51).", "Notas seguem as regras de exibição do RF32."],
   pend=["P-23", "P-27", "P-41"])
op("post", "/api/teams", "teamsCreate", "teams", "Criar equipe", ["RF21"], ["STUDENT"],
   "Cria uma equipe na edição vigente; o criador vira LEADER e o sistema gera o código da equipe.",
   body=ref("TeamCreate"), ok=ref("Team"), ok_code="201", ok_desc="Equipe criada.",
   rules=[EV, "Somente durante o prazo da etapa FORMATION.", "O aluno não pode estar em outra equipe ativa na edição.", "Nome único na edição."],
   conflicts=[FORM_CLOSED, IN_TEAM, ("team_name_taken", "Já existe equipe com este nome na edição."), ("no_current_edition", "Não há edição vigente.")],
   pend=["P-41"])
op("get", "/api/teams", "teamsListAvailable", "teams", "Consultar equipes com vagas", ["RF24"], ["STUDENT"],
   "Lista equipes ativas da edição vigente com vagas disponíveis.", params=["Search"] + PAGE, ok=PTeamListing, rules=[EV])
op("get", "/api/teams/{team_id}", "teamsGet", "teams", "Consultar equipe", ["RF13", "RF20"], ["STUDENT", "TEACHER", "ADMIN"],
   "Retorna a equipe com integrantes ativos e situação.", params=["TeamId"], ok=ref("Team"), errs=["404"],
   authz="STUDENT: integrante ativo. TEACHER: vínculo ativo com o curso do desafio do projeto da equipe. ADMIN: qualquer equipe. Sem acesso retorna 404.")
op("post", "/api/teams/{team_id}/invitations", "teamsCreateInvitation", "teams", "Enviar convite", ["RF22"], ["STUDENT"],
   "Convida um aluno (por identificador ou e-mail institucional).", params=["TeamId"], body=ref("InvitationCreate"),
   req_ex={"student_id": "5a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"}, ok=ref("Invitation"), ok_code="201", ok_desc="Convite enviado.", errs=["404"],
   authz=LEADER,
   rules=["Somente durante a formação.", "Total de integrantes atual < max_members.", "Convidado não pode estar em outra equipe da edição.",
          "Não pode haver convite PENDING para o mesmo aluno/e-mail e equipe.", "Gera notificação TEAM ao convidado quando ele já possui usuário (P-13)."],
   conflicts=[FORM_CLOSED, TEAM_FULL, IN_TEAM, ("invitation_pending_exists", "Já existe convite pendente para este aluno.")], pend=["P-13"])
op("get", "/api/teams/{team_id}/invitations", "teamsListInvitations", "teams", "Listar convites enviados pela equipe", ["RF22"], ["STUDENT"],
   "Lista os convites da equipe.", params=["TeamId", "InvitationStatusFilter"], ok=arr(ref("Invitation")), errs=["404"], authz=LEADER)
op("get", "/api/me/invitations", "teamsListMyInvitations", "teams", "Listar convites recebidos", ["RF23"], ["STUDENT"],
   "Lista os convites recebidos pelo aluno autenticado.", params=["InvitationStatusFilter"], ok=arr(ref("Invitation")),
   authz="Somente convites do próprio aluno.")
op("post", "/api/invitations/{invitation_id}/respond", "teamsRespondInvitation", "teams", "Aceitar ou recusar convite", ["RF23"], ["STUDENT"],
   "Registra a resposta ao convite.", params=["InvitationId"], body=ref("InvitationResponse"), ok=ref("Invitation"), errs=["404"],
   authz="Somente o aluno convidado.",
   rules=["Somente durante a formação e para convites PENDING.", "Ao aceitar, o aluno entra como MEMBER se houver vaga e se não estiver em outra equipe.",
          "Notifica o LEADER (TEAM).", "Convites pendentes são cancelados automaticamente ao fim da formação."],
   conflicts=[FORM_CLOSED, TEAM_FULL, IN_TEAM, ("invitation_not_pending", "O convite não está pendente.")])
op("post", "/api/teams/{team_id}/join-requests", "teamsCreateJoinRequest", "teams", "Solicitar entrada em equipe", ["RF24"], ["STUDENT"],
   "Registra solicitação de entrada.", params=["TeamId"], ok=ref("JoinRequest"), ok_code="201", ok_desc="Solicitação registrada.", errs=["404"],
   authz="Aluno sem equipe ativa na edição.",
   rules=["Somente durante a formação.", "A equipe deve ter vaga.", "Uma solicitação PENDING por aluno e equipe.", "Notifica o LEADER (TEAM)."],
   conflicts=[FORM_CLOSED, TEAM_FULL, IN_TEAM, ("join_request_pending_exists", "Já existe solicitação pendente para esta equipe.")])
op("get", "/api/me/join-requests", "teamsListMyJoinRequests", "teams", "Listar minhas solicitações de entrada", ["RF24"], ["STUDENT"],
   "Lista as solicitações do aluno autenticado.", params=["RequestStatusFilter"], ok=arr(ref("JoinRequest")), authz="Somente as próprias solicitações.")
op("get", "/api/teams/{team_id}/join-requests", "teamsListJoinRequests", "teams", "Listar solicitações recebidas pela equipe", ["RF25"], ["STUDENT"],
   "Lista as solicitações de entrada da equipe.", params=["TeamId", "RequestStatusFilter"], ok=arr(ref("JoinRequest")), errs=["404"], authz=LEADER)
op("post", "/api/join-requests/{join_request_id}/respond", "teamsRespondJoinRequest", "teams", "Aprovar ou recusar solicitação de entrada", ["RF25"],
   ["STUDENT"], "Registra a decisão do líder.", params=["JoinRequestId"], body=ref("JoinRequestDecision"), ok=ref("JoinRequest"), errs=["404"],
   authz="LEADER ativo da equipe da solicitação.",
   rules=["Somente durante a formação e para solicitações PENDING.", "Na aprovação, o aluno entra como MEMBER se houver vaga.", "Notifica o solicitante (TEAM)."],
   conflicts=[FORM_CLOSED, TEAM_FULL, IN_TEAM, ("join_request_not_pending", "A solicitação não está pendente.")])
op("post", "/api/teams/{team_id}/leave", "teamsLeave", "teams", "Sair da equipe", ["RF26"], ["STUDENT"],
   "Encerra o vínculo do próprio aluno (left_at preenchido, active=false), preservando o histórico.", params=["TeamId"],
   ok_code="204", ok_desc="Saída registrada.", errs=["404"], authz="Somente o próprio integrante ativo.",
   rules=["Somente durante a formação; depois disso a composição é congelada.", "O LEADER deve transferir a liderança antes (RF27).",
          "Se o curso do desafio ficar sem representante, a seleção do desafio deve ser invalidada (P-25)."],
   conflicts=[FORM_CLOSED, ("leader_must_transfer", "Transfira a liderança antes de sair da equipe.")], pend=["P-25"])
op("post", "/api/teams/{team_id}/leadership-transfer", "teamsTransferLeadership", "teams", "Transferir liderança", ["RF27"], ["STUDENT"],
   "Transfere o papel LEADER para outro integrante ativo.", params=["TeamId"], body=ref("LeadershipTransfer"), ok=ref("Team"), errs=["404"],
   authz=LEADER, rules=["O destinatário deve ser integrante ativo da equipe (400 caso contrário).", "Registra a transferência e notifica o novo líder (TEAM)."],
   conflicts=[CLOSED, ("team_disqualified", "A equipe está desclassificada.")])
op("post", "/api/teams/{team_id}/leadership-requests", "teamsCreateLeadershipRequest", "teams", "Solicitar liderança de equipe sem líder", ["RF28"],
   ["STUDENT"], "Registra pedido para assumir a liderança, a ser decidido por professor do curso do desafio.", params=["TeamId"],
   body=ref("LeadershipRequestCreate"), ok=ref("LeadershipRequest"), ok_code="201", ok_desc="Solicitação registrada.", errs=["404"],
   authz="Integrante ativo da equipe.",
   rules=["Somente quando a equipe não possui LEADER ativo.", "No máximo uma solicitação PENDING por equipe.", "Permitida após a formação se a equipe estiver ativa."],
   conflicts=[("team_has_leader", "A equipe já possui líder ativo."), ("leadership_request_pending_exists", "Já existe solicitação pendente."), CLOSED],
   pend=["P-24"])
op("get", "/api/teams/{team_id}/leadership-requests", "teamsListLeadershipRequests", "teams", "Listar solicitações de liderança da equipe", ["RF28"],
   ["STUDENT"], "Lista o histórico de solicitações de liderança.", params=["TeamId"], ok=arr(ref("LeadershipRequest")), errs=["404"],
   authz="Integrante ativo da equipe.")
op("get", "/api/teacher/leadership-requests", "teamsListTeacherLeadershipRequests", "teams", "Listar solicitações de liderança dos meus cursos",
   ["RF40"], ["TEACHER"], "Lista solicitações das equipes cujo desafio pertence a cursos com vínculo ativo do professor.",
   params=["RequestStatusFilter"] + PAGE, ok=PLeader, authz="Somente cursos com vínculo ativo em teacher_course.")
op("post", "/api/leadership-requests/{leadership_request_id}/decide", "teamsDecideLeadershipRequest", "teams", "Aprovar ou recusar solicitação de liderança",
   ["RF28", "RF40"], ["TEACHER"], "Registra a decisão do professor; na aprovação o solicitante vira LEADER.",
   params=["LeadershipRequestId"], body=ref("LeadershipDecision"), ok=ref("LeadershipRequest"), errs=["404"],
   authz="Professor com vínculo ativo no curso do desafio do projeto da equipe.",
   rules=["Registra professor, data e hora.", "Recusa mantém a equipe sem líder; nova solicitação pode ser feita depois.", "Notifica o solicitante (TEAM)."],
   conflicts=[("leadership_request_not_pending", "A solicitação não está pendente."), ("team_has_leader", "A equipe já possui líder ativo.")],
   pend=["P-24"])
op("post", "/api/teams/{team_id}/member-notes", "teamsCreateMemberNote", "teams", "Registrar observação sobre integrante", ["RF33"], ["STUDENT"],
   "Registra observação confidencial sobre um integrante.", params=["TeamId"], body=ref("MemberNoteCreate"), ok=ref("MemberNoteCreated"),
   ok_code="201", ok_desc="Observação registrada.", errs=["404"], authz=LEADER,
   rules=["O integrante deve pertencer à equipe.", "O conteúdo não é retornado nem consultável pelo líder ou pelos alunos."])
op("get", "/api/teams/{team_id}/member-notes", "teamsListMemberNotes", "teams", "Consultar observações sobre integrantes", ["RF39"], ["TEACHER", "ADMIN"],
   "Lista as observações registradas pelo líder.", params=["TeamId"], ok=arr(ref("MemberNote")), errs=["404"],
   authz="TEACHER com vínculo ativo no curso do desafio do projeto; ADMIN.")
op("get", "/api/admin/teams", "teamsAdminList", "teams", "Listar equipes (administração)", ["RF13"], ["ADMIN"], "Lista equipes com situação.",
   params=["EditionFilter", "TeamStatusFilter", "Search"] + PAGE, ok=PAdminTeam)
op("post", "/api/admin/teams/{team_id}/disqualify", "teamsDisqualify", "teams", "Desclassificar equipe", ["RF13"], ["ADMIN"],
   "Aplica a desclassificação formal com justificativa.", params=["TeamId"], body=ref("TeamDisqualify"), ok=ref("Team"), errs=["404"],
   rules=["A equipe deixa de enviar entregas, fica fora de finalistas, ranking e certificados e some da vitrine pública.",
          "Data e responsável não são persistidos no modelo atual (P-22)."],
   conflicts=[("team_already_disqualified", "A equipe já está desclassificada."), CLOSED], pend=["P-22"])

# ---------- projects
op("get", "/api/teams/{team_id}/project/options", "projectsGetOptions", "projects", "Desafios e categorias elegíveis", ["RF29", "RF50"], ["STUDENT"],
   "Lista os desafios ativos dos cursos dos integrantes ativos e as categorias ativas da edição.", params=["TeamId"], ok=ref("ProjectOptions"), errs=["404"],
   authz="Integrante ativo da equipe.")
op("get", "/api/teams/{team_id}/project", "projectsGetTeamProject", "projects", "Consultar projeto da equipe", ["RF30", "RF20"], ["STUDENT", "TEACHER", "ADMIN"],
   "Retorna o projeto da equipe.", params=["TeamId"], ok=ref("Project"), errs=["404"],
   authz="STUDENT: integrante ativo. TEACHER: vínculo ativo com o curso do desafio. ADMIN: qualquer.")
op("put", "/api/teams/{team_id}/project", "projectsSaveTeamProject", "projects", "Cadastrar ou atualizar projeto (desafio, categoria e dados)",
   ["RF29", "RF30", "RF50"], ["STUDENT"],
   "Cria ou atualiza o projeto em uma única operação, pois o modelo exige desafio, título e resumo juntos (P-25).",
   params=["TeamId"], body=ref("ProjectWrite"), ok=ref("Project"), ok_desc="Projeto atualizado.", errs=["404"], authz=LEADER,
   more={"201": {"description": "Projeto criado.", "content": {"application/json": {"schema": ref("Project")}}}},
   rules=["Somente durante a formação; depois os dados ficam congelados.", "Desafio deve pertencer a curso de integrante ativo (400 challenge_not_eligible).",
          "Categoria ativa da edição (400 category_not_available).", "A ODS e o curso do desafio são vinculados automaticamente.",
          "Título único na edição, ignorando maiúsculas/minúsculas e espaços extras."],
   conflicts=[FORM_CLOSED, ("project_title_taken", "Já existe projeto com título equivalente nesta edição.")], pend=["P-25"])
op("get", "/api/projects/{project_id}/deliverables", "projectsListDeliverables", "projects", "Consultar entregas do projeto por etapa", ["RF31", "RF38"],
   ["STUDENT", "TEACHER", "ADMIN"], "Retorna, por etapa com campos de entrega, os campos exigidos, o status e o histórico de versões.",
   params=["ProjectId"], ok=arr(ref("StageDeliverable")), errs=["404"],
   authz="STUDENT: integrante ativo da equipe. TEACHER: vínculo ativo com o curso do desafio. ADMIN: qualquer.", pend=["P-27"])
op("post", "/api/projects/{project_id}/stages/{stage_id}/versions", "projectsSubmitDeliverableVersion", "projects", "Enviar ou atualizar entrega da etapa",
   ["RF31"], ["STUDENT"], "Registra nova versão imutável da entrega e gera o comprovante. A confirmação prévia é responsabilidade do frontend.",
   params=["ProjectId", "StageId"], body=ref("DeliverableSubmission"), ct="multipart/form-data", ok=ref("DeliverableVersion"), ok_code="201",
   ok_desc="Versão registrada.", errs=["404"], authz=LEADER,
   rules=["Somente dentro do prazo da etapa.", "Todos os campos obrigatórios preenchidos e válidos (formatos e tamanho máximo).",
          "Cada envio cria version_number sequencial; versões anteriores são preservadas.", "Equipe desclassificada ou incompleta não envia (P-23)."],
   conflicts=[("stage_deadline_closed", "O prazo da etapa está encerrado."), ("team_disqualified", "A equipe está desclassificada."),
              ("team_incomplete", "Equipes incompletas não podem realizar entregas."), CLOSED], pend=["P-23", "P-43"])
op("get", "/api/deliverable-versions/{version_id}/receipt", "projectsGetReceipt", "projects", "Consultar comprovante de envio", ["RF31"], ["STUDENT", "ADMIN"],
   "Retorna o comprovante digital da versão.", params=["VersionId"], ok=ref("Receipt"), errs=["404"],
   authz="STUDENT: integrante ativo da equipe do projeto. ADMIN: qualquer.")

# ---------- evaluations
op("get", "/api/teacher/projects", "evaluationsListTeacherProjects", "evaluations", "Painel de acompanhamento do curso", ["RF37"], ["TEACHER"],
   "Lista os projetos dos cursos com vínculo ativo do professor, com status das entregas e das avaliações.",
   params=["CourseFilter", "StageFilter", "PendingOnly"] + PAGE, ok=PTeacherRow,
   authz="Somente projetos cujo desafio pertence a curso com vínculo ativo do professor. Não há atribuição individual de projetos.")
op("get", "/api/projects/{project_id}/stages/{stage_id}/evaluation", "evaluationsGetMyEvaluation", "evaluations", "Formulário e avaliação do professor",
   ["RF38"], ["TEACHER"], "Retorna critérios e pontuações máximas da etapa e a avaliação do professor autenticado, se existir.",
   params=["ProjectId", "StageId"], ok=ref("EvaluationForm"), errs=["404"], authz="Vínculo ativo com o curso do desafio do projeto.")
op("put", "/api/projects/{project_id}/stages/{stage_id}/evaluation", "evaluationsSaveMyEvaluation", "evaluations", "Salvar avaliação da entrega",
   ["RF38"], ["TEACHER"], "Cria ou atualiza a avaliação do professor autenticado (uma por professor, projeto e etapa).",
   params=["ProjectId", "StageId"], body=ref("EvaluationWrite"), ok=ref("Evaluation"), errs=["404"], authz="Vínculo ativo com o curso do desafio do projeto.",
   rules=["Somente etapas pontuadas do tipo EVALUATION.", "0 ≤ points ≤ max_score do critério (400 points_out_of_range).",
          "FINALIZED exige todos os critérios e torna a avaliação imutável; retificação é escopo do RF14 (P-21).",
          "Ao finalizar, recalcula stage_score (média simples; FINALIZED quando evaluation_count ≥ min_evaluators).",
          "Respeita o prazo de avaliação (P-19)."],
   conflicts=[("evaluation_already_finalized", "A avaliação já foi finalizada."), ("evaluation_period_closed", "O prazo de avaliação está encerrado."), CLOSED],
   pend=["P-19", "P-21", "P-33"])
op("get", "/api/projects/{project_id}/scores", "evaluationsGetProjectScores", "evaluations", "Notas e feedbacks das etapas", ["RF32"],
   ["STUDENT", "TEACHER", "ADMIN"], "Retorna, por etapa pontuada, nota, status, média por critério e feedbacks dos professores.",
   params=["ProjectId"], ok=ref("ProjectScores"), errs=["404"],
   authz="STUDENT: integrante ativo da equipe. TEACHER: vínculo ativo com o curso do desafio. ADMIN: qualquer.",
   rules=["Nota = média aritmética das avaliações finalizadas.", "Abaixo de min_evaluators, status PENDING e valor oculto.",
          "Sem entrega no prazo, nota zero.", "Avaliações finais de avaliadores externos não aparecem."],
   pend=["P-27", "P-33", "P-44"])
op("get", "/api/evaluator/finalists", "evaluationsListFinalists", "evaluations", "Painel de projetos finalistas", ["RF42"], ["EXTERNAL_EVALUATOR"],
   "Lista os projetos finalistas dentro da abrangência do avaliador, com sua situação de avaliação.",
   params=["CourseFilter", "CategoryFilter"] + PAGE, ok=PFinalist,
   authz="Avaliador vinculado à edição vigente (edition_evaluator) e restrito ao curso da abrangência.",
   rules=["Disponível somente com o formulário final publicado e a edição não encerrada.", "Não exibe notas internas das etapas anteriores."],
   conflicts=[("final_form_not_published", "O formulário da etapa final ainda não foi publicado.")], pend=["P-29", "P-32"])
op("get", "/api/evaluator/finalists/{project_id}/final-evaluation", "evaluationsGetFinalEvaluation", "evaluations", "Formulário e avaliação final do projeto",
   ["RF43"], ["EXTERNAL_EVALUATOR"], "Retorna o formulário publicado e a avaliação do avaliador autenticado, se existir.",
   params=["ProjectId"], ok=ref("FinalEvaluationForm"), errs=["404"], authz="Projeto finalista dentro da abrangência do avaliador.")
op("put", "/api/evaluator/finalists/{project_id}/final-evaluation", "evaluationsSaveFinalEvaluation", "evaluations", "Avaliar projeto finalista",
   ["RF43"], ["EXTERNAL_EVALUATOR"], "Cria ou atualiza a avaliação final do avaliador autenticado (uma por avaliador e projeto).",
   params=["ProjectId"], body=ref("FinalEvaluationWrite"), ok=ref("FinalEvaluation"), errs=["404"],
   authz="Projeto finalista dentro da abrangência do avaliador.",
   rules=["SCORE exige value entre 0 e max_score; TEXT exige answer_text.", "FINALIZED exige resposta para todas as perguntas e torna a avaliação imutável.",
          "Notas alimentam apenas a premiação; não alteram a nota acadêmica."],
   conflicts=[("final_evaluation_already_finalized", "A avaliação final já foi finalizada."), CLOSED], pend=["P-30"])

# ---------- results
op("get", "/api/admin/editions/{edition_id}/certificate-templates", "resultsListCertificateTemplates", "results", "Listar modelos de certificado",
   ["RF17"], ["ADMIN"], "Lista os modelos de certificado da edição.", params=["EditionId"], ok=arr(ref("CertificateTemplate")), errs=["404"], pend=["P-34"])
op("put", "/api/admin/editions/{edition_id}/certificate-templates/{certificate_type}", "resultsSaveCertificateTemplate", "results",
   "Configurar modelo de certificado", ["RF17"], ["ADMIN"], "Cria ou substitui o modelo de um tipo de certificado (um por tipo e edição).",
   params=["EditionId", "CertificateTypePath"], body=ref("CertificateTemplateWrite"), ct="multipart/form-data", ok=ref("CertificateTemplate"), errs=["404"],
   pend=["P-34", "P-43"])
op("get", "/api/me/certificates", "resultsListMyCertificates", "results", "Listar meus certificados", ["RF17"], ALL,
   "Lista os certificados emitidos para o usuário autenticado, com link para o PDF.", ok=arr(ref("Certificate")),
   authz="Somente certificados do próprio usuário; preservados mesmo com a conta desativada.")

# ---------- support
op("post", "/api/support/tickets", "supportCreateTicket", "support", "Abrir chamado de correção cadastral", ["RFXX"], ["STUDENT", "TEACHER"],
   "Abre chamado vinculado ao usuário autenticado; não altera o cadastro.", body=ref("SupportTicketCreate"), ok=ref("SupportTicket"),
   ok_code="201", ok_desc="Chamado aberto.", rules=["Status inicial OPEN; prioridade inicial MEDIUM.", "O solicitante sempre é o usuário do token."],
   pend=["P-06", "P-09", "P-10", "P-11"])
op("get", "/api/support/tickets", "supportListMyTickets", "support", "Listar meus chamados", ["RFXX"], ["STUDENT", "TEACHER"],
   "Lista os chamados do usuário autenticado.", params=["TicketStatusFilter"] + PAGE, ok=PTicket, authz="Somente os próprios chamados.")
op("get", "/api/support/tickets/{ticket_id}", "supportGetMyTicket", "support", "Consultar meu chamado", ["RFXX"], ["STUDENT", "TEACHER"],
   "Retorna um chamado do usuário autenticado, incluindo a resposta do administrador.", params=["TicketId"], ok=ref("SupportTicket"), errs=["404"],
   authz="Somente o solicitante; chamado de outro usuário retorna 404.")
op("get", "/api/admin/support/tickets", "supportAdminListTickets", "support", "Listar chamados (administração)", ["RFXX"], ["ADMIN"],
   "Lista chamados de todos os usuários.", params=["TicketStatusFilter", "TicketPriorityFilter", "AssignedToFilter", "Search"] + PAGE, ok=PTicketAdmin)
op("get", "/api/admin/support/tickets/{ticket_id}", "supportAdminGetTicket", "support", "Consultar chamado (administração)", ["RFXX"], ["ADMIN"],
   "Retorna um chamado para análise.", params=["TicketId"], ok=ref("SupportTicketAdmin"), errs=["404"])
op("patch", "/api/admin/support/tickets/{ticket_id}", "supportAdminUpdateTicket", "support", "Atender chamado", ["RFXX"], ["ADMIN"],
   "Atualiza status, prioridade, responsável e resposta do chamado.", params=["TicketId"], body=ref("SupportTicketAdminUpdate"),
   ok=ref("SupportTicketAdmin"), errs=["404"],
   rules=["Transições de status pendentes (P-06).", "Encerramento equivalente a recusa exige support_response (P-06/P-07).",
          "A correção cadastral é feita pelas rotas administrativas de usuários.", "Notifica o solicitante (SYSTEM)."],
   conflicts=[("invalid_status_transition", "Transição de status não permitida.")], pend=["P-06", "P-07", "P-08", "P-10", "P-12"])

# ---------- notifications
op("get", "/api/notifications", "notificationsList", "notifications", "Listar minhas notificações", ["RF22", "RF23", "RF24", "RF25", "RF27", "RF28"], ALL,
   "Lista as notificações do painel do usuário autenticado, das mais recentes para as mais antigas.", params=["UnreadOnly"] + PAGE, ok=PNotif,
   authz="Somente as próprias notificações.", pend=["P-14"])
op("post", "/api/notifications/{notification_id}/read", "notificationsMarkRead", "notifications", "Marcar notificação como lida",
   ["RF22", "RF23", "RF24", "RF25", "RF27", "RF28"], ALL, "Preenche read_at (idempotente).", params=["NotificationId"], ok=ref("Notification"), errs=["404"],
   authz="Somente notificações do próprio usuário; de outro usuário retorna 404.")

# ============================================================== document
def err_example(code, msg, details=None):
    return {"error": {"code": code, "message": msg, "details": details}}
spec = {
    "openapi": "3.1.0",
    "info": {
        "title": "Projeto X (Desafio X) — API",
        "version": "0.1.0",
        "description": "\n".join([
            "API REST da plataforma do Projeto X (Desafio X) da UniCatólica.",
            "",
            "Fonte de dados: DBML aprovado (nomes e enums em inglês). Os perfis são STUDENT, TEACHER, EXTERNAL_EVALUATOR e ADMIN (enum user_role).",
            "",
            "**Autenticação:** alunos e professores entram com a Microsoft; administradores e avaliadores externos, com e-mail e senha. Rotas protegidas usam Bearer JWT.",
            "",
            "**Convenções propostas (pendentes de aprovação):** formato de erro `Error` (P-37), paginação `page`/`page_size` (P-38), decimais como string (P-39).",
            "",
            "Cada operação informa o status (`x-status`: `confirmed` ou `proposed`), os requisitos (`x-requirements`), os perfis (`x-roles`) e as pendências (`x-pendencias`) registradas em api-pendencias.md. Operações `proposed` dependem de uma pendência de severidade alta.",
        ]),
    },
    "servers": [{"url": "http://localhost:8000", "description": "Ambiente local de desenvolvimento"}],
    "security": [{"bearerAuth": []}],
    "tags": [
        {"name": "auth", "description": "Autenticação, sessões e autocadastro."},
        {"name": "accounts", "description": "Gerenciamento administrativo de usuários e perfis."},
        {"name": "core", "description": "Cursos e ODS."},
        {"name": "editions", "description": "Edições, desafios, categorias, etapas, critérios e formulário final."},
        {"name": "teams", "description": "Equipes, integrantes, convites, solicitações e observações."},
        {"name": "projects", "description": "Projetos, entregas, versões e comprovantes."},
        {"name": "evaluations", "description": "Avaliações acadêmicas, notas e avaliação final."},
        {"name": "results", "description": "Certificados."},
        {"name": "support", "description": "Chamados de correção cadastral."},
        {"name": "notifications", "description": "Notificações do painel."},
        {"name": "public", "description": "Painel público (sem autenticação)."},
    ],
    "paths": dict(sorted(PATHS.items())),
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT",
                                           "description": "JWT da aplicação emitido pelas rotas de sessão."}},
        "parameters": PARAMS,
        "responses": {
            "BadRequest": {"description": "Requisição inválida.", "content": {"application/json": {"schema": ref("Error"),
                           "example": err_example("validation_error", "Dados inválidos.", {"title": ["Este campo é obrigatório."]})}}},
            "Unauthorized": {"description": "Autenticação ausente, inválida ou expirada.", "content": {"application/json": {"schema": ref("Error"),
                             "example": err_example("not_authenticated", "Credenciais de autenticação inválidas ou ausentes.")}}},
            "Forbidden": {"description": "Usuário autenticado sem permissão para a operação.", "content": {"application/json": {"schema": ref("Error"),
                          "example": err_example("permission_denied", "Você não tem permissão para executar esta operação.")}}},
            "NotFound": {"description": "Recurso inexistente ou inacessível ao usuário.", "content": {"application/json": {"schema": ref("Error"),
                         "example": err_example("not_found", "Recurso não encontrado.")}}},
        },
        "schemas": SC,
    },
}

class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data): return True
def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)
Dumper.add_representer(str, str_presenter)

with open("openapi.yaml", "w", encoding="utf-8") as f:
    yaml.dump(spec, f, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120)
print("operations:", len(OPIDS), "paths:", len(PATHS), "schemas:", len(SC))
