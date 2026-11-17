import pytest

from customer_insights import analysis, causes


def cust(i, cancelled=0, payment="paid", tickets=0, plan="Basic", signup="2025-01-10", cdate=None, country="France"):
    return {"customer_id": i, "cancelled": cancelled, "last_payment_status": payment, "support_tickets": tickets,
            "plan": plan, "monthly_fee": 4.99, "country": country, "signup_date": signup, "cancelled_date": cdate}


def dataset():
    """600 synthetic customers with every group large enough to be analysed."""
    customers, comments = [], []
    for i in range(600):
        cancelled = int(i % 4 == 0)
        customers.append(cust(
            i, cancelled=cancelled,
            payment="failed" if i % 10 == 0 else "late" if i % 10 == 1 else "paid",
            tickets=[0, 0, 1, 3, 6][i % 5], plan=["Basic", "Standard", "Premium"][i % 3],
            cdate=f"2025-{2 + i % 8:02d}-20" if cancelled else None,
            country="France" if i % 2 else "Egypt"))
        if i % 3 == 0:
            comments.append({"comment_id": i, "customer_id": i, "created_at": "2025-09-10" if i % 2 else "2026-02-10",
                             "comment_text": "Price went up and I am not sure it's worth it anymore."})
    return customers, comments


def test_monthly_trend_counts_active_customers_at_start_of_month():
    customers = [cust(1, 1, cdate="2025-03-05"), cust(2), cust(3, 1, signup="2025-03-10", cdate="2025-03-20")]
    assert causes.monthly_trend(customers) == [
        {"month": "2025-03", "cancellations": 2, "active_at_start": 2, "rate": 1.0}]


def test_monthly_trend_includes_months_without_cancellations():
    customers = [cust(1, 1, cdate="2025-01-05"), cust(2, 1, cdate="2025-04-05"), cust(3)]
    assert [r["month"] for r in causes.monthly_trend(customers)] == ["2025-01", "2025-02", "2025-03", "2025-04"]


@pytest.mark.parametrize("last_month, expected", [("2026-09", "2026-04-01"), ("2026-03", "2025-10-01")])
def test_surge_start_is_six_months_back(last_month, expected):
    assert causes.surge_start([{"month": last_month}]) == expected


def test_risk_matrix_covers_every_customer():
    customers, _ = dataset()
    assert sum(r["customers"] for r in causes.risk_matrix(customers)) == len(customers)


def test_comment_theme_adjusts_for_ticket_volume():
    # high-ticket customers cancel more (50% vs 10%); the theme is only written by high-ticket customers
    customers = [cust(i, cancelled=int(i % 2 == 0), tickets=6) for i in range(100)]
    customers += [cust(100 + i, cancelled=int(i % 10 == 0)) for i in range(300)]
    comments = [{"comment_id": i, "customer_id": i, "created_at": "2026-01-01", "comment_text": "App keeps buffering"}
                for i in range(100)]
    theme = analysis.comment_themes(customers, comments)[0]
    assert theme["rate"] == 0.5                      # raw rate looks alarming...
    assert theme["adjusted_lift"] == pytest.approx(1.0)  # ...but adds nothing beyond ticket volume


def test_country_table_flags_a_real_difference_but_not_noise():
    # 'Highland' really cancels more (40%) than the others; 'Midland' (25%) matches the rest of the base
    customers = [cust(i, cancelled=int(i % 10 < 4), country="Highland") for i in range(200)]   # 80 / 200
    customers += [cust(1000 + i, cancelled=int(i % 10 == 0), country="Lowland") for i in range(200)]  # 20 / 200
    customers += [cust(2000 + i, cancelled=int(i % 4 == 0), country="Midland") for i in range(200)]    # 50 / 200
    rows = causes.country_table(customers)
    by = {r["country"]: r for r in rows}
    assert rows[0]["country"] == "Highland"                       # sorted by rate, highest first
    assert by["Highland"]["p_value"] < 0.001
    assert by["Midland"]["p_value"] > 0.9                         # same rate as everyone else: pure noise


def test_explain_reports_billing_and_support_causes():
    customers, comments = dataset()
    titles = [c["title"] for c in causes.explain(customers, comments)]
    assert "Billing failures (involuntary churn)" in titles
    assert "Support friction" in titles


def test_excel_workbook_has_charts_formulas_and_no_personal_data(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from customer_insights import excel

    customers, comments = dataset()
    path = tmp_path / "out.xlsx"
    excel.write_workbook(path, customers, comments)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["Summary", "Drivers", "Risk matrix", "Monthly trend", "Recent vs earlier",
                             "Countries", "Comment themes", "At-risk", "Notes"]
    assert wb["Summary"]["B6"].value == "=B5/B4"
    assert wb["Countries"]["D2"].value == "=C2/B2"
    assert sum(len(ws._charts) for ws in wb) >= 8
    text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
    assert "@" not in text and "full_name" not in text
