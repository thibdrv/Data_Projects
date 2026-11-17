# Web scraping avec Beautiful Soup et Selenium

Expériences de web scraping sur deux sites publics, puis comparaison avec l'API officielle de GitHub. Il s'agit uniquement d'une phase de test et d'expérimentation technique. En production, plusieurs contraintes doivent être strictement respectées, notamment :

- **RGPD** : la collecte et le traitement de données personnelles (emails, profils...) sont encadrés par la loi, même si ces données sont publiques. Ce projet ne collecte aucune donnée personnelle.
- **Conditions d'utilisation (CGU)** : respecter le `robots.txt` du site et ne pas surcharger ses serveurs (utiliser l'API officielle quand elle existe). Le code du projet vérifie `robots.txt`, envoie un User-Agent explicite, attend entre les requêtes, utilise des timeouts et réessaie les erreurs temporaires avec un délai croissant.

## Contenu

| Notebook | Outils | Sujet |
|---|---|---|
| [`Crawling_Scraping.ipynb`](notebooks/Crawling_Scraping.ipynb) | `requests` + Beautiful Soup | Crawl paginé de chucknorrisfacts.fr (528 pages), avec reprise après interruption |
| [`Selenium_Scraping.ipynb`](notebooks/Selenium_Scraping.ipynb) | Selenium | Démonstration sur books.toscrape.com (nécessite Chrome) |
| [`Analyse_Livres.ipynb`](notebooks/Analyse_Livres.ipynb) | `requests` + Beautiful Soup, pandas, matplotlib | Même site, sans Selenium : collecte, validation, export, analyse et graphiques |
| [`API_GitHub.ipynb`](notebooks/API_GitHub.ipynb) | API REST de GitHub | L'alternative recommandée au scraping, sur des métadonnées de dépôts (aucune donnée personnelle) |

books.toscrape.com est un site statique : `requests` suffit et va beaucoup plus vite que Selenium. Selenium n'est utile que pour les pages rendues en JavaScript ou qui demandent des interactions. Le notebook Selenium affiche sa durée pour la comparer avec celle d'`Analyse_Livres`.

## Structure

```
notebooks/          les quatre notebooks
src/webscraping/    code réutilisable et testé (voir ci-dessous)
tests/              tests pytest, sans accès réseau
data/               fichiers générés (CSV, Parquet, SQLite), ignorés par git
```

| Module | Rôle |
|---|---|
| `http.py` | session avec retry, User-Agent, vérification de `robots.txt` |
| `chucknorris.py` | crawl paginé avec fichier de reprise |
| `books.py` | scraping des livres, nettoyage à la source (types, prix en €) |
| `validation.py` | contrôles de qualité (nombre de lignes, valeurs manquantes, doublons, valeurs hors plage) |
| `fx.py` | taux de change GBP → EUR du jour (API publique, données de la BCE) avec valeur de secours |
| `storage.py` | export CSV, Parquet et SQLite |
| `github_api.py` | appel à l'API GitHub avec gestion de la limite de requêtes |
| `plotting.py` | style matplotlib commun aux graphiques |

## Installation et utilisation

```bash
pip install -r requirements-dev.txt
pytest
```

Ouvrez ensuite les notebooks depuis le dossier `notebooks/` (Jupyter ou VS Code). Les chemins relatifs (`../src`, `../data`) supposent que le dossier de travail du notebook est `notebooks/`.

- Le crawl complet de chucknorrisfacts.fr dure environ 9 minutes. Il écrit un fichier de reprise toutes les 10 pages : relancer la cellule après une interruption reprend là où elle s'est arrêtée.
- `Analyse_Livres` met environ 10 minutes à collecter les 1000 livres, avec le même mécanisme de reprise.
- Pour l'API GitHub, la limite sans jeton est de 60 requêtes par heure. Pour plus, définissez la variable d'environnement `GITHUB_TOKEN` (jamais dans le code ou un notebook).

## Notes sur les données

- « Default » et « Add a comment » sont de vraies catégories du site books.toscrape.com (livres sans vraie catégorie), pas des erreurs de scraping. L'analyse les regroupe sous « Sans catégorie ».
- Deux livres du site n'ont pas de description : ils sont conservés avec une description vide.
- Le prix en euros utilise le taux du jour, enregistré dans la colonne `taux_gbp_eur` (avec la date de collecte dans `date_collecte`) pour garder la traçabilité.

---

Cette première phase, menée sur des sites publics et des sites d'entraînement, a permis d'évaluer la faisabilité technique tout en gardant en tête les bonnes pratiques légales et éthiques requises pour un projet finalisé.
