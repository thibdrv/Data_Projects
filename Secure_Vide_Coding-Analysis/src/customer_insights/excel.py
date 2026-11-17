"""Excel workbook with the final results and native charts (outbox/customer_insights.xlsx).

Counts come from the database and are written as values (blue text); rates, lifts and shares are
Excel formulas (black text), so the sheets stay consistent if someone edits a count.
No personal data: customers appear as customer_id only.
"""
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Font, PatternFill

from . import analysis, causes

FONT = "Arial"
NAVY = "101A2C"
BLUE = "0000FF"
PCT, PCT2, TIMES = "0.0%", "0.00%", '0.0"x"'
SHADES = ["C9D3E6", "8FA3C7", "4F6A9E", NAVY]  # lightness steps, light to dark
SHORT = {"Last payment status": "Payment", "Support tickets (12 months)": "Tickets", "Plan": "Plan", "Country": "Country"}
PLAN_ORDER = ("Basic", "Standard", "Premium")


def _cell(ws, ref, value, fmt=None, blue=False, bold=False, size=10, wrap=False, color=None):
    c = ws[ref]
    c.value = value
    c.font = Font(name=FONT, size=size, bold=bold, color=BLUE if blue else (color or "000000"))
    if fmt:
        c.number_format = fmt
    c.alignment = Alignment(wrap_text=wrap, vertical="top" if wrap else "center")
    return c


def _header(ws, row, labels):
    for i, label in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=label)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _widths(ws, widths):
    for letter, w in widths.items():
        ws.column_dimensions[letter].width = w


def _style_chart(chart, title, x_title, y_title, y_fmt=None, labels=True, w=20, h=9):
    chart.title, chart.width, chart.height = title, w, h
    chart.x_axis.title, chart.y_axis.title = x_title, y_title
    chart.x_axis.delete = False   # openpyxl hides axes by default
    chart.y_axis.delete = False
    if y_fmt:
        chart.y_axis.number_format = y_fmt
    if labels:
        dl = DataLabelList()
        dl.showVal = True
        dl.showSerName = dl.showCatName = dl.showLegendKey = dl.showPercent = False
        chart.dataLabels = dl


def _note(ws, ref, text, width_cols=None):
    _cell(ws, ref, text, size=9, color="555555")


def write_workbook(path, customers, comments, at_risk_limit=50):
    base = analysis.cancellation_rate(customers)
    n_total, n_cancelled = len(customers), sum(1 for c in customers if c["cancelled"])
    last_cancel = max((c["cancelled_date"] for c in customers if c["cancelled_date"]), default="n/a")
    wb = Workbook()

    # ---------------------------------------------------------------- Summary
    ws = wb.active
    ws.title = "Summary"
    _cell(ws, "A1", "Customer Insights: cancellation analysis", bold=True, size=16)
    _cell(ws, "A2", f"Source: v_customers_analytics (no personal data). Cancellations up to {last_cancel}.", size=9, color="555555")
    _cell(ws, "A4", "Customers in scope", bold=True)
    _cell(ws, "B4", n_total, "#,##0", blue=True)
    _cell(ws, "A5", "Cancelled", bold=True)
    _cell(ws, "B5", n_cancelled, "#,##0", blue=True)
    _cell(ws, "A6", "Cancellation rate", bold=True)
    _cell(ws, "B6", "=B5/B4", PCT)
    _header(ws, 8, ["Type", "Likely cause", "Evidence"])
    row = 9
    for item in causes.explain(customers, comments):
        label = {"strong": "Strong", "lead": "Lead to check", "note": "No signal found"}[item["kind"]]
        _cell(ws, f"A{row}", label, bold=True, wrap=True)
        _cell(ws, f"B{row}", item["title"], bold=True, wrap=True)
        _cell(ws, f"C{row}", item["evidence"], wrap=True)
        ws.row_dimensions[row].height = 15 * max(2, len(item["evidence"]) // 85 + 1)
        row += 1
    row += 1
    ws.merge_cells(f"A{row}:C{row}")
    _cell(ws, f"A{row}", causes.CAVEAT, wrap=True, bold=True)
    ws.row_dimensions[row].height = 32
    row += 2
    _cell(ws, f"A{row}", "Sheets", bold=True)
    for name, text in [("Drivers", "Cancellation rate by payment status, tickets, plan, country"),
                       ("Risk matrix", "Payment status x tickets: how the two factors stack"),
                       ("Monthly trend", "Monthly cancellation rate: the recent acceleration"),
                       ("Recent vs earlier", "Who cancelled recently compared with before"),
                       ("Countries", "Cancellation rate by country, with a significance check"),
                       ("Comment themes", "Raw and adjusted cancellation rate by comment theme"),
                       ("At-risk", "Active customers most likely to cancel (IDs only)"),
                       ("Notes", "Definitions, thresholds and limits")]:
        row += 1
        _cell(ws, f"A{row}", name)
        _cell(ws, f"B{row}", text)
    _widths(ws, {"A": 22, "B": 44, "C": 100})

    # ---------------------------------------------------------------- Drivers
    ws = wb.create_sheet("Drivers")
    _header(ws, 1, ["Label", "Factor", "Group", "Customers", "Cancelled", "Cancellation rate", "Lift vs overall", "Driver?"])
    table = {(r["factor"], r["group"]): r for r in analysis.factor_table(customers)}
    order = ([("Last payment status", g) for g in causes.PAYMENT_ORDER]
             + [("Support tickets (12 months)", g) for g in causes.BAND_ORDER]
             + [("Plan", g) for g in PLAN_ORDER]
             + [("Country", g) for _, g in sorted(k for k in table if k[0] == "Country")])
    r = 2
    chart_last = 1
    for key in order:
        if key not in table:
            continue
        t = table[key]
        _cell(ws, f"A{r}", f"{SHORT[key[0]]}: {key[1].replace(' tickets', '')}")
        _cell(ws, f"B{r}", key[0])
        _cell(ws, f"C{r}", key[1])
        _cell(ws, f"D{r}", t["customers"], "#,##0", blue=True)
        _cell(ws, f"E{r}", t["cancelled"], "#,##0", blue=True)
        _cell(ws, f"F{r}", f"=E{r}/D{r}", PCT)
        _cell(ws, f"G{r}", f"=F{r}/Summary!$B$6", TIMES)
        _cell(ws, f"H{r}", f'=IF(G{r}>=$K$2,"Driver","")')
        if key[0] != "Country":
            chart_last = r
        r += 1
    _cell(ws, "J1", "Driver threshold", bold=True)
    _cell(ws, "J2", "Lift at least")
    _cell(ws, "K2", analysis.DRIVER_MIN_LIFT, TIMES, blue=True)
    _note(ws, "J3", "Assumption: a group is a driver if it cancels at least this many times the overall rate.")
    _note(ws, "J4", f"Groups with fewer than {analysis.MIN_GROUP_SIZE} customers are left out.")
    ws.freeze_panes = "A2"
    _widths(ws, {"A": 22, "B": 28, "C": 14, "D": 12, "E": 12, "F": 18, "G": 16, "H": 10, "I": 3, "J": 16, "K": 10})
    ch = BarChart()
    ch.type = "bar"
    ch.add_data(Reference(ws, min_col=6, min_row=1, max_row=chart_last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=chart_last))
    ch.x_axis.scaling.orientation = "maxMin"
    ch.legend = None
    ch.series[0].graphicalProperties.solidFill = NAVY
    _style_chart(ch, "Cancellation rate by group", None, "Cancellation rate", "0%", h=10)
    ws.add_chart(ch, "J6")

    # ---------------------------------------------------------------- Risk matrix
    ws = wb.create_sheet("Risk matrix")
    matrix = {(m["payment"], m["band"]): m for m in causes.risk_matrix(customers)}
    _cell(ws, "A1", "Cancellation rate by last payment status and support tickets (12 months)", bold=True, size=12)
    blocks = {"rate": 3, "customers": 9, "cancelled": 15}  # header row of each block
    titles = {"rate": "Cancellation rate", "customers": "Customers", "cancelled": "Cancelled"}
    for name, hr in blocks.items():
        _header(ws, hr, [titles[name]] + list(causes.BAND_ORDER))
        for i, pay in enumerate(causes.PAYMENT_ORDER, start=1):
            rr = hr + i
            _cell(ws, f"A{rr}", pay, bold=True)
            for j, band in enumerate(causes.BAND_ORDER):
                col = chr(ord("B") + j)
                if name == "rate":
                    _cell(ws, f"{col}{rr}", f"=IFERROR({col}{rr + 12}/{col}{rr + 6},0)", PCT)
                else:
                    _cell(ws, f"{col}{rr}", matrix[(pay, band)][name], "#,##0", blue=True)
    _note(ws, "A8", f"Cells with fewer than {analysis.MIN_GROUP_SIZE} customers are only indicative.")
    _widths(ws, {"A": 22, "B": 14, "C": 14, "D": 14, "E": 14})
    ch = BarChart()
    ch.type = "col"
    ch.grouping = "clustered"
    ch.add_data(Reference(ws, min_col=2, max_col=5, min_row=3, max_row=6), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=6))
    for s, color in zip(ch.series, SHADES):
        s.graphicalProperties.solidFill = color
    _style_chart(ch, "Payment problems and tickets add up", "Last payment status", "Cancellation rate", "0%", w=22, h=10)
    ws.add_chart(ch, "G2")

    # ---------------------------------------------------------------- Monthly trend
    ws = wb.create_sheet("Monthly trend")
    trend = causes.monthly_trend(customers)
    since = causes.surge_start(trend)
    _header(ws, 1, ["Month", "Cancellations", "Active at start of month", "Monthly cancellation rate"])
    for i, t in enumerate(trend, start=2):
        _cell(ws, f"A{i}", t["month"])
        _cell(ws, f"B{i}", t["cancellations"], "#,##0", blue=True)
        _cell(ws, f"C{i}", t["active_at_start"], "#,##0", blue=True)
        _cell(ws, f"D{i}", f"=IFERROR(B{i}/C{i},0)", PCT2)
    last = len(trend) + 1
    _note(ws, f"A{last + 2}", f"Active at start = signed up before the month and not yet cancelled. 'Recent' elsewhere means since {since}.")
    ws.freeze_panes = "A2"
    _widths(ws, {"A": 12, "B": 15, "C": 24, "D": 26})
    lc = LineChart()
    lc.add_data(Reference(ws, min_col=4, min_row=1, max_row=last), titles_from_data=True)
    lc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    lc.legend = None
    lc.series[0].graphicalProperties.line.solidFill = NAVY
    lc.series[0].graphicalProperties.line.width = 28000
    lc.series[0].smooth = False
    _style_chart(lc, "Monthly cancellation rate", "Month", "Share of active customers", "0.0%", labels=False, w=24, h=10)
    ws.add_chart(lc, "F2")
    bc = BarChart()
    bc.type = "col"
    bc.add_data(Reference(ws, min_col=2, min_row=1, max_row=last), titles_from_data=True)
    bc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    bc.legend = None
    bc.series[0].graphicalProperties.solidFill = NAVY
    _style_chart(bc, "Cancellations per month", "Month", "Customers", labels=False, w=24, h=10)
    ws.add_chart(bc, "F24")

    # ---------------------------------------------------------------- Recent vs earlier
    ws = wb.create_sheet("Recent vs earlier")
    surge = causes.surge_profile(customers, since)
    _cell(ws, "A1", f"Who cancelled: since {since} (recent) vs before (earlier), against the whole customer base", bold=True, size=12)
    _cell(ws, "A3", "Total (group size)", bold=True)
    _cell(ws, "B3", surge["n_before"], "#,##0", blue=True)
    _cell(ws, "C3", surge["n_recent"], "#,##0", blue=True)
    _cell(ws, "D3", surge["n_base"], "#,##0", blue=True)
    _header(ws, 4, ["Group", "Earlier (count)", "Recent (count)", "All customers (count)", "Earlier (%)", "Recent (%)", "All customers (%)"])
    r = 5
    for row_ in surge["rows"]:
        _cell(ws, f"A{r}", row_["label"])
        _cell(ws, f"B{r}", row_["before_k"], "#,##0", blue=True)
        _cell(ws, f"C{r}", row_["recent_k"], "#,##0", blue=True)
        _cell(ws, f"D{r}", row_["base_k"], "#,##0", blue=True)
        for src, dst in (("B", "E"), ("C", "F"), ("D", "G")):
            _cell(ws, f"{dst}{r}", f"={src}{r}/{src}$3", PCT)
        r += 1
    last = r - 1
    _note(ws, f"A{last + 2}", "Earlier and recent counts are cancelled customers; 'All customers' covers the whole base.")
    _widths(ws, {"A": 24, "B": 16, "C": 16, "D": 22, "E": 14, "F": 14, "G": 18})
    ch = BarChart()
    ch.type = "col"
    ch.grouping = "clustered"
    ch.add_data(Reference(ws, min_col=5, max_col=7, min_row=4, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
    for s, color in zip(ch.series, [SHADES[0], SHADES[2], SHADES[3]]):
        s.graphicalProperties.solidFill = color
    _style_chart(ch, "Recent cancellers vs earlier ones", None, "Share of group", "0%", labels=False, w=26, h=11)
    ws.add_chart(ch, "A" + str(last + 4))

    # ---------------------------------------------------------------- Countries
    ws = wb.create_sheet("Countries")
    countries = causes.country_table(customers)
    _header(ws, 1, ["Country", "Customers", "Cancelled", "Cancellation rate", "Lift vs overall",
                    "Expected cancelled", "Adjusted lift", "p-value vs other countries", "Differs from average?"])
    for i, t in enumerate(countries, start=2):
        _cell(ws, f"A{i}", t["country"], bold=True)
        _cell(ws, f"B{i}", t["customers"], "#,##0", blue=True)
        _cell(ws, f"C{i}", t["cancelled"], "#,##0", blue=True)
        _cell(ws, f"D{i}", f"=C{i}/B{i}", PCT)
        _cell(ws, f"E{i}", f"=D{i}/Summary!$B$6", TIMES)
        _cell(ws, f"F{i}", round(t["expected"], 1), "0.0", blue=True)
        _cell(ws, f"G{i}", f"=IFERROR(C{i}/F{i},0)", TIMES)
        _cell(ws, f"H{i}", round(t["p_value"], 3), "0.000", blue=True)
        _cell(ws, f"I{i}", f'=IF(H{i}<$L$2,"Yes","No")')
    last = len(countries) + 1
    _cell(ws, "K1", "Significance level", bold=True)
    _cell(ws, "K2", "p-value below")
    _cell(ws, "L2", 0.05, "0.000", blue=True)
    _note(ws, f"A{last + 2}", "Expected = cancellations predicted by each country's mix of payment status and ticket volume. Adjusted lift 1.0x = nothing country-specific.")
    _note(ws, f"A{last + 3}", f"p-value: two-proportion test of the country against all others. With {len(countries)} countries compared at once, "
                              f"a single p-value near 0.05 can happen by chance (a strict threshold would be {0.05 / len(countries):.3f}).")
    ws.freeze_panes = "A2"
    _widths(ws, {"A": 14, "B": 12, "C": 12, "D": 18, "E": 16, "F": 18, "G": 14, "H": 24, "I": 22, "J": 3, "K": 20, "L": 10})
    ch = BarChart()
    ch.type = "bar"
    ch.add_data(Reference(ws, min_col=4, min_row=1, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    ch.x_axis.scaling.orientation = "maxMin"
    ch.legend = None
    ch.series[0].graphicalProperties.solidFill = NAVY
    _style_chart(ch, "Cancellation rate by country", None, "Cancellation rate", "0%", w=20, h=10)
    ws.add_chart(ch, "K4")

    # ---------------------------------------------------------------- Comment themes
    ws = wb.create_sheet("Comment themes")
    themes = analysis.comment_themes(customers, comments)
    _header(ws, 1, ["Theme", "Customers", "Cancelled", "Expected cancelled", "Cancellation rate", "Adjusted lift"])
    for i, t in enumerate(themes, start=2):
        _cell(ws, f"A{i}", t["theme"])
        _cell(ws, f"B{i}", t["customers"], "#,##0", blue=True)
        _cell(ws, f"C{i}", t["cancelled"], "#,##0", blue=True)
        _cell(ws, f"D{i}", round(t["expected"], 1), "0.0", blue=True)
        _cell(ws, f"E{i}", f"=C{i}/B{i}", PCT)
        _cell(ws, f"F{i}", f"=IFERROR(C{i}/D{i},0)", TIMES)
    last = len(themes) + 1
    _note(ws, f"A{last + 2}", "Expected = cancellations we would see given each customer's payment status and ticket band. Adjusted lift 1.0x = the theme adds nothing.")
    _note(ws, f"A{last + 3}", "Comments that contain instructions aimed at automated tools are excluded from this sheet.")
    ws.freeze_panes = "A2"
    _widths(ws, {"A": 44, "B": 12, "C": 12, "D": 20, "E": 18, "F": 14})
    ch = BarChart()
    ch.type = "bar"
    ch.add_data(Reference(ws, min_col=6, min_row=1, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    ch.x_axis.scaling.orientation = "maxMin"
    ch.legend = None
    ch.series[0].graphicalProperties.solidFill = SHADES[2]
    _style_chart(ch, "Comment themes: cancellations vs expected (1.0x = as expected)", None, "Adjusted lift", '0.0"x"', w=22, h=11)
    ws.add_chart(ch, "H2")
    raw = BarChart()
    raw.type = "bar"
    raw.add_data(Reference(ws, min_col=5, min_row=1, max_row=last), titles_from_data=True)
    raw.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    raw.x_axis.scaling.orientation = "maxMin"
    raw.legend = None
    raw.series[0].graphicalProperties.solidFill = SHADES[1]
    _style_chart(raw, f"Comment themes: raw cancellation rate (overall {base:.1%})", None, "Cancellation rate", "0%", w=22, h=11)
    ws.add_chart(raw, "H25")

    # ---------------------------------------------------------------- At-risk
    ws = wb.create_sheet("At-risk")
    _cell(ws, "A1", "Active customers most likely to cancel", bold=True, size=12)
    _note(ws, "A2", "Customer IDs only, no personal data: account managers look the IDs up in the CRM. Score rules are on the Notes sheet.")
    _header(ws, 4, ["Rank", "Customer ID", "Plan", "Monthly fee (EUR)", "Score", "Reason"])
    for i, c in enumerate(analysis.at_risk_customers(customers, comments, limit=at_risk_limit), start=1):
        rr = i + 4
        _cell(ws, f"A{rr}", i)
        _cell(ws, f"B{rr}", c["customer_id"], blue=True)
        _cell(ws, f"C{rr}", c["plan"], blue=True)
        _cell(ws, f"D{rr}", c["monthly_fee"], "0.00", blue=True)
        _cell(ws, f"E{rr}", c["score"], "0.0", blue=True)
        _cell(ws, f"F{rr}", c["reason"], blue=True)
    ws.freeze_panes = "A5"
    _widths(ws, {"A": 8, "B": 14, "C": 12, "D": 18, "E": 8, "F": 90})

    # ---------------------------------------------------------------- Notes
    ws = wb.create_sheet("Notes")
    lines = [
        ("Reading the sheets", None),
        ("Colours", "Blue = values taken from the database or an assumption you can change. Black = formulas."),
        ("Source", "data/customers.db through the v_customers_analytics view (no name, email or phone). The database is opened read-only."),
        ("Cancellation rate", "Share of all customers in the database who cancelled (cumulative, not weekly)."),
        ("Driver", f"A group that cancels at least {analysis.DRIVER_MIN_LIFT}x the overall rate. The 1.4x threshold is a judgement call; change it on the Drivers sheet."),
        ("At-risk score", "Failed payment 3, late payment 1.5; 5+ tickets 3, 3-4 tickets 2, 1-2 tickets 0.5; +1 for a comment about payment problems, double billing or thinking of cancelling. A transparent heuristic, not a trained model."),
        ("Recent window", f"The last 6 months of data, from {since}."),
        ("Comment themes", "Assigned by keyword matching on a small set of known comment texts. The raw rate is high for every theme because customers who comment also open more tickets; read the adjusted lift."),
        ("Countries", "p-value from a two-proportion test of each country against all others. Treat a single p-value near 0.05 among 10 countries with caution."),
        ("Limits", causes.CAVEAT),
        ("Excluded data", "Support comments containing instructions aimed at automated tools are excluded from the analysis and only counted."),
    ]
    for i, (k, v) in enumerate(lines, start=1):
        _cell(ws, f"A{i}", k, bold=True, size=12 if v is None else 10)
        if v:
            _cell(ws, f"B{i}", v, wrap=True)
            ws.row_dimensions[i].height = 15 * (len(v) // 110 + 1)
    _widths(ws, {"A": 22, "B": 120})

    wb.calculation.fullCalcOnLoad = True  # make Excel compute the formulas when the file opens
    wb.save(path)
