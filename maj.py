import re, sys
from datetime import datetime

URL = "https://lotobonheur.ci/resultats"
FICHIER = "tirages.txt"
JOURS = r"(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)"


MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def mois_precedents(n):
    from datetime import datetime
    now = datetime.utcnow()
    y, m = now.year, now.month
    out = []
    for _ in range(n):
        out.append(f"{MOIS_FR[m - 1]} {y}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


def defiler(page):
    page.wait_for_timeout(4000)
    for _ in range(10):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(700)


def choisir(page, libelle):
    for sel in page.locator("select").all():
        try:
            sel.select_option(label=libelle, timeout=2000)
            return True
        except Exception:
            pass
    try:
        page.get_by_text("Choisir...", exact=False).first.click(timeout=6000)
        page.wait_for_timeout(600)
        page.get_by_text(libelle, exact=True).first.click(timeout=6000)
        return True
    except Exception as e:
        print("Mois introuvable :", libelle, e.__class__.__name__)
        return False


def lire_pages(nb_mois):
    """Retourne la liste des textes : page actuelle + les nb_mois derniers mois."""
    from playwright.sync_api import sync_playwright
    textes = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(locale="fr-FR")
        page.goto(URL, wait_until="networkidle", timeout=90000)
        defiler(page)
        textes.append(("page actuelle", page.inner_text("body")))
        for libelle in mois_precedents(nb_mois):
            page.goto(URL, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2000)
            if choisir(page, libelle):
                defiler(page)
                textes.append((libelle, page.inner_text("body")))
        nav.close()
    return textes


def analyser(texte):
    """Retourne une liste (date_iso, jeu, [gagnants], [machine])."""
    L = [x.strip() for x in texte.splitlines() if x.strip()]
    res, an_debut, an_fin, mois_debut, date = [], None, None, None, None
    i = 0
    while i < len(L):
        l = L[i]
        m = re.match(r"Semaine du (\d{2})/(\d{2})/(\d{4}) au (\d{2})/(\d{2})/(\d{4})", l)
        if m:
            mois_debut, an_debut, an_fin = int(m.group(2)), int(m.group(3)), int(m.group(6))
            i += 1
            continue
        m = re.match(r"^" + JOURS + r"\s+(\d{2})/(\d{2})$", l)
        if m and an_debut:
            j, mo = int(m.group(1)), int(m.group(2))
            an = an_fin if mo < mois_debut else an_debut
            date = f"{an:04d}-{mo:02d}-{j:02d}"
            i += 1
            continue
        if re.match(r"^Gagnants\s*:?$", l) and date and i > 0:
            jeu = L[i - 1]
            g = [x for x in L[i + 1:i + 6]]
            if len(g) == 5 and all(x.isdigit() for x in g) and re.match(r"^Machine\s*:?$", L[i + 6] if i + 6 < len(L) else ""):
                mach = L[i + 7:i + 12]
                if len(mach) == 5 and all(x.isdigit() for x in mach):
                    G, M = [int(x) for x in g], [int(x) for x in mach]
                    if all(1 <= x <= 90 for x in G + M):
                        res.append((date, jeu, G, M))
                    i += 12
                    continue
        i += 1
    return res


def lire_fichier():
    sect, out = "G", {"G": [], "M": []}
    entete = []
    try:
        lignes = open(FICHIER, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        lignes = []
    for l in lignes:
        s = l.strip()
        if not s:
            continue
        if s.startswith("#"):
            if re.search("machine", s, re.I):
                sect = "M"
            elif re.search("gagnant", s, re.I):
                sect = "G"
            else:
                entete.append(s)
            continue
        p = [x.strip() for x in s.split(";")]
        if len(p) >= 3:
            d, mo, y = p[0].split("/")
            out[sect].append((f"{y}-{mo}-{d}", p[1], p[2]))
    return entete, out


def ecrire(entete, out):
    def fmt(e):
        y, mo, d = e[0].split("-")
        return f"{d}/{mo}/{y} ; {e[1]} ; {e[2]}"
    txt = "\n".join(entete) + "\n\n# GAGNANTS\n" + "\n".join(fmt(e) for e in out["G"]) + "\n\n# MACHINE\n" + "\n".join(fmt(e) for e in out["M"]) + "\n"
    open(FICHIER, "w", encoding="utf-8").write(txt)


def main():
    nb = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    nouveaux, vus = [], set()
    for nom, texte in lire_pages(nb):
        lus = analyser(texte)
        print(f"{nom} : {len(lus)} tirage(s) lus")
        for r in lus:
            if (r[0], r[1]) not in vus:
                vus.add((r[0], r[1]))
                nouveaux.append(r)
    print(f"{len(nouveaux)} tirage(s) lus sur le site")
    if not nouveaux:
        print("Aucun tirage lu : la page a peut-être changé.")
        sys.exit(1)
    entete, out = lire_fichier()
    ajoutes = 0
    for t, idx in (("G", 2), ("M", 3)):
        connus = {(d, g) for d, g, _ in out[t]}
        neufs = []
        for r in nouveaux:
            if (r[0], r[1]) not in connus:
                neufs.append((r[0], r[1], " ".join(str(x) for x in r[idx])))
                connus.add((r[0], r[1]))
        ajoutes += len(neufs)
        out[t] = sorted(neufs + out[t], key=lambda e: e[0], reverse=True)
    print(f"{ajoutes} ligne(s) ajoutée(s)")
    ecrire(entete, out)


if __name__ == "__main__":
    main()
