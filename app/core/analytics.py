"""
Analytics & AML typology engine (POI schema) — every finding carries an
**evidence** DataFrame and a **basis** string so the UI can show *why* a flag
fired and *on what data*.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

CURRENCY = "AED "

EVID_COLS = ["date", "direction", "account_no", "counterparty",
             "counterparty_type", "amount", "transaction_method"]

THRESHOLDS = dict(
    reporting_threshold=10_000, structuring_band=0.90, structuring_min=3,
    high_value_pct=0.97, rapid_days=3, rapid_tol=0.15, smurf_min=4,
    fanout_min=6, repeat_min=4, dormancy_days=45, round_mod=1_000,
    freq_wd_count=8, freq_wd_window=30, roundtrip_days=45,
)

WEIGHTS = dict(
    structuring=22, smurfing=18, funnel=16, pass_through=15, round_trip=20,
    round_dollar=8, own_churn=12, fan_out=12, dormant_active=12,
    repeated_identical=10, frequent_withdrawal=10, high_value=10,
    unusual_cheque=9, abnormal_frequency=9, behavioural_outlier=8,
)


def money(x) -> str:
    x = float(x); s = "-" if x < 0 else ""; x = abs(x)
    if x >= 1e6:
        return f"{s}{CURRENCY}{x/1e6:.2f}M"
    if x >= 1e3:
        return f"{s}{CURRENCY}{x/1e3:.1f}K"
    return f"{s}{CURRENCY}{x:,.0f}"


def money_full(x) -> str:
    return f"{CURRENCY}{float(x):,.0f}"


def risk_band(s) -> str:
    return "High" if s >= 66 else "Medium" if s >= 33 else "Low"


def score_from(findings) -> int:
    """Overall 0–100 risk recomputed from an (already-filtered) findings list."""
    return min(100, int(round(sum(f["weight"] for f in findings) * 0.85)))


def spike_breakdown(df: pd.DataFrame, month: str) -> dict:
    """Who sent / received during a spike month."""
    gm = df[df.month == month]
    gi = gm[gm.direction == "in"]
    go = gm[gm.direction == "out"]
    def rank(frame, denom):
        ext = frame[~frame.counterparty_type.isin(["POI", "Internal"])]
        if ext.empty:
            return []
        r = (ext.groupby("counterparty")
             .agg(amount=("amount", "sum"), count=("amount", "size")).reset_index()
             .sort_values("amount", ascending=False).head(6))
        return [dict(name=x.counterparty, amount=x.amount, count=int(x.count),
                     pct=100 * x.amount / denom if denom else 0) for x in r.itertuples()]
    return dict(month=month, inflow=gi.amount.sum(), outflow=go.amount.sum(),
                in_count=len(gi), out_count=len(go),
                senders=rank(gi, gi.amount.sum()), beneficiaries=rank(go, go.amount.sum()),
                evidence=gm[EVID_COLS].sort_values("amount", ascending=False))


def _acc_masks(df, acc):
    in_m = (df.direction == "in") & df.accounts.apply(lambda l: acc in l)
    out_m = (df.direction == "out") & df.accounts.apply(lambda l: acc in l)
    own_in = (df.direction == "own") & (df.account_to == acc)
    own_out = (df.direction == "own") & (df.account_from == acc)
    return in_m, out_m, own_in, own_out


def account_details(df: pd.DataFrame) -> list[dict]:
    """Per-account incoming / outgoing / current balance + spike detection
    (based on the monthly inflow-vs-outflow series for that account)."""
    accts = sorted(set(a for row in df.accounts for a in row))
    out = []
    for acc in accts:
        in_m, out_m, own_in, own_out = _acc_masks(df, acc)
        in_ext = df[in_m].amount.sum()
        in_own = df[own_in].amount.sum()
        out_ext = df[out_m].amount.sum()
        out_own = df[own_out].amount.sum()
        inflow = in_ext + in_own
        outflow = out_ext + out_own
        g = df[in_m | out_m | own_in | own_out]
        months = sorted(g.month.unique())
        mi, mo = [], []
        for mth in months:
            gm = g[g.month == mth]
            mi.append(gm[(gm.direction == "in") | ((gm.direction == "own") & (gm.account_to == acc))].amount.sum())
            mo.append(gm[(gm.direction == "out") | ((gm.direction == "own") & (gm.account_from == acc))].amount.sum())
        spike_months = []
        if len(months) >= 3:
            mi_a, mo_a = np.array(mi), np.array(mo)
            for i, mth in enumerate(months):
                if mi_a[i] > mi_a.mean() + 1.2 * mi_a.std() or mo_a[i] > mo_a.mean() + 1.2 * mo_a.std():
                    spike_months.append(mth)
        out.append(dict(account=acc, inflow=inflow, outflow=outflow,
                        in_ext=in_ext, in_own=in_own, out_ext=out_ext, out_own=out_own,
                        balance=inflow - outflow, count=int((in_m | out_m | own_in | own_out).sum()),
                        spike=bool(spike_months), spike_months=spike_months))
    return out


SCHEMA_COLS = ["date", "direction", "account_no", "sender", "sender_name", "sender_type",
               "beneficiary", "beneficiary_name", "beneficiary_type", "amount",
               "transaction_method"]


def account_spike_txns(df: pd.DataFrame, acc: str, months: list[str]) -> pd.DataFrame:
    """Transactions in an account's spike months (ALL dataset columns), plus an
    IN/OUT flag relative to this account."""
    in_m, out_m, own_in, own_out = _acc_masks(df, acc)
    g = df[(in_m | out_m | own_in | own_out) & df.month.isin(months)].copy()

    def flow(r):
        if r["direction"] == "in" or (r["direction"] == "own" and r["account_to"] == acc):
            return "IN"
        return "OUT"
    g["flow"] = g.apply(flow, axis=1)
    cols = [c for c in SCHEMA_COLS if c in g.columns]
    return g[["flow"] + cols].sort_values("date")


def account_top(df: pd.DataFrame, acc: str, direction: str, n: int = 5) -> list[dict]:
    """Top-n external senders (direction='in') or receivers ('out') for an account."""
    in_m, out_m, _, _ = _acc_masks(df, acc)
    g = df[(in_m if direction == "in" else out_m) &
           (~df.counterparty_type.isin(["POI", "Internal"]))]
    if g.empty:
        return []
    r = (g.groupby(["counterparty", "counterparty_type"])
         .agg(amount=("amount", "sum"), count=("amount", "size")).reset_index()
         .sort_values("amount", ascending=False).head(n))
    return [dict(name=x.counterparty, type=x.counterparty_type, amount=x.amount,
                 count=int(x.count)) for x in r.itertuples()]


def counterparty_aggregates(df: pd.DataFrame) -> dict:
    """Per external counterparty: type, own account number(s), POI accounts used,
    total inbound and total outbound (POI-relative), and count. Keyed by name."""
    ext = df[~df.counterparty_type.isin(["POI", "Internal"])]
    agg = {}
    has_acc = "counterparty_account" in ext.columns
    has_det = "counterparty_details" in ext.columns
    has_os = "counterparty_osint" in ext.columns
    for name, g in ext.groupby("counterparty"):
        accts = sorted(set(str(a) for a in g["counterparty_account"].unique()
                           if str(a).strip())) if has_acc else []
        details = ""
        if has_det:
            nz = [str(x).strip() for x in g["counterparty_details"] if str(x).strip()]
            details = nz[0] if nz else ""
        osint = bool(g["counterparty_osint"].any()) if has_os else False
        agg[name] = dict(
            name=name, type=g.counterparty_type.iat[0], accounts=accts,
            poi_accounts=sorted(set(a for row in g.accounts for a in row)),
            total_in=g[g.direction == "in"].amount.sum(),
            total_out=g[g.direction == "out"].amount.sum(),
            count=len(g), details=details, osint=osint)
    return agg


def multi_account_counterparties(df: pd.DataFrame, min_accounts: int = 2) -> list[dict]:
    """Counterparties that moved money with the POI across several of the POI's
    accounts (a spreading pattern). Returns one row per counterparty with the
    set of POI accounts touched, type, direction and totals."""
    ext = df[(~df.counterparty_type.isin(["POI", "Internal"])) & (df.counterparty != "Unknown")]
    rows = []
    for cp, g in ext.groupby("counterparty"):
        accts = sorted(set(g.account_from) | set(g.account_to))
        accts = [a for a in accts if a]
        if len(accts) < min_accounts:
            continue
        inflow = g[g.direction == "in"].amount.sum()
        outflow = g[g.direction == "out"].amount.sum()
        direction = ("both" if inflow > 0 and outflow > 0 else "in" if inflow > 0 else "out")
        rows.append(dict(counterparty=cp, type=g.counterparty_type.iat[0],
                         n_accounts=len(accts), accounts=accts, inflow=inflow,
                         outflow=outflow, direction=direction, count=len(g)))
    rows.sort(key=lambda r: (r["n_accounts"], r["inflow"] + r["outflow"]), reverse=True)
    return rows


def _f(key, title, icon, level, conf, weight, why, basis, evidence, metric=None):
    return dict(key=key, title=title, icon=icon, level=level, confidence=conf,
                weight=weight, why=why, basis=basis,
                evidence=evidence[EVID_COLS].copy() if evidence is not None
                else pd.DataFrame(columns=EVID_COLS),
                metric=metric or {})


# --------------------------------------------------------------------------- #
def analyze(df: pd.DataFrame) -> dict:
    df = df.copy()
    inc = df[df.direction == "in"]
    out = df[df.direction == "out"]
    own = df[df.direction == "own"]
    ext_in = inc[~inc.counterparty_type.isin(["POI", "Internal"])]
    ext_out = out[~out.counterparty_type.isin(["POI", "Internal"])]

    total_in = inc.amount.sum()
    total_out = out.amount.sum()

    findings, acc_risk, ent_risk = _detect(df, inc, out, own, ext_in, ext_out)
    overall = min(100, int(round(sum(f["weight"] for f in findings) * 0.85)))

    R = dict(df=df, inc=inc, out=out, own=own)
    R["period"] = (df.date.min(), df.date.max())
    R["period_str"] = f"{df.date.min():%d %b %Y} – {df.date.max():%d %b %Y}"
    R["findings"] = findings
    R["overall_risk"] = overall
    R["overall_band"] = risk_band(overall)
    R["account_risk"] = acc_risk
    R["entity_risk"] = ent_risk

    R["kpis"] = dict(
        total_txns=len(df), total_in=total_in, total_out=total_out,
        net=total_in - total_out, own_total=own.amount.sum(),
        n_accounts=len(set(a for row in df.accounts for a in row)),
        n_senders=ext_in.counterparty.nunique(),
        n_beneficiaries=ext_out.counterparty.nunique(),
        avg=df.amount.mean(), largest=df.amount.max(), risk=overall,
        n_high=sum(f["level"] == "High" for f in findings),
        n_med=sum(f["level"] == "Medium" for f in findings),
        n_flags=len(findings),
    )
    R["flow"] = dict(inflow=total_in, outflow=total_out, net=total_in - total_out,
                     own=own.amount.sum(), in_count=len(inc), out_count=len(out),
                     own_count=len(own))

    # accounts
    accts = []
    all_accounts = sorted(set(a for row in df.accounts for a in row))
    for acc in all_accounts:
        mask_in = df.accounts.apply(lambda a: acc in a) & (df.direction == "in")
        mask_out = df.accounts.apply(lambda a: acc in a) & (df.direction == "out")
        mask_any = df.accounts.apply(lambda a: acc in a)
        g = df[mask_any]
        gi, go = df[mask_in], df[mask_out]
        top_cp = "—"
        ext = g[~g.counterparty_type.isin(["POI", "Internal"])]
        if len(ext):
            top_cp = ext.counterparty.mode().iat[0]
        accts.append(dict(
            account=acc, inflow=gi.amount.sum(), outflow=go.amount.sum(),
            count=int(mask_any.sum()), largest=g.amount.max() if len(g) else 0,
            avg=g.amount.mean() if len(g) else 0, top_counterparty=top_cp,
            risk=int(acc_risk.get(acc, 8)), band=risk_band(acc_risk.get(acc, 8))))
    accts.sort(key=lambda a: a["count"], reverse=True)
    R["accounts"] = accts

    R["senders"] = _rank(ext_in, total_in)
    R["beneficiaries"] = _rank(ext_out, total_out)

    # timeline
    tl = []
    for m in sorted(df.month.unique()):
        gm = df[df.month == m]
        tl.append(dict(month=m, inflow=gm[gm.direction == "in"].amount.sum(),
                       outflow=gm[gm.direction == "out"].amount.sum(),
                       count=len(gm)))
    R["timeline"] = tl
    ins = np.array([t["inflow"] for t in tl]); outs = np.array([t["outflow"] for t in tl])
    R["spikes"] = dict(
        inflow=[tl[i]["month"] for i in range(len(tl)) if ins[i] > ins.mean() + 1.2 * ins.std()],
        outflow=[tl[i]["month"] for i in range(len(tl)) if outs[i] > outs.mean() + 1.2 * outs.std()])

    # methods
    meth = []
    for m, g in df.groupby("transaction_method"):
        meth.append(dict(method=m, count=len(g), amount=g.amount.sum(),
                         pct=100 * g.amount.sum() / df.amount.sum()))
    meth.sort(key=lambda x: x["amount"], reverse=True)
    R["methods"] = meth

    R["top_in"] = _top(inc, 10)
    R["top_out"] = _top(out, 10)

    # risk components
    R["risk_components"] = [dict(title=f["title"], level=f["level"],
                                 confidence=f["confidence"], weight=f["weight"])
                            for f in findings]
    R["bluf"] = _bluf(R)
    return R


def _rank(frame, denom):
    if frame.empty:
        return []
    rows = []
    for name, g in frame.groupby("counterparty"):
        rows.append(dict(name=name, type=g.counterparty_type.iat[0],
                         amount=g.amount.sum(), count=len(g),
                         pct=100 * g.amount.sum() / denom if denom else 0))
    rows.sort(key=lambda x: x["amount"], reverse=True)
    return rows


def _top(frame, n):
    t = frame.sort_values("amount", ascending=False).head(n)
    return [dict(date=r["date"], amount=r["amount"], counterparty=r["counterparty"],
                 direction=r["direction"], method=r["transaction_method"],
                 account=r["account_no"]) for _, r in t.iterrows()]


def _bluf(R):
    k = R["kpis"]
    top = R["findings"][0]["title"] if R["findings"] else "no material indicators"
    largest = R["top_out"][0] if R["top_out"] else (R["top_in"][0] if R["top_in"] else None)
    lg = ""
    if largest:
        lg = (f" Largest single movement: {money(largest['amount'])} "
              f"{'to' if largest['direction']=='out' else 'from'} "
              f"{largest['counterparty']} on {largest['date']:%d %b %Y}.")
    return (
        f"Over {R['period_str']}, the subject operated {k['n_accounts']} account(s) "
        f"across {k['total_txns']} transactions — inflow {money(k['total_in'])}, "
        f"outflow {money(k['total_out'])} (net {money(k['net'])}). "
        f"Automated monitoring raised {k['n_flags']} typology indicator(s) "
        f"({k['n_high']} high, {k['n_med']} medium), giving an overall risk of "
        f"{k['risk']}/100 ({R['overall_band']}). Most significant: {top}.{lg} "
        f"Indicators are decision-support only and require analyst review.")


# --------------------------------------------------------------------------- #
#  Detection
# --------------------------------------------------------------------------- #
def _detect(df, inc, out, own, ext_in, ext_out):
    T = THRESHOLDS
    F = []
    acc_risk = defaultdict(float)
    ent_raw = defaultdict(float)
    ent_role = {}

    def hit_acc(acc, pts):
        for a in str(acc).split("|"):
            acc_risk[a.strip()] += pts

    def hit_ent(name, pts, role):
        if name in ("POI", "Internal transfer", "Unknown"):
            return
        ent_raw[name] += pts; ent_role.setdefault(name, role)

    thr = T["reporting_threshold"]

    # structuring
    near = ext_in[(ext_in.amount >= thr * T["structuring_band"]) & (ext_in.amount < thr)]
    if len(near) >= T["structuring_min"]:
        acc = near.account_no.mode().iat[0]
        win = (near.date.max() - near.date.min()).days
        hit_acc(acc, WEIGHTS["structuring"])
        F.append(_f("structuring", "Structuring — sub-threshold deposits", "🚨",
                    "High", "High", WEIGHTS["structuring"],
                    f"{len(near)} inbound credits sit just below the "
                    f"{money_full(thr)} reporting line and cluster within {win} days — "
                    f"a pattern consistent with deliberate value-splitting to avoid a "
                    f"reporting trigger.",
                    f"Rule: inbound amount in [{money(thr*T['structuring_band'])}, "
                    f"{money(thr)}) · count ≥ {T['structuring_min']}. "
                    f"Observed: {len(near)} credits, total {money(near.amount.sum())}.",
                    near, dict(count=len(near), total=near.amount.sum(), window_days=win)))

    # smurfing / fan-in
    for acc, g in ext_in.groupby("account_no"):
        small = g[g.amount < 5000].sort_values("date")
        if small.counterparty.nunique() < T["smurf_min"]:
            continue
        dts = small.date.tolist()
        best = max((small[(small.date >= d) & (small.date <= d + pd.Timedelta(days=30))]
                    for d in dts), key=lambda w: w.counterparty.nunique())
        if best.counterparty.nunique() >= T["smurf_min"]:
            span = (best.date.max() - best.date.min()).days or 1
            hit_acc(acc, WEIGHTS["smurfing"])
            for c in best.counterparty.unique():
                hit_ent(c, 5, "Sender")
            F.append(_f("smurfing", "Smurfing / fan-in", "🕸️", "High", "High",
                        WEIGHTS["smurfing"],
                        f"{best.counterparty.nunique()} distinct low-value senders paid "
                        f"{len(best)} credits into {acc} within {span} days "
                        f"(total {money(best.amount.sum())}) — consistent with smurfing, "
                        f"where a larger sum is broken across many small deposits.",
                        f"Rule: ≥ {T['smurf_min']} distinct senders, each < {money(5000)}, "
                        f"into one account within 30 days.",
                        best, dict(senders=best.counterparty.nunique(),
                                   total=best.amount.sum(), window_days=span)))
            break

    # funnel / layering
    for acc, g in out.groupby("account_no"):
        big = g[(~g.counterparty_type.isin(["POI", "Internal"])) & (g.amount >= 10_000)]
        if big.empty or big.amount.sum() < 80_000:
            continue
        top3 = big.groupby("counterparty").amount.sum().sort_values(ascending=False).head(3)
        conc = top3.sum() / big.amount.sum()
        if big.counterparty.nunique() <= 4 or conc >= 0.6:
            gi = inc[inc.account_no == acc].amount.sum()
            hit_acc(acc, WEIGHTS["funnel"])
            for b in top3.index:
                hit_ent(b, 8, "Beneficiary")
            F.append(_f("funnel", "Funnel / layering behaviour", "🔀", "High", "Medium",
                        WEIGHTS["funnel"],
                        f"Account {acc} aggregated {money(gi)} of inflows and then routed "
                        f"{money(big.amount.sum())} out in {len(big)} large lump sums, "
                        f"{int(conc*100)}% concentrated to {len(top3)} beneficiary(ies) "
                        f"(notably {top3.index[0]}) — a layering signature.",
                        f"Rule: large outbound (≥ {money(10000)}) summing ≥ {money(80000)}, "
                        f"concentrated (≤4 beneficiaries or ≥60% to top-3).",
                        big, dict(total_out=big.amount.sum(), concentration=round(conc, 2))))
            break

    # pass-through
    pairs = []
    for _, ci in inc[inc.amount >= 5000].sort_values("date").iterrows():
        w = out[(out.account_no == ci.account_no) & (out.date >= ci.date) &
                (out.date <= ci.date + pd.Timedelta(days=T["rapid_days"]))]
        m = w[(w.amount - ci.amount).abs() <= ci.amount * T["rapid_tol"]]
        if not m.empty:
            pairs.append(ci); pairs.append(m.iloc[0])
            hit_acc(ci.account_no, 4)
            hit_ent(m.iloc[0].counterparty, 5, "Beneficiary")
    if pairs:
        ev = pd.DataFrame(pairs)
        F.append(_f("pass_through", "Pass-through / rapid in-out", "⚡", "High", "High",
                    WEIGHTS["pass_through"],
                    f"{len(pairs)//2} case(s) where a credit was followed within "
                    f"{T['rapid_days']} days by a near-identical debit from the same "
                    f"account, leaving little economic footprint — a pass-through hallmark.",
                    f"Rule: inbound ≥ {money(5000)} matched by outbound within "
                    f"{T['rapid_days']} days, amount within ±{int(T['rapid_tol']*100)}%.",
                    ev, dict(cases=len(pairs)//2)))

    # round-dollar
    rnd = df[(df.amount % T["round_mod"] == 0) & (df.amount >= 10_000)]
    if len(rnd) >= 3:
        for _, r in rnd.iterrows():
            hit_ent(r.counterparty, 6, "Counterparty"); hit_acc(r.account_no, 2)
        F.append(_f("round_dollar", "Round-dollar high-value transfers", "💵",
                    "Medium", "Medium", WEIGHTS["round_dollar"],
                    f"{len(rnd)} transfers move exact round amounts ≥ {money(10000)} "
                    f"(e.g. {', '.join(money(a) for a in sorted(rnd.amount.unique())[-3:])}). "
                    f"Round, high-value figures rarely reflect organic commerce and "
                    f"warrant source-of-funds checks.",
                    f"Rule: amount divisible by {money(T['round_mod'])} and ≥ {money(10000)}.",
                    rnd, dict(count=len(rnd))))

    # round-tripping (circular)
    rt = []
    for cp in ext_out.counterparty.unique():
        outs_cp = out[(out.counterparty == cp) & (out.amount >= 5000)]
        ins_cp = inc[inc.counterparty == cp]
        for _, o in outs_cp.iterrows():
            back = ins_cp[(ins_cp.date >= o.date) &
                          (ins_cp.date <= o.date + pd.Timedelta(days=T["roundtrip_days"])) &
                          ((ins_cp.amount - o.amount).abs() <= 0.25 * o.amount)]
            if not back.empty:
                rt.append(o); rt.append(back.iloc[0])
                hit_ent(cp, 7, "Counterparty")
    if rt:
        ev = pd.DataFrame(rt)
        ev = ev[~ev.index.duplicated()]
        F.append(_f("round_trip", "Round-tripping / circular flow", "🔁", "High", "Medium",
                    WEIGHTS["round_trip"],
                    f"Funds sent to a counterparty returned to the subject shortly after "
                    f"({len(rt)//2} loop(s)) — circular movement can be used to disguise "
                    f"the true origin of funds or fabricate turnover.",
                    f"Rule: an outbound payment to entity X followed by an inbound from the "
                    f"same X within {T['roundtrip_days']} days.",
                    ev, dict(loops=len(rt)//2)))

    # own-account churn
    if len(own) >= 5 or (out.amount.sum() and own.amount.sum() >= 0.3 * out.amount.sum()):
        for _, r in own.iterrows():
            hit_acc(r.account_no, 3)
        F.append(_f("own_churn", "Rapid own-account movement", "🔁", "Medium", "Medium",
                    WEIGHTS["own_churn"],
                    f"{len(own)} transfers between the subject's own accounts "
                    f"(total {money(own.amount.sum())}). Frequent self-shuffling can be a "
                    f"layering step that complicates the audit trail.",
                    f"Rule: ≥5 own-account transfers, or own-account volume ≥ 30% of outflow.",
                    own, dict(count=len(own), total=own.amount.sum())))

    # fan-out
    for acc, g in ext_out[ext_out.amount >= 2000].groupby("account_no"):
        for mth, gm in g.groupby(g.date.dt.to_period("M")):
            if gm.counterparty.nunique() >= T["fanout_min"]:
                hit_acc(acc, WEIGHTS["fan_out"])
                F.append(_f("fan_out", "Fan-out to many beneficiaries", "📤", "Medium",
                            "Medium", WEIGHTS["fan_out"],
                            f"In {mth}, account {acc} sent ≥ {money(2000)} to "
                            f"{gm.counterparty.nunique()} different beneficiaries — a "
                            f"one-to-many dispersal pattern worth confirming against a "
                            f"legitimate purpose (e.g. payroll).",
                            f"Rule: ≥ {T['fanout_min']} distinct beneficiaries (≥ {money(2000)} "
                            f"each) from one account in a single month.",
                            gm, dict(beneficiaries=gm.counterparty.nunique())))
                break
        else:
            continue
        break

    # dormant then active
    for acc in set(a for row in df.accounts for a in row):
        g = df[df.accounts.apply(lambda a: acc in a)].sort_values("date")
        if len(g) < 5:
            continue
        gaps = g.date.diff().dt.days.fillna(0)
        if gaps.max() >= T["dormancy_days"]:
            wake = g.loc[gaps.idxmax(), "date"]
            after = g[g.date >= wake].head(6)
            if len(after) >= 4:
                hit_acc(acc, WEIGHTS["dormant_active"])
                F.append(_f("dormant_active", "Dormant account reactivation", "😴",
                            "Medium", "Medium", WEIGHTS["dormant_active"],
                            f"Account {acc} was inactive for ~{int(gaps.max())} days and then "
                            f"produced a burst of {len(after)} transactions from "
                            f"{wake:%d %b %Y} — sudden reactivation is a known red flag.",
                            f"Rule: inactivity gap ≥ {T['dormancy_days']} days followed by "
                            f"≥4 transactions.",
                            after, dict(gap_days=int(gaps.max()))))
                break

    # repeated identical
    key = out[~out.counterparty_type.isin(["POI", "Internal"])].groupby(
        ["counterparty", "amount"]).size()
    rep = key[key >= T["repeat_min"]]
    if not rep.empty:
        (cp, amt) = rep.sort_values(ascending=False).index[0]; n = int(rep.max())
        ev = out[(out.counterparty == cp) & (out.amount == amt)]
        hit_ent(cp, 5, "Beneficiary")
        F.append(_f("repeated_identical", "Repeated identical transfers", "📌",
                    "Medium", "Medium", WEIGHTS["repeated_identical"],
                    f"{n} identical transfers of {money_full(amt)} to “{cp}”. Repeated "
                    f"exact-value payments can indicate structured or obligation-driven "
                    f"flows and merit a documented rationale.",
                    f"Rule: same beneficiary + identical amount ≥ {T['repeat_min']} times.",
                    ev, dict(count=n, amount=amt)))

    # frequent withdrawals
    wd = out[out.transaction_method == "withdrawal"].sort_values("date")
    if not wd.empty:
        wmax, wbest = 0, wd
        for i in range(len(wd)):
            w = wd[(wd.date >= wd.date.iloc[i]) &
                   (wd.date <= wd.date.iloc[i] + pd.Timedelta(days=T["freq_wd_window"]))]
            if len(w) > wmax:
                wmax, wbest = len(w), w
        if wmax >= T["freq_wd_count"]:
            F.append(_f("frequent_withdrawal", "Frequent cash withdrawals", "🏧",
                        "Medium", "High", WEIGHTS["frequent_withdrawal"],
                        f"Up to {wmax} cash withdrawals fall inside a "
                        f"{T['freq_wd_window']}-day window "
                        f"({money(wd.amount.sum())} withdrawn across {len(wd)} events). "
                        f"Elevated cash extraction reduces traceability.",
                        f"Rule: ≥ {T['freq_wd_count']} withdrawals within "
                        f"{T['freq_wd_window']} days.",
                        wbest, dict(peak=wmax, total=wd.amount.sum())))

    # high value
    hv_line = df.amount.quantile(T["high_value_pct"])
    hv = df[df.amount >= max(hv_line, 20_000)]
    if not hv.empty:
        for _, r in hv.iterrows():
            hit_ent(r.counterparty, 4, "Counterparty")
        F.append(_f("high_value", "High-value transactions", "💠", "Medium", "High",
                    WEIGHTS["high_value"],
                    f"{len(hv)} transactions sit in the top value band "
                    f"(≥ {money(max(hv_line,20000))}); the largest is {money(hv.amount.max())}. "
                    f"Enhanced due diligence on source/destination is recommended.",
                    f"Rule: amount ≥ max(P97, {money(20000)}).",
                    hv, dict(count=len(hv), largest=hv.amount.max())))

    # unusual cheque
    chq = inc[inc.transaction_method == "cheque"]
    if len(chq[chq.amount >= 5000]) >= 3:
        F.append(_f("unusual_cheque", "Unusual cheque deposit activity", "🧾", "Low",
                    "Medium", WEIGHTS["unusual_cheque"],
                    f"{len(chq)} inbound cheque deposits (total {money(chq.amount.sum())}), "
                    f"including {len(chq[chq.amount>=5000])} of ≥ {money(5000)}. Cheque "
                    f"clustering can warrant payee verification.",
                    f"Rule: ≥3 inbound cheques of ≥ {money(5000)}.",
                    chq, dict(count=len(chq))))

    # abnormal frequency
    daily = df.groupby(df.date.dt.date).size()
    spike_days = daily[daily >= daily.mean() + 2 * daily.std()]
    if not spike_days.empty:
        ev = df[df.date.dt.date.isin(spike_days.index)]
        F.append(_f("abnormal_frequency", "Abnormal transaction frequency", "📈", "Low",
                    "Medium", WEIGHTS["abnormal_frequency"],
                    f"{len(spike_days)} day(s) carry transaction counts far above the daily "
                    f"average (peak {int(spike_days.max())} vs mean {daily.mean():.1f}). "
                    f"Bursts can indicate coordinated activity.",
                    f"Rule: daily count ≥ mean + 2σ.",
                    ev, dict(spike_days=len(spike_days))))

    # behavioural outlier
    z = (df.amount - df.amount.mean()) / (df.amount.std() or 1)
    outl = df[z > 3]
    if not outl.empty:
        F.append(_f("behavioural_outlier", "Transactions outside normal behaviour", "🔍",
                    "Low", "Medium", WEIGHTS["behavioural_outlier"],
                    f"{len(outl)} transaction(s) exceed 3σ of the subject's own value "
                    f"distribution — statistically atypical versus normal behaviour.",
                    f"Rule: amount z-score > 3 (σ = {money(df.amount.std())}).",
                    outl, dict(count=len(outl))))

    # normalise entity risk 0..100
    ent = {}
    if ent_raw:
        mx = max(ent_raw.values())
        for n, pts in ent_raw.items():
            sc = min(100, int(round(60 * pts / mx + 25)))
            ent[n] = dict(score=sc, band=risk_band(sc), role=ent_role.get(n, "Counterparty"))

    accr = {a: min(100, int(round(s))) for a, s in acc_risk.items()}
    for a in set(x for row in df.accounts for x in row):
        accr.setdefault(a, 8)

    F.sort(key=lambda f: (f["level"] != "High", f["level"] != "Medium", -f["weight"]))
    return F, accr, ent
