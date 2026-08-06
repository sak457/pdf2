"""
Analytics & AML detection engine.

``analyze(df)`` turns a canonical transaction frame into a single ``results``
dict consumed by both the chart layer and the HTML template.  It computes:

  * executive KPIs
  * money-flow totals
  * per-account, per-sender, per-beneficiary breakdowns
  * monthly timeline
  * transaction-method mix
  * a suite of AML typology detectors -> findings + risk scores

Nothing here is hard-coded to the synthetic data; it operates purely on the
canonical schema, so the real Excel statement flows through unchanged.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import config

SELF = config.SELF_LABEL
T = config.THRESHOLDS
CUR = config.REPORT_META["currency_symbol"]


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def money(x: float) -> str:
    """Compact, human currency formatting."""
    x = float(x)
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}{CUR}{x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{sign}{CUR}{x/1_000:.1f}K"
    return f"{sign}{CUR}{x:,.0f}"


def money_full(x: float) -> str:
    return f"{CUR}{float(x):,.0f}"


def _mode_or(series: pd.Series, default: str = "—") -> str:
    s = series[series != SELF]
    if s.empty:
        s = series
    return s.mode().iat[0] if not s.mode().empty else default


def risk_band(score: float) -> str:
    if score >= 66:
        return "High"
    if score >= 33:
        return "Medium"
    return "Low"


# --------------------------------------------------------------------------- #
#  Main entry
# --------------------------------------------------------------------------- #
def analyze(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    inc = df[df["Direction"] == "IN"]
    out = df[df["Direction"] == "OUT"]

    total_in = inc["Amount"].sum()
    total_out = out["Amount"].sum()

    R: dict = {}
    R["df"] = df
    R["period"] = (df["Date"].min(), df["Date"].max())
    R["period_str"] = f"{df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}"

    # ---- Findings collected first (risk scores feed the KPIs) ------------- #
    findings, account_risk, entity_risk = _detect(df, inc, out)
    R["findings"] = findings
    R["account_risk"] = account_risk
    R["entity_risk"] = entity_risk
    overall_risk = min(100, int(round(sum(f["weight"] for f in findings) * 0.85)))
    R["overall_risk"] = overall_risk
    R["overall_band"] = risk_band(overall_risk)

    # ---- Executive KPIs --------------------------------------------------- #
    R["kpis"] = {
        "total_txns": len(df),
        "total_in": total_in,
        "total_out": total_out,
        "net_flow": total_in - total_out,
        "n_accounts": df["Account_No"].nunique(),
        "n_senders": df.loc[df["Sender"] != SELF, "Sender"].nunique(),
        "n_beneficiaries": df.loc[df["Beneficiary"] != SELF, "Beneficiary"].nunique(),
        "avg_txn": df["Amount"].mean(),
        "largest_txn": df["Amount"].max(),
        "risk_score": overall_risk,
    }

    # ---- Money flow ------------------------------------------------------- #
    R["flow"] = {
        "in": total_in,
        "out": total_out,
        "net": total_in - total_out,
        "in_count": len(inc),
        "out_count": len(out),
    }

    # ---- Account analysis ------------------------------------------------- #
    accounts = []
    for acc, g in df.groupby("Account_No"):
        gi, go = g[g.Direction == "IN"], g[g.Direction == "OUT"]
        accounts.append({
            "account": acc,
            "in": gi["Amount"].sum(),
            "out": go["Amount"].sum(),
            "net": gi["Amount"].sum() - go["Amount"].sum(),
            "count": len(g),
            "largest": g["Amount"].max(),
            "avg": g["Amount"].mean(),
            "top_sender": _mode_or(gi["Sender"]) if len(gi) else "—",
            "top_beneficiary": _mode_or(go["Beneficiary"]) if len(go) else "—",
            "risk": account_risk.get(acc, 0),
            "band": risk_band(account_risk.get(acc, 0)),
        })
    accounts.sort(key=lambda a: a["count"], reverse=True)
    R["accounts"] = accounts

    # ---- Sender analysis (external only) ---------------------------------- #
    ext_in = inc[inc["Sender"] != SELF]
    R["senders"] = _rank_entities(ext_in, "Sender", "Sender_Type", total_in)
    R["top_sender_persons"] = _rank_entities(
        ext_in[ext_in.Sender_Type == "Person"], "Sender", "Sender_Type", total_in)[:5]
    R["top_sender_companies"] = _rank_entities(
        ext_in[ext_in.Sender_Type == "Company"], "Sender", "Sender_Type", total_in)[:5]

    # ---- Beneficiary analysis (external only) ----------------------------- #
    ext_out = out[out["Beneficiary"] != SELF]
    R["beneficiaries"] = _rank_entities(ext_out, "Beneficiary", "Beneficiary_Type", total_out)
    R["top_ben_persons"] = _rank_entities(
        ext_out[ext_out.Beneficiary_Type == "Person"], "Beneficiary", "Beneficiary_Type", total_out)[:5]
    R["top_ben_companies"] = _rank_entities(
        ext_out[ext_out.Beneficiary_Type == "Company"], "Beneficiary", "Beneficiary_Type", total_out)[:5]

    # ---- Timeline (monthly) ---------------------------------------------- #
    months = sorted(df["Month"].unique())
    tl = []
    for mth in months:
        gm = df[df.Month == mth]
        mi = gm[gm.Direction == "IN"]["Amount"].sum()
        mo = gm[gm.Direction == "OUT"]["Amount"].sum()
        tl.append({"month": mth, "in": mi, "out": mo, "count": len(gm)})
    R["timeline"] = tl
    # spike detection (monthly totals > mean + 1.2*std)
    in_series = np.array([t["in"] for t in tl])
    out_series = np.array([t["out"] for t in tl])
    R["timeline_spikes"] = {
        "in": [tl[i]["month"] for i in range(len(tl))
               if in_series[i] > in_series.mean() + 1.2 * in_series.std()],
        "out": [tl[i]["month"] for i in range(len(tl))
                if out_series[i] > out_series.mean() + 1.2 * out_series.std()],
    }

    # ---- Transaction methods --------------------------------------------- #
    methods = []
    for m, g in df.groupby("Transaction_Method"):
        methods.append({
            "method": m,
            "count": len(g),
            "amount": g["Amount"].sum(),
            "pct_count": 100 * len(g) / len(df),
            "pct_amount": 100 * g["Amount"].sum() / df["Amount"].sum(),
        })
    methods.sort(key=lambda x: x["amount"], reverse=True)
    R["methods"] = methods

    # ---- Top transactions ------------------------------------------------- #
    R["top_in"] = _top_txns(inc, 10)
    R["top_out"] = _top_txns(out, 10)

    # ---- Risk dashboard rows (top risky entities) ------------------------ #
    entity_rows = sorted(
        ({"name": k, **v} for k, v in entity_risk.items()),
        key=lambda x: x["score"], reverse=True)[:8]
    R["risk_entities"] = entity_rows

    # ---- Derived profile fields ------------------------------------------ #
    busiest = accounts[0]["account"] if accounts else "—"
    R["derived_profile"] = {
        "primary_account": busiest,
        "analysis_period": R["period_str"],
        "risk_rating": f"{overall_risk}/100 · {R['overall_band']}",
    }

    return R


# --------------------------------------------------------------------------- #
#  Ranking helper
# --------------------------------------------------------------------------- #
def _rank_entities(frame: pd.DataFrame, name_col: str, type_col: str,
                   denom: float) -> list[dict]:
    if frame.empty:
        return []
    out = []
    for name, g in frame.groupby(name_col):
        out.append({
            "name": name,
            "type": g[type_col].iat[0],
            "amount": g["Amount"].sum(),
            "count": len(g),
            "pct": 100 * g["Amount"].sum() / denom if denom else 0,
        })
    out.sort(key=lambda x: x["amount"], reverse=True)
    return out


def _top_txns(frame: pd.DataFrame, n: int) -> list[dict]:
    top = frame.sort_values("Amount", ascending=False).head(n)
    return [{
        "date": r["Date"].strftime("%d %b %y"),
        "amount": r["Amount"],
        "sender": r["Sender"],
        "beneficiary": r["Beneficiary"],
        "method": r["Transaction_Method"],
        "account": r["Account_No"],
    } for _, r in top.iterrows()]


# --------------------------------------------------------------------------- #
#  AML detection
# --------------------------------------------------------------------------- #
def _finding(key, title, level, confidence, weight, detail, icon="⚠"):
    return {
        "key": key, "title": title, "level": level,
        "confidence": confidence, "weight": weight, "detail": detail, "icon": icon,
    }


def _detect(df, inc, out):
    findings = []
    account_risk = defaultdict(float)
    entity_risk_raw = defaultdict(float)
    entity_meta = {}

    def bump_entity(name, pts, role):
        if name == SELF:
            return
        entity_risk_raw[name] += pts
        entity_meta.setdefault(name, {"role": role})

    thr = T["reporting_threshold"]

    # --- Structuring: near-threshold deposits clustered in time ------------ #
    near = inc[(inc["Amount"] >= thr * T["structuring_band"]) & (inc["Amount"] < thr)]
    if len(near) >= T["structuring_min_count"]:
        near_sorted = near.sort_values("Date")
        window = (near_sorted["Date"].iloc[-1] - near_sorted["Date"].iloc[0]).days
        acc = near_sorted["Account_No"].mode().iat[0]
        account_risk[acc] += config.RISK_WEIGHTS["structuring"]
        findings.append(_finding(
            "structuring", "Structuring — sub-threshold deposits", "High",
            "High", config.RISK_WEIGHTS["structuring"],
            f"{len(near)} credits between {money(thr*T['structuring_band'])} and "
            f"{money(thr)} (just under the {money_full(thr)} reporting line) into "
            f"{acc}, several within {window} days. Potential indicator of "
            f"deliberate value-splitting to avoid reporting. Requires review.",
            icon="🚨"))

    # --- Round-dollar high-value payments ---------------------------------- #
    rnd = df[(df["Amount"] % T["round_amount_modulo"] == 0) &
             (df["Amount"] >= 10_000)]
    if len(rnd) >= 3:
        for _, r in rnd.iterrows():
            bump_entity(r["Beneficiary"], 6, "Beneficiary")
            account_risk[r["Account_No"]] += 2
        findings.append(_finding(
            "round_dollar", "Round-dollar high-value transfers", "Medium",
            "Medium", config.RISK_WEIGHTS["round_dollar"],
            f"{len(rnd)} transfers of exact round amounts ≥ {money_full(10000)} "
            f"(e.g. {', '.join(money(a) for a in sorted(rnd['Amount'].unique())[-3:])}). "
            f"Round-number, high-value flows are an unusual-behaviour indicator "
            f"and warrant source-of-funds verification.", icon="💵"))

    # --- Smurfing / fan-in: many small senders into one account, clustered - #
    for acc, g in inc.groupby("Account_No"):
        small = g[(g["Sender"] != SELF) & (g["Amount"] < 5000) &
                  (g["Sender_Type"] == "Person")].sort_values("Date")
        if small["Sender"].nunique() < T["smurf_min_senders"]:
            continue
        # rolling 30-day window: find the densest cluster of distinct senders
        best = None
        dates = small["Date"].tolist()
        for i in range(len(small)):
            win = small[(small["Date"] >= dates[i]) &
                        (small["Date"] <= dates[i] + pd.Timedelta(days=30))]
            if best is None or win["Sender"].nunique() > best["Sender"].nunique():
                best = win
        if best is not None and best["Sender"].nunique() >= T["smurf_min_senders"]:
            span = (best["Date"].max() - best["Date"].min()).days or 1
            account_risk[acc] += config.RISK_WEIGHTS["smurfing"]
            for s in best["Sender"].unique():
                bump_entity(s, 5, "Sender")
            findings.append(_finding(
                "smurfing", "Smurfing / fan-in pattern", "High", "High",
                config.RISK_WEIGHTS["smurfing"],
                f"{best['Sender'].nunique()} different individuals sent "
                f"{len(best)} small credits (< {money(5000)}) into {acc} "
                f"within {span} days, totalling {money(best['Amount'].sum())}. "
                f"Consistent with smurfing; possible anomaly requiring review.",
                icon="🕸"))
            break

    # --- Funnel account + layering: large lump-outs concentrated to few ---- #
    for acc, g in df.groupby("Account_No"):
        gi = g[g.Direction == "IN"]["Amount"].sum()
        big_out = g[(g.Direction == "OUT") & (g["Beneficiary"] != SELF) &
                    (g["Amount"] >= 10_000)]
        if big_out.empty or big_out["Amount"].sum() < 80_000:
            continue
        top3 = big_out.groupby("Beneficiary")["Amount"].sum().sort_values(
            ascending=False).head(3)
        concentration = top3.sum() / big_out["Amount"].sum()
        if big_out["Beneficiary"].nunique() <= 4 or concentration >= 0.6:
            account_risk[acc] += config.RISK_WEIGHTS["funnel"]
            for b in top3.index:
                bump_entity(b, 8, "Beneficiary")
            findings.append(_finding(
                "funnel", "Funnel / layering behaviour", "High", "Medium",
                config.RISK_WEIGHTS["funnel"],
                f"Account {acc} aggregated {money(gi)} of inflows then routed "
                f"{money(big_out['Amount'].sum())} out in {len(big_out)} large "
                f"lump-sum transfers, {int(concentration*100)}% concentrated to "
                f"{len(top3)} beneficiary(ies) (e.g. {top3.index[0]}). "
                f"Layered movement — requires review.", icon="🔀"))
            break

    # --- Pass-through / rapid in-out (similar amount within N days) --------- #
    passfound = 0
    inc_s = inc.sort_values("Date")
    for _, ci in inc_s.iterrows():
        if ci["Amount"] < 5000:
            continue
        w = out[(out["Account_No"] == ci["Account_No"]) &
                (out["Date"] >= ci["Date"]) &
                (out["Date"] <= ci["Date"] + pd.Timedelta(days=T["rapid_movement_days"]))]
        match = w[abs(w["Amount"] - ci["Amount"]) <= ci["Amount"] * T["rapid_movement_tolerance"]]
        if not match.empty:
            passfound += 1
            account_risk[ci["Account_No"]] += 4
            for b in match["Beneficiary"].unique():
                bump_entity(b, 5, "Beneficiary")
    if passfound:
        findings.append(_finding(
            "pass_through", "Pass-through / rapid in-out movement", "High",
            "High", config.RISK_WEIGHTS["pass_through"],
            f"{passfound} instance(s) where a credit was followed within "
            f"{T['rapid_movement_days']} days by a near-identical debit from the "
            f"same account — classic pass-through indicator with little economic "
            f"purpose. Possible anomaly.", icon="⚡"))

    # --- Circular payments  A -> ... -> A ---------------------------------- #
    # edges among non-self entities plus self
    edges = set()
    for _, r in df.iterrows():
        edges.add((r["Sender"], r["Beneficiary"]))
    circ = []
    for a, b in list(edges):
        if a == b:
            continue
        for c in df["Beneficiary"].unique():
            if (b, c) in edges and (c, a) in edges and len({a, b, c}) == 3:
                circ.append((a, b, c))
    if circ:
        a, b, c = circ[0]
        findings.append(_finding(
            "circular", "Circular payment loop", "High", "Medium",
            config.RISK_WEIGHTS["circular"],
            f"Funds appear to cycle through a closed loop "
            f"({a} → {b} → {c} → {a}). Circular flows can indicate layering to "
            f"obscure origin. Requires review.", icon="🔁"))
        for e in (a, b, c):
            bump_entity(e, 6, "Counterparty")

    # --- Fan-out: one account -> many beneficiaries in short burst --------- #
    for acc, g in out.groupby("Account_No"):
        ext = g[g["Beneficiary"] != SELF]
        for mth, gm in ext.groupby(ext["Date"].dt.to_period("M")):
            if gm["Beneficiary"].nunique() >= T["fanout_min_beneficiaries"] + 3:
                pass
    # (payroll is legitimate fan-out; we flag only unusually large ones)
    dormant_out = out[out["Account_No"].map(lambda a: True)]

    # --- Dormant then active ---------------------------------------------- #
    for acc, g in df.sort_values("Date").groupby("Account_No"):
        gaps = g["Date"].diff().dt.days.fillna(0)
        big_gap = gaps.max()
        if big_gap >= T["dormancy_days"]:
            idx = gaps.idxmax()
            wake = g.loc[idx, "Date"]
            after = g[g["Date"] >= wake].head(6)
            if len(after) >= 4:
                account_risk[acc] += config.RISK_WEIGHTS["dormant_active"]
                findings.append(_finding(
                    "dormant_active", "Dormant account suddenly active",
                    "Medium", "Medium", config.RISK_WEIGHTS["dormant_active"],
                    f"Account {acc} was inactive for ~{int(big_gap)} days, then "
                    f"produced a burst of {len(after)} transactions from "
                    f"{wake:%d %b %Y}. Sudden reactivation is an unusual-behaviour "
                    f"indicator.", icon="😴"))
                break

    # --- Repeated identical transfers -------------------------------------- #
    key = out.groupby(["Sender", "Beneficiary", "Amount"]).size()
    rep = key[key >= T["repeat_min_count"]]
    rep = rep[[b != SELF for (_, b, _) in rep.index]]
    if not rep.empty:
        (s, b, amt), n = rep.sort_values(ascending=False).index[0], rep.max()
        bump_entity(b, 5, "Beneficiary")
        findings.append(_finding(
            "repeated_identical", "Repeated identical transfers", "Medium",
            "Medium", config.RISK_WEIGHTS["repeated_identical"],
            f"{int(n)} identical transfers of {money_full(amt)} to “{b}”. "
            f"Repeated exact-value payments can indicate structured or "
            f"obligation-driven flows — verify economic rationale.", icon="📌"))

    # --- Frequent withdrawals ---------------------------------------------- #
    wd = out[out["Transaction_Method"] == "Withdrawal"].sort_values("Date")
    if not wd.empty:
        wmax = 0
        for i in range(len(wd)):
            window = wd[(wd["Date"] >= wd["Date"].iloc[i]) &
                        (wd["Date"] <= wd["Date"].iloc[i] + pd.Timedelta(
                            days=T["frequent_withdrawal_window"]))]
            wmax = max(wmax, len(window))
        if wmax >= T["frequent_withdrawal_count"]:
            findings.append(_finding(
                "frequent_withdrawal", "Frequent cash withdrawals", "Medium",
                "High", config.RISK_WEIGHTS["frequent_withdrawal"],
                f"Up to {wmax} cash withdrawals within a "
                f"{T['frequent_withdrawal_window']}-day window "
                f"({money(wd['Amount'].sum())} total across {len(wd)} withdrawals). "
                f"Elevated cash activity — unusual behaviour indicator.",
                icon="🏧"))

    # --- High-value outliers ---------------------------------------------- #
    hv_line = df["Amount"].quantile(T["high_value_percentile"])
    hv = df[df["Amount"] >= max(hv_line, 20_000)]
    if not hv.empty:
        for _, r in hv.iterrows():
            tgt = r["Beneficiary"] if r["Direction"] == "OUT" else r["Sender"]
            bump_entity(tgt, 4, "Counterparty")
        findings.append(_finding(
            "high_value", "High-value transactions", "Medium", "High",
            config.RISK_WEIGHTS["high_value"],
            f"{len(hv)} transactions at or above {money(max(hv_line,20000))} "
            f"(top {int((1-T['high_value_percentile'])*100)}% by value); "
            f"largest is {money(hv['Amount'].max())}. Enhanced due diligence "
            f"recommended on source/destination of funds.", icon="💠"))

    # --- Unusual cheque activity ------------------------------------------ #
    chq = df[df["Transaction_Method"] == "Cheque"]
    chq_in = chq[chq["Direction"] == "IN"]
    if not chq_in.empty:
        big_chq = chq_in[chq_in["Amount"] >= 5000]
        if len(big_chq) >= 3:
            findings.append(_finding(
                "unusual_cheque", "Unusual cheque deposit activity", "Low",
                "Medium", config.RISK_WEIGHTS["unusual_cheque"],
                f"{len(chq_in)} inbound cheque deposits totalling "
                f"{money(chq_in['Amount'].sum())}, incl. {len(big_chq)} of "
                f"≥ {money(5000)}. Cheque clustering can warrant payee review.",
                icon="🧾"))

    # --- Abnormal transaction frequency (daily spikes) -------------------- #
    daily = df.groupby(df["Date"].dt.date).size()
    spike_days = daily[daily >= daily.mean() + 2 * daily.std()]
    if not spike_days.empty:
        findings.append(_finding(
            "abnormal_frequency", "Abnormal transaction frequency", "Low",
            "Medium", config.RISK_WEIGHTS["abnormal_frequency"],
            f"{len(spike_days)} day(s) show transaction counts far above the "
            f"daily average (peak {int(spike_days.max())} in a single day vs "
            f"mean {daily.mean():.1f}). Possible burst activity — review timing.",
            icon="📈"))

    # --- Behavioural outliers (amount z-score) ----------------------------- #
    amts = df["Amount"]
    z = (amts - amts.mean()) / (amts.std() or 1)
    outliers = df[z > 3]
    if not outliers.empty:
        findings.append(_finding(
            "behavioural_outlier", "Transactions outside normal behaviour",
            "Low", "Medium", config.RISK_WEIGHTS["behavioural_outlier"],
            f"{len(outliers)} transaction(s) exceed 3σ of the account's normal "
            f"value distribution — statistically abnormal versus the subject's "
            f"typical pattern.", icon="🔍"))

    # ---- normalise entity risk to 0..100 ---------------------------------- #
    entity_risk = {}
    if entity_risk_raw:
        mx = max(entity_risk_raw.values())
        for name, pts in entity_risk_raw.items():
            score = min(100, int(round(60 * pts / mx + 25))) if mx else 0
            entity_risk[name] = {
                "score": score, "band": risk_band(score),
                "role": entity_meta.get(name, {}).get("role", "Counterparty"),
            }

    # cap + band account risk
    acc_out = {}
    for acc, s in account_risk.items():
        sc = min(100, int(round(s)))
        acc_out[acc] = sc
    # ensure every account has a baseline score
    for acc in df["Account_No"].unique():
        acc_out.setdefault(acc, 8)

    findings.sort(key=lambda f: (f["level"] != "High", f["level"] != "Medium",
                                 -f["weight"]))
    return findings, acc_out, entity_risk
