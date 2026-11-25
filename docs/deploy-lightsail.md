# Deploy na AWS Lightsail (#99 homologação, #102 produção)

Uma instância só, com Docker Compose: Caddy (HTTPS automático) → gunicorn → Postgres.
Arquivos: `Dockerfile`, `docker-compose.prod.yaml`, `deploy/Caddyfile`.
Testado localmente: a stack inteira usa ~140 MB de RAM em repouso.

## 1. Instância

1. Lightsail → **Create instance** → Linux/Unix → **OS Only → Ubuntu 24.04 LTS**.
2. Plano: **US$ 7 (1 GB)**. O plano gratuito da conta não libera planos maiores;
   para o de US$ 12 é preciso passar a conta para o plano pago.
3. **Networking → Create static IP** e anexe à instância (grátis enquanto anexado).
4. **Networking → IPv4 Firewall**: adicione **HTTPS (443)**. SSH (22) e HTTP (80) já vêm abertos.
5. Billing → **Budgets**: alerta em US$ 10 e US$ 25. Anote quando o plano gratuito acaba.

## 2. Preparar o servidor (SSH pelo navegador da Lightsail)

```bash
# Swap de 2 GB: o build da imagem e o Postgres não estouram a memória.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # entre de novo para valer o grupo
```

## 3. Subir

```bash
git clone https://github.com/LCapistrano25/challenge-x-api.git && cd challenge-x-api
git switch main            # homologação: developer
cp .env.example .env && nano .env
```

No `.env` de produção:

| Variável | Valor |
|---|---|
| `DOMAIN` | domínio apontado para o IP estático. Sem domínio: `<ip-com-hífens>.sslip.io`, ex. `3-15-20-7.sslip.io` |
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DJANGO_ALLOWED_HOSTS` | o mesmo valor de `DOMAIN` |
| `POSTGRES_PASSWORD` | senha forte, nova |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | origem do frontend. Homologação: `http://localhost:5173` (o front usa o proxy do Vite) |
| `EMAIL_URL` | SMTP, ex. `smtp+tls://usuario:senha@smtp.servidor.com:587`. Sem ele o e-mail só aparece em `logs api` |
| `ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES` | **só homologação**: `True` deixa aluno e professor entrarem com senha (usuários criados no admin). Em produção, não definir |
| `ENABLE_API_DOCS` | `True` na homologação: Swagger em `https://$DOMAIN/api/docs/`. Em produção, não definir |
| `MICROSOFT_*` | do app no Entra ID; `MICROSOFT_REDIRECT_URI` com o domínio do frontend |

`POSTGRES_HOST`/`POSTGRES_PORT` do `.env` são ignorados: o compose aponta para o serviço `db`.

```bash
docker compose -f docker-compose.prod.yaml up -d --build
docker compose -f docker-compose.prod.yaml logs -f api      # migrate + collectstatic + gunicorn
docker compose -f docker-compose.prod.yaml exec api python manage.py createsuperuser
```

Abra `https://$DOMAIN/admin/`. O certificado sai no primeiro acesso (precisa das portas 80 e 443 abertas).

## 4. Atualizar

```bash
git pull && docker compose -f docker-compose.prod.yaml up -d --build
```

As migrations rodam sozinhas na subida do container `api`.

## 5. Backup (#102)

Dump diário às 3h, guardando 7 dias (`crontab -e`):

```cron
0 3 * * * cd ~/challenge-x-api && docker compose -f docker-compose.prod.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > ~/backup-$(date +\%a).sql.gz
```

O dump fica no próprio disco: para sobreviver à perda da instância, ligue também
**Snapshots → Automatic snapshots** na Lightsail (cobrado por GB, centavos por mês).
Os arquivos das entregas ficam no volume `deliveries` e entram no snapshot, não no dump.
Os PDFs dos editais ficam no volume `regulations`, montado em
`REGULATION_STORAGE_ROOT=/data/regulations`. Inclua esse volume no backup.
Em homologação, publique um edital, guarde o link retornado e confira o mesmo
download após recriar o serviço `api` com o volume preservado.

Restaurar: `gunzip -c backup-Seg.sql.gz | docker compose -f docker-compose.prod.yaml exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'`.
