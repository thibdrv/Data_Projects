"""Export d'un DataFrame en CSV, Parquet et SQLite."""
from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

import pandas as pd


def save_dataset(
    df: pd.DataFrame,
    name: str,
    directory: str | Path = "data",
    formats: tuple[str, ...] = ("csv", "parquet", "sqlite"),
) -> list[Path]:
    """Enregistre `df` sous `directory/name.<ext>` et retourne les fichiers créés.

    Parquet nécessite `pyarrow` : s'il manque, ce format est ignoré avec un avertissement.
    SQLite crée une table `name` dans `directory/name.sqlite` (remplacée à chaque export).
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in formats:
        path = directory / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(path, index=False, encoding="utf-8")
        elif fmt == "parquet":
            try:
                df.to_parquet(path, index=False)
            except ImportError:
                warnings.warn("pyarrow n'est pas installé : export Parquet ignoré")
                continue
        elif fmt == "sqlite":
            with sqlite3.connect(path) as connection:
                df.to_sql(name, connection, if_exists="replace", index=False)
            connection.close()  # `with` valide la transaction mais ne ferme pas la connexion
        else:
            raise ValueError(f"format inconnu : {fmt}")
        written.append(path)
    return written
