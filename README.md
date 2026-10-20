# Volleyball RSVP

Preprosta aplikacija za prijavo na naslednji termin odbojke.

## Funkcije

- dostop do strani s skupnim geslom `RobiJeCar` (velja 12 ur)
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


## Ankete

Po odklepu se aktivne ankete prikažejo v vijolični kartici nad naslednjim terminom, tudi če termina ni. Če aktivnih anket ni, kartice ni. Aktivnih je lahko več anket hkrati.

Na `/admin` je razdelek **Ankete**. Administrator določi naslov, od 1 do 20 vprašanj in od 2 do 20 odgovorov na vprašanje. Po objavi so vprašanja nespremenljiva; za drugačna vprašanja objavi novo anketo. Arhiviranje skrije anketo in njene rezultate uporabnikom ter ustavi glasovanje. Administrator v arhivu vidi vprašanja, datum objave/arhiviranja ter imena, odgovore in čas oddaje.

Uporabnik vpiše ime in izbere en odgovor pri vsakem vprašanju. Normalizirano ime lahko na isto anketo odgovori enkrat. Rezultati so skupni in ne vsebujejo imen; API jih vrne šele z naključnim žetonom, izdanim ob oddaji. Žeton je shranjen v `sessionStorage`, zato so rezultati dostopni tudi po osvežitvi istega zavihka. Brez uporabniških računov ime ostaja samoprijavljeno; anketa ne preverja identitete in ne preprečuje glasovanja pod drugim imenom.

Ob zagonu se samodejno ustvarita novi tabeli `polls` in `poll_submissions`. Obstoječih tabel in podatkov se ne spreminja. Arhiviranje anket podatkov ne izbriše. Odgovori niso vezani na rok hrambe prijav na odbojko; rok hrambe arhiva anket mora določiti organizator.

Preverjanje na začasni bazi (potrebne so backend odvisnosti in `httpx`):

```sh
python -m unittest discover -s tests -p 'test_*.py'
npm --prefix frontend run build
```

Za preizkus uporabniškega vmesnika je dodan `tests/polls_browser.py` (potrebuje še Python `playwright`, Google Chrome in dovoljenje za lokalni testni strežnik). Preverja namizni in mobilni prikaz, več vprašanj, rezultate po oddaji, imena v administratorskem pregledu in arhiviranje. Med implementacijo njegov zagon ni bil dovoljen; preverjanje v brskalniku zato ostaja za izvedbo.
