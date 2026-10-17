# Guia de Configuração e Execução do Projeto

Este documento contém todo o passo a passo necessário para preparar o ambiente de desenvolvimento e executar a aplicação pela primeira vez.

---

## 1. Pré-requisitos de Sistema

Antes de começar, certifique-se de ter os seguintes recursos instalados na sua máquina.

### 1.1. Python 3.12+

- Baixe e instale a versão oficial em [python.org]

```
python --version
```

### 1.2. pip e uv (Gerenciador de Pacotes)

O `pip` já vem instalado com o Python. Certifique-se de que está atualizado:

```
python -m pip install --upgrade pip
```

Instale o **uv**, gerenciador de dependências de alta performance para Python:

```
pip install uv
```

### 1.3. Docker Desktop

- Baixe e instale o [Docker Desktop](https://www.docker.com/).
- Crie uma conta no Docker Hub, se necessário.
- Certifique-se de que a engine do Docker está rodando e que o suporte ao `docker compose` está habilitado.
- Verifique a instalação no terminal:

```
docker --version
docker compose version
```

### 1.4. Git

- Baixe e instale o Git em [git-scm.com](https://git-scm.com/).

---

## ⚙️ 2. Passo a Passo para Executar o Projeto

### Passo 1: Clonar o Repositório

Clone o repositório e acesse a pasta do projeto:

```
git clone <URL_DO_REPOSITORIO>
```

Substitua `<URL_DO_REPOSITORIO>` pela URL real do repositório.

---

### Passo 2: Configurar o Arquivo `.env`

Crie um arquivo chamado `.env` na raiz do projeto, no mesmo nível dos arquivos `manage.py` e `docker-compose.yaml`.

**1. Gere uma chave secreta exclusiva do Django:**

```
python -c "import django.core.management.utils; print(django.core.management.utils.get_random_secret_key())"
```

**2. Abra o arquivo `.env` e configure as variáveis de ambiente:**

```
# Django
DJANGO_SECRET_KEY=cole_sua_chave_gerada_aqui
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
POSTGRES_DB=desafiox
POSTGRES_USER=desafiox
POSTGRES_PASSWORD=dev_password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Substitua `cole_sua_chave_gerada_aqui` pela chave gerada no comando anterior.

> **Atenção:** o arquivo `.env` contém configurações sensíveis e não deve ser enviado ao Git. Certifique-se de que ele esteja listado no `.gitignore`.

---

### Passo 3: Iniciar o Banco de Dados via Docker

Com o Docker Desktop em execução, inicie o container do PostgreSQL em segundo plano:

```
docker compose up -d
```

Para verificar se o container foi iniciado corretamente, execute:

```
docker ps
```

---

### Passo 4: Instalar e Sincronizar as Dependências com `uv`

Execute o comando abaixo para criar o ambiente virtual (`.venv`) e instalar as dependências declaradas no projeto:

```
uv sync
```

---

### Passo 5: Executar as Migrações do Banco de Dados

Aplique as migrações para criar ou atualizar as tabelas do Django no PostgreSQL:

```
python manage.py migrate
```

---

### Passo 6: Criar o Superusuário (Painel Admin)

Crie um usuário administrador para acessar o **Django Admin**:

```
python manage.py createsuperuser
```

Informe o nome de usuário, o e-mail e a senha conforme solicitado no terminal.

---

### Passo 7: Iniciar o Servidor de Desenvolvimento

Inicie o servidor local do Django:

```
python manage.py runserver
```

Após executar o comando, a aplicação estará disponível nos seguintes endereços:

- **API / Home:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Painel Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## ✅ 3. Resumo dos Comandos

Para facilitar a consulta, estes são os principais comandos necessários para configurar e executar o projeto após clonar o repositório e configurar o `.env`.

```
# Instalar dependências
uv sync

# Iniciar o banco de dados
docker compose up -d

# Aplicar migrações
python manage.py migrate

# Criar administrador (opcional, se ainda não existir)
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

**Pronto!** O ambiente estará configurado para o desenvolvimento local do Projeto X.

Observação técnica: como você está usando `uv`, também pode executar os comandos Django com `uv run`, por exemplo, `uv run python manage.py migrate` e `uv run python manage.py runserver`. Isso garante que os comandos utilizem o ambiente virtual gerenciado pelo `uv`.