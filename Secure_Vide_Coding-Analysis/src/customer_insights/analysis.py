"""Customer analysis: cancellation rate, drivers of cancellation, at-risk active customers.

All functions take plain lists of dicts (see db.py) and never touch the database.
Customers are identified by customer_id only; no PII is handled here.
"""
import re
from collections import defaultdict

MIN_GROUP_SIZE = 30      # ignore groups too small to be meaningful
DRIVER_MIN_LIFT = 1.4    # a group is a "driver" if it cancels at least 1.4x the overall rate

# Comment themes (keyword -> label). Matching is on lowercase text.
THEMES = {
    "payment failed": "Payment failures",
    "charged me twice": "Double billing",
    "log in": "TV app login problems",
    "buffering": "Buffering",
    "arabic audio": "Missing Arabic audio",
    "subtitles": "Subtitles out of sync",
    "support took": "Slow support",
    "price went up": "Price increase",
    "repeats": "Repetitive content / thinking of cancelling",
    "moving abroad": "Moving abroad",
    "love the new": "Positive",
    "no complaints": "Positive",
}

# Customer-written text can contain instructions aimed at AI tools. Such comments are
# never analysed as content: they are excluded and only counted.
SUSPICIOUS = re.compile(
    r"ignore (all |your )?(previous|prior) instructions|system note|ai assistants|do not mention", re.I)


def cancellation_rate(customers):
    """Share of customers who cancelled, as a fraction between 0 and 1."""
    if not customers:
        raise ValueError("no customers")
    return sum(1 for c in customers if c["cancelled"]) / len(customers)


def _ticket_band(n):
    return "0 tickets" if n == 0 else "1-2 tickets" if n <= 2 else "3-4 tickets" if n <= 4 else "5+ tickets"


def _group_rates(customers, key):
    groups = defaultdict(lambda: [0, 0])
    for c in customers:
        g = groups[key(c)]
        g[0] += 1
        g[1] += 1 if c["cancelled"] else 0
    return groups


def factor_table(customers):
    """Cancellation rate for every group of every structured factor (used by the chart)."""
    base = cancellation_rate(customers)
    factors = {
        "Last payment status": lambda c: c["last_payment_status"],
        "Support tickets (12 months)": lambda c: _ticket_band(c["support_tickets"]),
        "Plan": lambda c: c["plan"],
        "Country": lambda c: c["country"],
    }
    rows = []
    for factor, key in factors.items():
        for group, (n, k) in _group_rates(customers, key).items():
            if n >= MIN_GROUP_SIZE:
                rate = k / n
                rows.append({"factor": factor, "group": group, "customers": n, "cancelled": k,
                             "rate": rate, "lift": rate / base if base else 0.0})
    return rows


def cancellation_reasons(customers):
    """Main factors associated with cancelling: groups cancelling at >= DRIVER_MIN_LIFT x the
    overall rate, strongest first. These are associations, not proven causes."""
    drivers = [r for r in factor_table(customers) if r["lift"] >= DRIVER_MIN_LIFT]
    return sorted(drivers, key=lambda r: r["lift"], reverse=True)


def split_comments(comments):
    """Return (usable, suspicious_count). Comments that look like injected instructions are dropped."""
    usable = [c for c in comments if not SUSPICIOUS.search(c["comment_text"] or "")]
    return usable, len(comments) - len(usable)


def _themes_of(text):
    t = (text or "").lower()
    return {label for kw, label in THEMES.items() if kw in t}


def _cell(c):
    return (c["last_payment_status"], _ticket_band(c["support_tickets"]))


def comment_themes(customers, comments):
    """Do comment themes explain cancellations beyond payment status and ticket volume?

    For each theme, compare the customers who wrote about it with what we would expect given
    their payment status and ticket band (their cell's overall cancellation rate).
    adjusted_lift = observed cancellations / expected cancellations; 1.0 means the theme adds
    nothing. Each customer counts once per theme. Comments are about as numerous as tickets, so
    a raw comparison would mostly re-measure ticket volume; this adjustment avoids that.
    """
    by_id = {c["customer_id"]: c for c in customers}
    cell_rate = {k: g[1] / g[0] for k, g in _group_rates(customers, _cell).items()}
    usable, _ = split_comments(comments)
    per_customer = defaultdict(set)
    for cm in usable:
        if cm["customer_id"] in by_id:
            per_customer[cm["customer_id"]] |= _themes_of(cm["comment_text"])
    stats = defaultdict(lambda: [0, 0, 0.0])  # customers, cancelled, expected
    for cid, themes in per_customer.items():
        c = by_id[cid]
        for th in themes:
            s = stats[th]
            s[0] += 1
            s[1] += 1 if c["cancelled"] else 0
            s[2] += cell_rate[_cell(c)]
    rows = [{"theme": th, "customers": n, "cancelled": k, "expected": e,
             "rate": k / n, "adjusted_lift": k / e if e else 0.0}
            for th, (n, k, e) in stats.items() if n >= MIN_GROUP_SIZE]
    return sorted(rows, key=lambda r: r["adjusted_lift"], reverse=True)


def at_risk_customers(customers, comments, limit=10):
    """Active customers most likely to cancel, with a simple, explainable score.

    Points: failed payment 3, late payment 1.5; 5+ tickets 3, 3-4 tickets 2, 1-2 tickets 0.5;
    a comment about payment/billing problems or cancelling 1 each. Returns dicts with
    customer_id, plan, monthly_fee, score and reason (no PII).
    """
    usable, _ = split_comments(comments)
    flags = defaultdict(set)
    for cm in usable:
        for th in _themes_of(cm["comment_text"]):
            if th in ("Payment failures", "Double billing", "Repetitive content / thinking of cancelling"):
                flags[cm["customer_id"]].add(th)

    scored = []
    for c in customers:
        if c["cancelled"]:
            continue
        score, reasons = 0.0, []
        if c["last_payment_status"] == "failed":
            score += 3
            reasons.append("last payment failed")
        elif c["last_payment_status"] == "late":
            score += 1.5
            reasons.append("late payment")
        t = c["support_tickets"]
        if t >= 5:
            score += 3
            reasons.append(f"{t} support tickets")
        elif t >= 3:
            score += 2
            reasons.append(f"{t} support tickets")
        elif t >= 1:
            score += 0.5
        for th in sorted(flags.get(c["customer_id"], ())):
            score += 1
            reasons.append(f"comment: {th.lower()}")
        if score > 0:
            scored.append({"customer_id": c["customer_id"], "plan": c["plan"], "monthly_fee": c["monthly_fee"],
                           "score": score, "reason": ", ".join(reasons) or "some support tickets"})
    # highest score first; higher-paying customers first on ties; stable by id
    scored.sort(key=lambda r: (-r["score"], -r["monthly_fee"], r["customer_id"]))
    return scored[:limit]
