# Volleyball RSVP

Preprosta aplikacija za prijavo na naslednji termin odbojke.

## Funkcije

- prikaz naslednjega termina
- lokacija, ura, minimum igralcev in rok prijave
- RSVP brez prijave:
  - Igram
  - Samo na pijačo
  - Ne pridem
- opcijska opomba
- ponovna sprememba lastnega odgovora na istem brskalniku
- admin prijava
- admin lahko ustvari/uredi/zaključi termin
- admin lahko briše prijave
- arhiv terminov se hrani v SQLite
- mobile-first UI

## Hiter zagon

1. Kopiraj `.env.example` v `.env`
2. Nastavi močno admin geslo in SECRET_KEY
3. Zaženi:

```bash
docker compose up -d --build
```

4. Odpri:

```text
http://NAS_IP:8080
```

Admin:

```text
http://NAS_IP:8080/admin
```

## Synology

V Container Managerju uvozi projekt oziroma ga zaženi z Docker Compose.

Priporočena javna postavitev:

```text
Internet
  |
HTTPS 443
  |
Synology Reverse Proxy
  |
127.0.0.1:8080
  |
Frontend nginx
  |-- /      React
  |-- /api   FastAPI
```

Navzven ne odpiraj porta 8080. V usmerjevalniku odpri samo 443 proti Synologyju.

Za domeno npr.:

```text
odbojka.example.si
```

v Synology Reverse Proxy nastavi:
- Source: HTTPS / odbojka.example.si / 443
- Destination: HTTP / localhost / 8080

Nato domeni dodeli Let's Encrypt certifikat.

## Varnost

Pred javno objavo OBVEZNO spremeni:
- ADMIN_PASSWORD
- SECRET_KEY

Backend ni neposredno izpostavljen internetu; dosegljiv je samo prek nginx `/api`.

SQLite datoteka je v Docker volume `volleyball_data`.

## Lokalni razvoj

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

V Vite development načinu se `/api` proxya na `http://localhost:8000`.
