import { useRef, type KeyboardEvent } from 'react'
import config from './privacy-config.json'

export function PrivacyFooter() {
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)

  const previousOverflow = useRef('')

  function trapFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return
    const targets = event.currentTarget.querySelectorAll<HTMLElement>('button, [tabindex="0"]')
    const first = targets[0]
    const last = targets[targets.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }

  function close() {
    document.body.style.overflow = previousOverflow.current
    trigger.current?.focus()
  }

  return <footer className="privacy-footer">
    <button ref={trigger} className="privacy-link" type="button" aria-haspopup="dialog" onClick={() => {
      previousOverflow.current = document.body.style.overflow
      dialog.current?.showModal()
      document.body.style.overflow = 'hidden'
    }}>Zasebnost</button>
    <dialog ref={dialog} className="privacy-dialog" aria-labelledby="privacy-title" onClose={close} onKeyDown={trapFocus}>
      <div className="privacy-header">
        <h2 id="privacy-title">Zasebnost</h2>
        <button type="button" className="secondary" autoFocus onClick={() => dialog.current?.close()}>Zapri</button>
      </div>
      <div className="privacy-content" tabIndex={0} aria-label="Obvestilo o zasebnosti">
        <p>Ta spletna stran je namenjena organizaciji rekreativne odbojke znotraj zasebne skupine prijateljev.</p>
        <h3>Katere podatke zbiramo?</h3>
        <ul>
          <li>Ime oziroma vzdevek udeleženca.</li>
          <li>Status udeležbe na posameznem terminu.</li>
          <li>Morebitno prostovoljno vneseno opombo.</li>
          <li>Tehnične identifikatorje prijave in termina, žeton za urejanje odgovora ter čas nastanka in zadnje spremembe prijave.</li>
        </ul>
        <p>V opombo vnesi samo podatke, ki jih želiš deliti s skupino.</p>
        <h3>Kako uporabljamo podatke?</h3>
        <p>Podatke uporabljamo za organizacijo odbojkarskih srečanj, prikaz prijavljenih udeležencev in urejanje odgovorov.</p>
        <h3>Kdo lahko vidi podatke?</h3>
        <p>Prijave na trenutni termin lahko vidijo osebe z dostopnim geslom. Organizator z administratorskim dostopom lahko vidi tudi arhiv, ureja in briše prijave. Geslo je namenjeno samo članom zasebne skupine in ga ne deli naprej.</p>
        <h3>Kako dolgo hranimo podatke?</h3>
        <p>{config.retentionPolicy || 'Rok hrambe še ni potrjen. Aplikacija trenutno hrani tudi pretekle termine in njihove prijave ter jih ne briše samodejno. Administrator mora pred uvedbo tega obvestila potrditi rok in način brisanja, tudi za varnostne kopije.'}</p>
        <p>Aplikacija prijav ob objavi naslednjega termina trenutno ne izbriše samodejno, ampak jih ohrani v arhivu. Za izbris v dogovorjenem roku mora poskrbeti organizator. Rok izbrisa iz varnostnih kopij mora administrator še potrditi.</p>
        <h3>Popravek ali izbris podatkov</h3>
        <p>Za popravek ali izbris podatkov se obrni na organizatorja srečanj.</p>
        <p>{config.organizerContact ? `Kontakt organizatorja: ${config.organizerContact}` : 'Kontakt organizatorja: čaka na potrditev administratorja.'}</p>
        <h3>Piškotki in shranjevanje v brskalniku</h3>
        <p>Za dostop uporabljamo nujni piškotek <code>site_access</code>, ki velja 12 ur. Vsebuje podpisan dostopni žeton, ne gesla, in ni dostopen JavaScriptu.</p>
        <p>V <code>localStorage</code> shranimo ime, status, opombo in žeton za ponovno urejanje odgovora za posamezni termin. Ti podatki nimajo samodejnega roka izteka in ostanejo do brisanja podatkov spletnega mesta v brskalniku. Brisanje v brskalniku ne izbriše prijave na strežniku.</p>
        <p>Pri administratorski prijavi shranimo dostopni žeton v <code>sessionStorage</code>, praviloma do zaprtja zavihka oziroma odjave; žeton velja največ 12 ur.</p>
        <p>Aplikacija ne vključuje zunanje analitike, oglaševalskih piškotkov ali sledilnikov.</p>
        <h3>Tehnični dnevniki</h3>
        <p>Spletni strežnik lahko v dnevnikih dostopa beleži naslov IP, čas in zahtevano pot ter podatke o brskalniku. Dejanski rok hrambe dnevnikov in morebitnih varnostnih kopij mora potrditi administrator.</p>
      </div>
    </dialog>
  </footer>
}
