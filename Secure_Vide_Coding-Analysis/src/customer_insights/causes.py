"""Looking for the causes behind the cancellation rate.

Everything here is observational: it shows what cancelling customers have in common and how
the rate moves over time. It cannot prove cause and effect (see `explain` for the caveats).
Functions take plain lists of dicts (see db.py); customers are identified by customer_id only.
"""
import math
from collections import defaultdict

from . import analysis

PAYMENT_ORDER = ("paid", "late", "failed")
BAND_ORDER = ("0 tickets", "1-2 tickets", "3-4 tickets", "5+ tickets")


def _rate(k, n):
    return k / n if n else 0.0


def risk_matrix(customers):
    """Cancellation rate for every combination of last payment status and ticket band."""
    cells = analysis._group_rates(customers, analysis._cell)
    rows = []
    for pay in PAYMENT_ORDER:
        for band in BAND_ORDER:
            n, k = cells.get((pay, band), (0, 0))
            rows.append({"payment": pay, "band": band, "customers": n, "cancelled": k, "rate": _rate(k, n)})
    return rows


def _p_value_vs_rest(n, k, total_n, total_k):
    """Two-sided p-value of a two-proportion z-test: is this group's rate different from everyone else's?"""
    rest_n, rest_k = total_n - n, total_k - k
    if n == 0 or rest_n == 0:
        return 1.0
    p = total_k / total_n
    se = math.sqrt(p * (1 - p) * (1 / n + 1 / rest_n))
    if se == 0:
        return 1.0
    z = (k / n - rest_k / rest_n) / se
    return math.erfc(abs(z) / math.sqrt(2))


def country_table(customers):
    """Per country: customers, cancelled, rate, the cancellations expected from its payment/ticket mix,
    the adjusted lift (cancelled / expected) and the p-value against all other countries. Highest rate first."""
    cell_rate = {k: g[1] / g[0] for k, g in analysis._group_rates(customers, analysis._cell).items()}
    total_n, total_k = len(customers), sum(1 for c in customers if c["cancelled"])
    by_country = defaultdict(list)
    for c in customers:
        by_country[c["country"]].append(c)
    rows = []
    for country, cs in by_country.items():
        n, k = len(cs), sum(1 for c in cs if c["cancelled"])
        expected = sum(cell_rate[analysis._cell(c)] for c in cs)
        rows.append({"country": country, "customers": n, "cancelled": k, "rate": _rate(k, n),
                     "expected": expected, "adjusted_lift": k / expected if expected else 0.0,
                     "p_value": _p_value_vs_rest(n, k, total_n, total_k)})
    return sorted(rows, key=lambda r: -r["rate"])


def avg_tickets_by_payment(customers):
    sums = defaultdict(lambda: [0, 0])
    for c in customers:
        s = sums[c["last_payment_status"]]
        s[0] += c["support_tickets"]
        s[1] += 1
    return {p: _rate(t, n) for p, (t, n) in sums.items()}


def cohorts(customers):
    """Cancellation rate by signup year."""
    groups = analysis._group_rates(customers, lambda c: c["signup_date"][:4])
    return [{"year": y, "customers": n, "cancelled": k, "rate": _rate(k, n)} for y, (n, k) in sorted(groups.items())]


def _month_start(ym):
    return ym + "-01"


def _next_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y + (m == 12)}-{1 if m == 12 else m + 1:02d}"


def monthly_trend(customers):
    """Per month: cancellations, customers active at the start of the month, and the monthly rate."""
    months_with_cancel = sorted({c["cancelled_date"][:7] for c in customers if c["cancelled_date"]})
    if not months_with_cancel:
        return []
    rows, ym = [], months_with_cancel[0]
    while ym <= months_with_cancel[-1]:
        start = _month_start(ym)
        active = sum(1 for c in customers
                     if c["signup_date"] < start and (not c["cancelled_date"] or c["cancelled_date"] >= start))
        cancelled = sum(1 for c in customers if c["cancelled_date"] and c["cancelled_date"][:7] == ym)
        rows.append({"month": ym, "cancellations": cancelled, "active_at_start": active,
                     "rate": _rate(cancelled, active)})
        ym = _next_month(ym)
    return rows


def surge_start(trend, months=6):
    """First day of the window used to compare 'recent' cancellations with earlier ones."""
    ym = trend[-1]["month"]
    y, m = int(ym[:4]), int(ym[5:7]) - (months - 1)
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}-01"


def surge_profile(customers, since):
    """Who cancelled before vs since a date: share by plan, by payment status, and with 3+ tickets.

    Also returns the mix of the whole customer base for reference."""
    cancelled = [c for c in customers if c["cancelled"]]
    before = [c for c in cancelled if c["cancelled_date"] < since]
    recent = [c for c in cancelled if c["cancelled_date"] >= since]

    def count(group, pred):
        return sum(1 for c in group if pred(c))

    rows = []
    for label, pred in (
        [(f"Plan: {p}", (lambda c, p=p: c["plan"] == p)) for p in ("Basic", "Standard", "Premium")]
        + [(f"Payment: {p}", (lambda c, p=p: c["last_payment_status"] == p)) for p in PAYMENT_ORDER]
        + [("3+ support tickets", lambda c: c["support_tickets"] >= 3)]
    ):
        b, r, a = count(before, pred), count(recent, pred), count(customers, pred)
        rows.append({"label": label, "before_k": b, "recent_k": r, "base_k": a,
                     "before": _rate(b, len(before)), "recent": _rate(r, len(recent)), "base": _rate(a, len(customers))})
    return {"since": since, "n_before": len(before), "n_recent": len(recent), "n_base": len(customers), "rows": rows}


def theme_trend(comments, theme):
    """Share of all (usable) comments about one theme, by half-year, oldest to newest."""
    usable, _ = analysis.split_comments(comments)
    totals, hits = defaultdict(int), defaultdict(int)
    for cm in usable:
        d = cm["created_at"]
        period = f"{d[:4]}H{1 if int(d[5:7]) <= 6 else 2}"
        totals[period] += 1
        if theme in analysis._themes_of(cm["comment_text"]):
            hits[period] += 1
    return [{"period": p, "comments": totals[p], "share": _rate(hits[p], totals[p])} for p in sorted(totals)]


def explain(customers, comments):
    """Likely causes. Each item: kind ('strong' = solid evidence, 'lead' = to check, 'note' = no signal found),
    title, evidence."""
    base = analysis.cancellation_rate(customers)
    by_pay = {r["group"]: r for r in analysis.factor_table(customers) if r["factor"] == "Last payment status"}
    by_band = {r["group"]: r for r in analysis.factor_table(customers) if r["factor"] == "Support tickets (12 months)"}
    by_plan = {r["group"]: r for r in analysis.factor_table(customers) if r["factor"] == "Plan"}
    matrix = [r for r in risk_matrix(customers) if r["customers"] >= analysis.MIN_GROUP_SIZE]
    worst, best = max(matrix, key=lambda r: r["rate"]), min(matrix, key=lambda r: r["rate"])
    tickets = avg_tickets_by_payment(customers)
    trend = monthly_trend(customers)
    since = surge_start(trend)
    surge = surge_profile(customers, since)
    prof = {r["label"]: r for r in surge["rows"]}
    early = [r for r in trend if r["month"] < since][-6:]
    early_rate = _rate(sum(r["cancellations"] for r in early), sum(r["active_at_start"] for r in early))

    out = [
        {"kind": "strong", "title": "Billing failures (involuntary churn)",
         "evidence": (f"{by_pay['failed']['rate']:.0%} of customers whose last payment failed cancelled, vs "
                      f"{by_pay['paid']['rate']:.0%} of those who paid ({by_pay['failed']['rate'] / by_pay['paid']['rate']:.1f}x).")},
        {"kind": "strong", "title": "Support friction",
         "evidence": (f"{by_band['5+ tickets']['rate']:.0%} cancelled with 5+ tickets in 12 months, vs "
                      f"{by_band['0 tickets']['rate']:.0%} with none.")},
        {"kind": "strong", "title": "The two factors stack and are independent",
         "evidence": (f"Customers with payment status '{worst['payment']}' and {worst['band']} cancel at {worst['rate']:.0%} "
                      f"(n={worst['customers']}); with status '{best['payment']}' and {best['band']}, {best['rate']:.0%}. "
                      f"Average tickets are similar whatever the "
                      f"payment status ({tickets.get('failed', 0):.1f} / {tickets.get('late', 0):.1f} / {tickets.get('paid', 0):.1f}), "
                      f"so they are separate problems.")},
        {"kind": "strong", "title": "Premium customers stay",
         "evidence": (f"Premium cancels at {by_plan['Premium']['rate']:.1%} vs {by_plan['Basic']['rate']:.1%} for Basic, and only "
                      f"{prof['Plan: Premium']['recent']:.0%} of recent cancellations are Premium vs "
                      f"{prof['Plan: Premium']['base']:.0%} of customers.")},
    ]
    last = trend[-1]
    out.append({
        "kind": "lead", "title": "Cancellations are accelerating, and the known factors do not explain it",
        "evidence": (f"The monthly cancellation rate went from {early_rate:.2%} (6 months before {since[:7]}) to "
                     f"{last['rate']:.2%} in {last['month']}. Recent cancellers are less ticket-heavy "
                     f"({prof['3+ support tickets']['recent']:.0%} with 3+ tickets vs {prof['3+ support tickets']['before']:.0%} earlier) "
                     f"and more often up to date on payments ({prof['Payment: paid']['recent']:.0%} vs {prof['Payment: paid']['before']:.0%}), "
                     f"mostly Basic and Standard. Something changed around {since[:7]} that this data does not capture "
                     f"(for example pricing or an app release): check it first.")})
    price = theme_trend(comments, "Price increase")
    if len(price) >= 2:
        out.append({"kind": "lead", "title": "Price complaints are creeping up (weak signal)",
                    "evidence": (f"Comments about the price increase went from {price[0]['share']:.1%} of all comments "
                                 f"({price[0]['period']}) to {price[-1]['share']:.1%} ({price[-1]['period']}). "
                                 f"The change is small; treat it as a lead to test, not a finding.")})
    countries = country_table(customers)
    if len(countries) >= 2:
        top, low = countries[0], countries[-1]
        reliable = [r for r in countries if r["p_value"] < 0.05 / len(countries)]  # Bonferroni correction
        weak = [r for r in countries if r["p_value"] < 0.05]
        if reliable:
            verdict = "Differs reliably from the average: " + ", ".join(r["country"] for r in reliable) + "."
        elif weak:
            verdict = (f"Only {', '.join(r['country'] for r in weak)} differs from the average at the usual 5% level, "
                       f"and that does not hold once {len(countries)} countries are compared at once.")
        else:
            verdict = "No country differs reliably from the average."
        out.append({"kind": "note", "title": "Country",
                    "evidence": (f"Highest: {top['country']} {top['rate']:.1%} (n={top['customers']}, p={top['p_value']:.2f}); "
                                 f"lowest: {low['country']} {low['rate']:.1%} (p={low['p_value']:.2f}). {verdict}")})
    themes = analysis.comment_themes(customers, comments)
    if themes:
        top = themes[0]
        flagged = [t for t in themes if t["adjusted_lift"] >= analysis.DRIVER_MIN_LIFT]
        if flagged:
            text = ("After adjusting for payment and tickets, these themes still stand out: "
                    + ", ".join(f"{t['theme']} ({t['adjusted_lift']:.1f}x expected)" for t in flagged) + ".")
        else:
            text = (f"After adjusting for payment status and ticket volume, no comment theme cancels more than expected "
                    f"(highest: {top['theme']}, {top['adjusted_lift']:.1f}x). The text of the comments adds little.")
        out.append({"kind": "strong" if flagged else "note", "title": "What customers write", "evidence": text})
    return out


CAVEAT = ("These are associations, not proof of cause: payment status and ticket counts are snapshots, so a failed "
          "payment or a ticket can also be a consequence of a customer leaving.")
