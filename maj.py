import re, sys
from datetime import datetime

URL = "https://lotobonheur.ci/resultats"
FICHIER = "tirages.txt"
JOURS = r"(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)"


def lire_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(locale="fr-FR")
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(5000)
        for _ in range(10):
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(700)
        texte = page.inner_text("body")
        nav.close()
    return texte


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
    nouveaux = analyser(lire_page())
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
