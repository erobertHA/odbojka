# Pregled zasebnosti odbojkaje.top

Pregled kode in lokalni testi: 16. 10. 2026. Produkcijska namestitev, dnevniki, varnostne kopije in produkcijska baza niso bili dostopni niti spreminjani. Lokalna SQLite datoteka v projektu ni prisotna: pregledana je SQLAlchemy shema in ustvarjena ločena testna baza v začasnem imeniku. Aplikacije med pregledom ne uvažaj z nastavitvami produkcijske baze, saj ob uvozu kliče `create_all`.

## Podatki in shranjevanje

| Mesto | Podatki | Trenutna hramba |
| --- | --- | --- |
| SQLite `responses` | Ime/vzdevek, status, prostovoljna opomba, ID prijave, ID termina, žeton za urejanje, čas nastanka in spremembe | Brez samodejnega izbrisa; tudi v arhivu |
| SQLite `events` | Datum, ura, kraj, opis, minimalno število igralcev, rok prijave, aktivnost, čas nastanka | Brez samodejnega izbrisa; kraj ali opis lahko vsebujeta osebne podatke, če jih vnese organizator |
| Piškotek `site_access` | Podpisan JWT z obsegom dostopa in rokom izteka; brez gesla | 12 ur, `HttpOnly`, `SameSite=Strict`, `Path=/`; `Secure` pogojno glede na shemo/proxy |
| `localStorage`: `volleyball_rsvp_<termin>` | Ime, status, opomba zadnjega shranjenega odgovora za termin | Brez izteka; do brisanja podatkov spletnega mesta |
| `localStorage`: `volleyball_token_<termin>_<ime>` | Žeton za urejanje; tudi ime v ključu; bere se še starejši ključ brez imena | Brez izteka |
| `sessionStorage`: `admin_token` | Administratorski JWT | Do odjave/zaprtja zavihka; JWT velja 12 ur |
| Konfiguracija | Skupno geslo v kodi, admin uporabniško ime in geslo ter podpisni ključ v okolju oziroma nevarnih privzetih vrednostih | Do ročne spremembe; niso v SQLite |
| Dnevniki | Privzeti nginx/uvicorn dnevniki lahko vsebujejo IP, čas, pot, status; nginx tudi podatke o brskalniku in napotitelju | Produkcijske nastavitve in rok niso preverjeni |

Frontend uporablja lokalne datoteke in sistemske pisave; ni najdenih zunanjih analitičnih SDK-jev, oglaševanja ali sledilnikov. FastAPI dokumentacija po odklenitvi lahko nalaga Swagger/ReDoc sredstva s CDN; to ni analitika uporabniškega vmesnika, je pa zunanja zahteva. Dejanske nastavitve gostovanja, reverse proxyja in dodatnih produkcijskih storitev mora preveriti administrator. Novo obvestilo ne nalaga zunanjih sredstev in ne dodaja shranjevanja ali soglasij.

## Rok hrambe in kontakt

Administrator je v tej nalogi potrdil **hrambo prijav do naslednjega termina** in kontakt **robert.erat@gmail.com**. Vrednosti sta v `frontend/src/privacy-config.json` in sta vključeni v frontend ob buildu. `retentionPolicy` je konfiguracija besedila, ne mehanizem izbrisa.

**Odprta razlika med politiko in implementacijo:** objava naslednjega termina prejšnjega samo deaktivira. Njegove prijave ostanejo v bazi in arhivu. Obvestilo izrecno pove, da mora za izbris poskrbeti organizator. Administratorski API omogoča izbris prijave, obstoječi UI pa urejanje/brisanje prikazuje le za aktivni termin. Pred uporabo dogovorjenega roka je treba določiti izvedljiv postopek izbrisa arhivskih prijav ali posebej odobriti samodejni izbris. Ta sprememba ničesar ne briše in ne uvaja avtomatike. Rok za kopije, dnevnike in lokalno shrambo ni samodejno enak roku za prijave. Kontakt ni samodejno dokaz identitete upravljavca.

## Zaščita API-ja in ugotovljena tveganja

- Middleware preverja podpis, iztek in obseg piškotka pri vseh API poteh, tudi admin, OpenAPI in dokumentaciji; izjemi sta `/health` (samo stanje) in `/auth/unlock` (vnos gesla). Admin zahteva še ločen Bearer žeton. Lokalni testi preverijo vse registrirane zasebne poti brez piškotka, neveljaven/pretečen piškotek in napačen obseg ter uspešen dostop po odklenitvi. Na običajni poti brez veljavnih poverilnic iskalnik do zasebnih podatkov ne pride. Produkcijskega delovanja ni mogoče potrditi samo iz kode.
- **Visoka prioriteta: nevarne privzete poverilnice.** Javna privzeta vrednost `SECRET_KEY` omogoča ponarejanje dostopnih in administratorskih JWT, če ni zamenjana. Privzeto admin geslo je prav tako nevarno. Dejanske `.env` vrednosti niso bile izpisane ali spreminjane; administrator mora preveriti produkcijsko konfiguracijo. Zaščita z geslom ne odpravlja tega tveganja.
- **Visoka prioriteta: spreminjanje tujih odgovorov znotraj skupine.** RSVP ob odsotnosti ustreznega žetona poišče ujemajoče ime in prepiše odgovor ter vrne njegov žeton. Kdor pozna skupno geslo, lahko spremeni odgovor drugega člana. Ohranjen obstoječi postopek; popravek potrebuje ločeno odobritev.
- Skupno geslo je shranjeno v izvorni kodi v čisti obliki; admin geslo je v okolju in se neposredno primerja, brez hashiranja. Frontend gesli pošilja v JSON telesu POST, ne v URL; šifriranje prenosa zahteva HTTPS. Gesli nista v piškotku ali brskalniški shrambi. Skupno geslo ne identificira posameznika, v kodi ni omejevanja poskusov ali individualnega preklica seje.
- **Preveriti HTTPS/proxy:** nginx nastavi `X-Forwarded-Proto` na lastni `$scheme`. Če zunanji Synology zaključi TLS in z nginx komunicira po HTTP, se lahko izgubi izvorna HTTPS shema in piškotek ne dobi `Secure`. Dostop prek navadnega HTTP prenaša gesla brez zaščite. Dejanske verige proxyjev, preusmeritve HTTPS, zaupanja glavam in neposredne dostopnosti porta 8080 ni bilo mogoče preveriti.
- Ni eksplicitnega `Cache-Control: no-store` za zasebne API odgovore. Preveriti predpomnilnike zunanjih proxyjev/CDN. Ni dodanega `noindex`; ta ni nadomestilo za avtorizacijo. Statični frontend in obvestilo sta javno dostopna, prijave niso vgrajene v frontend.
- Aplikacija ne izpisuje teles prijav ali gesel z `print`/lastnim loggerjem. Privzeti dnevniki in napake infrastrukture lahko beležijo tehnične podatke. Preveriti rotacijo, dostop, roke in preprečiti beleženje teles, piškotkov ter `Authorization`. Ne dodajati osebnih podatkov v query string.
- Lokalni podatki in administratorski žeton so dostopni skriptam istega izvora in uporabnikom istega brskalniškega profila; zaklep strani ne izbriše prejšnjih zapisov `localStorage`.

Avtentikacija, backend, podatkovna shema in podatki so ostali nespremenjeni. Zgornja tveganja so ugotovitve, ne trditev o odpravljeni varnosti.

## Vsebinska in pravna potrditev pred uvedbo

Izjema po členu 2(2)(c) in uvodni izjavi 18 GDPR je mogoča pri izključno osebni/domači dejavnosti fizične osebe brez povezave s poklicno ali komercialno dejavnostjo. Opisana skupina prijateljev je lahko tak primer, vendar samo geslo ali zasebna oznaka ne dokazujeta izjeme. Administrator mora potrditi dejanski namen, obseg in krog prejemnikov. Ne gre za ugotovitev, da GDPR zagotovo ne velja. Vir: [GDPR, člen 2 in uvodna izjava 18](https://eur-lex.europa.eu/legal-content/EN/ALL/?tid=111403396&uri=celex%3A32016R0679).

Če GDPR velja, mora obvestilo po [13. členu GDPR](https://eur-lex.europa.eu/legal-content/EN/TXT/?qid=1731412878471&uri=CELEX%3A32016R0679) vsebovati oziroma glede na uporabo potrditi:

- identiteto in kontakt upravljavca; zastopnika in DPO, kjer sta relevantna;
- namene in pravno podlago; legitimne interese, če je podlaga člen 6(1)(f);
- prejemnike/kategorije, tudi gostovanje, ter morebitne prenose izven EGP in zaščitne ukrepe;
- rok hrambe ali merila zanj;
- pravice do dostopa, popravka, izbrisa, omejitve, ugovora in prenosljivosti glede na njihovo uporabo; preklic privolitve, če se nanjo opira obdelava;
- pravico do pritožbe pri nadzornem organu;
- obveznost ali prostovoljnost posredovanja podatkov in posledice neposredovanja;
- avtomatizirano odločanje/profiliranje, kjer obstaja, ter nove namene pred nadaljnjo obdelavo.

To je seznam za dopolnitev, ne izmišljena pravna podlaga. Modal je obvestilo za zasebno skupino, ne potrjena popolna izjava po 13. členu. Potrditi je treba tudi gostovanje, kopije, dnevnike in dejansko izvajanje izbrisa. Potrditveno polje GDPR in pasica za soglasje nista dodana; v pregledanem uporabniškem vmesniku ni nenujnih sledilnih tehnologij.

## Ponovljivi testi

Testi uporabljajo samo začasno SQLite bazo, z lastnim podpisnim ključem in admin poverilnicami. Ne uporabljajo `.env` ali produkcijskih podatkov.

```sh
python3 -m venv /tmp/volleyball-privacy-venv
/tmp/volleyball-privacy-venv/bin/pip install -r backend/requirements.txt httpx playwright
npm --prefix frontend run build
/tmp/volleyball-privacy-venv/bin/python tests/test_api_access.py
/tmp/volleyball-privacy-venv/bin/python tests/privacy_browser.py
```

Brskalniški test zahteva nameščen Google Chrome in dovoljen lokalni testni strežnik. Preveri širine 1280, 390 in 320 px, zaklenjeno/prazno/admin/aktivno stran, gumb za zapiranje, ESC, vrnitev in omejitev fokusa, pomikanje, prelivanje ter shranjevanje in spremembo RSVP. Mobilni prikaz je emulacija v Chrome, ne test na fizičnem telefonu. Produkcijska TLS/proxy konfiguracija in dostop s fizičnega telefona zahtevata ločen pregled po namestitvi.

### Rezultati tega pregleda

- Frontend `npm run build`: uspešno (TypeScript in Vite).
- `tests/test_api_access.py`: vseh 5 testov uspešnih, vključno s preverjanjem vseh registriranih zasebnih poti in obstoječega postopka RSVP.
- Prvi brskalniški test: modal se odpre, začetni fokus in prehod na besedilo delujeta; pri kroženju Tab je test zaznal prehod fokusa iz modala v vrstico brskalnika. Dodano je izrecno kroženje fokusa naprej/nazaj. Build po popravku je uspešen.
- Ponovni brskalniški test je bil zavrnjen pri zahtevi za dovoljenje lokalnega strežnika in brskalnika. Zato celoten namizni in mobilni test, ESC, povratek fokusa, pomikanje in RSVP prek brskalnika ostajajo za ponovitev. Teh preverjanj ne štejemo kot uspešno opravljenih.
- `git diff --check`: uspešno. Sprememb backend kode, sheme in produkcijskih podatkov ni.
