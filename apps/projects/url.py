#POST	/api/projects/	Criar um projeto
#GET	/api/projects/	Listar projetos
#GET	/api/projects/{id}/	Visualizar um projeto
#PATCH	/api/projects/{id}/	Atualizar um projeto
#DELETE	/api/projects/{id}/	Excluir um projeto

#POST	/api/projects/{id}/submissions/	Criar uma entrega vinculada ao projeto
#GET	/api/projects/{id}/submissions/	Listar as entregas do projeto
#GET	/api/submissions/{id}/	Consultar uma entrega
#GET	/api/submissions/{id}/versions/	Consultar o histórico de versões
#POST	/api/submissions/{id}/versions/	Registrar uma nova versão
#GET	/api/submissions/{id}/valid-version/	Consultar a versão válida calculada