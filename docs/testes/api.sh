# Funcoes de apoio para os roteiros (Git Bash). Uso:
#   source docs/testes/api.sh            # B=http://127.0.0.1:8000 por padrao
#   login admin.jar admin@desafiox.local 'SuaSenha!2026'
#   api admin.jar GET /api/admin/courses
#   api admin.jar POST /api/admin/courses -d '{"name":"Curso X","term_count":8}'
#   upload aluno.jar POST /api/projects/1/stages/3/versions -F 'items=[...]' -F 'files[]=@arquivo.pdf'
#   sessao aluno.jar <sessionid>         # usa a sessao impressa pelo cenario (force_login)
# Cada arquivo .jar guarda os cookies (sessionid e csrftoken) de um perfil.
B=${B:-http://127.0.0.1:8000}

_csrf() { awk '$6=="csrftoken"{print $7}' "$1"; }

# api <jar> <METODO> <rota> [opcoes do curl]: JSON, com o X-CSRFToken do jar.
api() {
  local jar=$1 method=$2 path=$3; shift 3
  curl -s -m 30 -b "$jar" -c "$jar" -X "$method" -H "X-CSRFToken: $(_csrf "$jar")" \
    -H "Content-Type: application/json" "$@" -w '\n[HTTP %{http_code}]\n' "$B$path"
}

# upload <jar> <METODO> <rota> -F ...: multipart (o curl monta o Content-Type).
upload() {
  local jar=$1 method=$2 path=$3; shift 3
  curl -s -m 30 -b "$jar" -c "$jar" -X "$method" -H "X-CSRFToken: $(_csrf "$jar")" \
    "$@" -w '\n[HTTP %{http_code}]\n' "$B$path"
}

# login <jar> <email> <senha>: pega o CSRF e abre a sessao por senha.
login() {
  rm -f "$1"
  curl -s -m 30 -c "$1" -b "$1" "$B/api/auth/csrf" > /dev/null
  api "$1" POST /api/auth/sessions/password -d "{\"email\":\"$2\",\"password\":\"$3\"}"
}

# sessao <jar> <sessionid>: monta o jar com a sessao do force_login e pega o CSRF.
sessao() {
  local host=${B#*://}; host=${host%%:*}
  printf '%s\tFALSE\t/\tFALSE\t0\tsessionid\t%s\n' "$host" "$2" > "$1"
  curl -s -m 30 -c "$1" -b "$1" "$B/api/auth/csrf" > /dev/null
  api "$1" GET /api/auth/me
}
