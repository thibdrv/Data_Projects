"""Style matplotlib commun aux notebooks.

Une seule teinte pour une série unique, texte en encre neutre (jamais dans la couleur
de la série), grille discrète, pas de cadre haut/droite, barres fines.
Teinte et encres issues de la palette de référence (bleu, slot 1, surface claire).
"""
import matplotlib.pyplot as plt

SERIES = "#2a78d6"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": MUTED,
            "axes.titlecolor": INK,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "font.size": 10,
            "figure.dpi": 110,
        }
    )
