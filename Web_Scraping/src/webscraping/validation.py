"""Contrôles de qualité sur le jeu de données des livres."""
from __future__ import annotations

import pandas as pd

REQUIRED = ["url", "categorie", "titre", "prix_gbp", "stock", "note"]  # la description est optionnelle


def validate_books(df: pd.DataFrame, expected_rows: int | None = 1000, strict: bool = False) -> list[str]:
    """Retourne la liste des problèmes détectés (vide si tout est correct).

    Avec strict=True, lève une ValueError au lieu de retourner la liste.
    """
    problems: list[str] = []

    missing_columns = [c for c in REQUIRED if c not in df.columns]
    if missing_columns:
        problems.append(f"colonnes manquantes : {missing_columns}")
    present = [c for c in REQUIRED if c in df.columns]

    if expected_rows is not None and len(df) != expected_rows:
        problems.append(f"{len(df)} lignes au lieu de {expected_rows}")

    for column in present:
        nulls = int(df[column].isna().sum())
        if nulls:
            problems.append(f"{nulls} valeur(s) manquante(s) dans '{column}'")

    if "url" in df.columns and df["url"].duplicated().any():
        problems.append(f"{int(df['url'].duplicated().sum())} URL en double")
    if "prix_gbp" in df.columns:
        bad = int((~df["prix_gbp"].between(0, 100, inclusive="right") & df["prix_gbp"].notna()).sum())
        if bad:
            problems.append(f"{bad} prix hors de l'intervalle ]0, 100] GBP")
    if "stock" in df.columns and (df["stock"] < 0).any():
        problems.append(f"{int((df['stock'] < 0).sum())} stock(s) négatif(s)")
    if "note" in df.columns:
        bad = int((~df["note"].between(1, 5) & df["note"].notna()).sum())
        if bad:
            problems.append(f"{bad} note(s) hors de l'intervalle 1-5")

    if strict and problems:
        raise ValueError("Données invalides : " + " ; ".join(problems))
    return problems
