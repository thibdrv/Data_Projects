"""Builds the weekly summary (outbox/summary.md), a chart (outbox/drivers.png) and the Excel results."""
from pathlib import Path

from jinja2 import Template

from . import analysis, causes, db

ROOT = Path(__file__).resolve().parents[2]
OUTBOX = Path("outbox")
CHART_FACTORS = ("Last payment status", "Support tickets (12 months)", "Plan")


def make_chart(customers, path):
    """Bar chart of the cancellation rate by group, with the overall rate as a reference line."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = analysis.cancellation_rate(customers)
    rows = [r for r in analysis.factor_table(customers) if r["factor"] in CHART_FACTORS]
    rows.sort(key=lambda r: (CHART_FACTORS.index(r["factor"]), -r["rate"]))
    labels = [f"{r['group']}  (n={r['customers']})" for r in rows]
    values = [r["rate"] * 100 for r in rows]
    colors = ["#c0392b" if r["lift"] >= analysis.DRIVER_MIN_LIFT else "#7f8c8d" for r in rows]

    fig, ax = plt.subplots(figsize=(8, 0.42 * len(rows) + 1.6))
    bars = ax.barh(range(len(rows)), values, color=colors)
    ax.set_yticks(range(len(rows)), labels)
    ax.invert_yaxis()
    ax.axvline(base * 100, color="black", linestyle="--", linewidth=1)
    ax.text(base * 100, -0.9, f" overall {base:.1%}", fontsize=8, va="bottom")
    for bar, v, r in zip(bars, values, rows):
        ax.text(v + 0.5, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%  [{r['factor']}]", va="center", fontsize=8)
    ax.set_xlabel("Cancellation rate (%)")
    ax.set_title("Cancellation rate by group (red = at least 1.4x the overall rate)", fontsize=10, pad=18)
    ax.set_xlim(0, max(values) * 1.45)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def describe_driver(r, base):
    return (f"{r['group']} ({r['factor'].lower()}): {r['rate']:.0%} cancelled vs {base:.0%} overall "
            f"({r['lift']:.1f}x, {r['customers']} customers)")


def build():
    conn = db.connect()
    try:
        customers = db.get_customers(conn)
        comments = db.get_comments(conn)
    finally:
        conn.close()

    base = analysis.cancellation_rate(customers)
    drivers = [describe_driver(r, base) for r in analysis.cancellation_reasons(customers)]
    likely_causes = causes.explain(customers, comments)
    _, suspicious = analysis.split_comments(comments)
    at_risk = analysis.at_risk_customers(customers, comments)

    OUTBOX.mkdir(exist_ok=True)
    files = []
    try:
        make_chart(customers, OUTBOX / "drivers.png")
        files.append("outbox/drivers.png")
    except ImportError:
        print("chart skipped: matplotlib is not installed")
    try:
        from . import excel
        excel.write_workbook(OUTBOX / "customer_insights.xlsx", customers, comments)
        files.append("outbox/customer_insights.xlsx")
    except ImportError:
        print("excel skipped: openpyxl is not installed")

    tpl = Template((ROOT / "templates" / "weekly_summary.md.j2").read_text(encoding="utf-8"))
    out = tpl.render(
        total=len(customers),
        cancelled=sum(1 for c in customers if c["cancelled"]),
        cancellation_rate=f"{base:.1%}",
        drivers=drivers,
        causes=likely_causes,
        caveat=causes.CAVEAT,
        at_risk=at_risk,
        suspicious=suspicious,
        files=files,
    )
    (OUTBOX / "summary.md").write_text(out, encoding="utf-8")
    print("wrote outbox/summary.md")


if __name__ == "__main__":
    build()
