"""Outils de web scraping utilisés par les notebooks du projet.

Modules :
    http        session avec retry, User-Agent, vérification de robots.txt
    chucknorris crawl paginé de chucknorrisfacts.fr (requests + Beautiful Soup)
    books       scraping de books.toscrape.com (requests + Beautiful Soup)
    validation  contrôles de qualité sur le jeu de données des livres
    fx          taux de change GBP -> EUR (API publique, avec valeur de secours)
    storage     export CSV / Parquet / SQLite
    github_api  exemple avec l'API officielle de GitHub (alternative au scraping)
"""
