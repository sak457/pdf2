"""
Built-in analytics assistant.

A rule-based assistant that answers questions about the *loaded data and charts*
— totals, rankings, a specific counterparty, risk, spikes, methods, typologies.
It runs fully offline (no external LLM); answers are computed from the analysis
results, so every number it gives is traceable to the data on screen.
"""

from __future__ import annotations

import re

from .analytics import money, money_full
from . import i18n


def _topn(q, default=3):
    m = re.search(r"\b(\d{1,2})\b", q)
    return int(m.group(1)) if m else default


def answer(question: str, R: dict, df, lang: str = "en") -> str:
    q = (question or "").lower().strip()
    k = R["kpis"]
    ar = lang == "ar"

    def L(en, arabic):
        return arabic if ar else en

    if not q:
        return i18n.T("chat_intro", lang)

    # help / greeting
    if any(w in q for w in ["help", "hi", "hello", "مساعدة", "مرحبا", "اهلا", "أهلا"]):
        return i18n.T("chat_intro", lang)

    # risk
    if any(w in q for w in ["risk", "score", "خطر", "مخاطر", "درجة"]):
        top = ", ".join(f["title"] for f in R["findings"][:3]) or "—"
        return L(f"Overall risk is **{k['risk']}/100 ({R['overall_band']})**, from "
                 f"{k['n_flags']} indicators ({k['n_high']} high, {k['n_med']} medium). "
                 f"Biggest contributors: {top}.",
                 f"المخاطر الإجمالية **{k['risk']}/100 ({R['overall_band']})**، من "
                 f"{k['n_flags']} مؤشرًا ({k['n_high']} مرتفع، {k['n_med']} متوسط). "
                 f"أبرز المساهمين: {top}.")

    # totals
    if ("net" in q or "صافي" in q):
        return L(f"Net cash flow is **{money(k['net'])}** (in {money(k['total_in'])} − "
                 f"out {money(k['total_out'])}).",
                 f"صافي التدفق **{money(k['net'])}** (وارد {money(k['total_in'])} − "
                 f"صادر {money(k['total_out'])}).")
    if any(w in q for w in ["total out", "outgoing", "outflow", "spent", "صادر", "مصروف"]):
        return L(f"Total outgoing is **{money(k['total_out'])}** across "
                 f"{R['flow']['out_count']} debits.",
                 f"إجمالي الصادر **{money(k['total_out'])}** عبر {R['flow']['out_count']} عملية.")
    if any(w in q for w in ["total in", "incoming", "inflow", "received", "وارد", "دخل"]):
        return L(f"Total incoming is **{money(k['total_in'])}** across "
                 f"{R['flow']['in_count']} credits.",
                 f"إجمالي الوارد **{money(k['total_in'])}** عبر {R['flow']['in_count']} عملية.")
    if any(w in q for w in ["own account", "own-account", "internal", "بين الحسابات", "داخلي"]):
        return L(f"Own-account movement totals **{money(k['own_total'])}** over "
                 f"{R['flow']['own_count']} transfers.",
                 f"إجمالي التحويلات بين الحسابات **{money(k['own_total'])}** عبر "
                 f"{R['flow']['own_count']} عملية.")

    # largest
    if any(w in q for w in ["largest", "biggest", "max", "أكبر", "اكبر"]):
        allt = (R["top_out"] + R["top_in"])
        allt.sort(key=lambda x: x["amount"], reverse=True)
        x = allt[0]
        dirn = L("to" if x["direction"] == "out" else "from",
                 "إلى" if x["direction"] == "out" else "من")
        return L(f"Largest transaction: **{money_full(x['amount'])}** {dirn} "
                 f"{x['counterparty']} on {x['date']:%d %b %Y} ({x['method']}).",
                 f"أكبر معاملة: **{money_full(x['amount'])}** {dirn} "
                 f"{x['counterparty']} بتاريخ {x['date']:%Y-%m-%d} ({x['method']}).")

    # accounts / count
    if any(w in q for w in ["how many transaction", "number of transaction", "count", "كم معامل", "عدد المعامل"]):
        return L(f"There are **{k['total_txns']:,}** transactions in the current scope.",
                 f"يوجد **{k['total_txns']:,}** معاملة في النطاق الحالي.")
    if any(w in q for w in ["account", "حساب"]) and any(w in q for w in ["how many", "number", "كم", "عدد"]):
        return L(f"The subject holds **{k['n_accounts']}** account(s).",
                 f"يمتلك الشخص **{k['n_accounts']}** حساب/حسابات.")

    # methods
    if any(w in q for w in ["method", "channel", "transfer", "withdrawal", "cheque", "cash",
                            "طريقة", "طرق", "تحويل", "سحب", "شيك", "نقد"]):
        parts = [f"{m['method']}: {m['count']} ({m['pct']:.0f}%)" for m in R["methods"]]
        return L("Methods — " + " · ".join(parts), "الطرق — " + " · ".join(parts))

    # spikes
    if any(w in q for w in ["spike", "peak", "unusual month", "قفز", "ذروة"]):
        sp = R["spikes"]["inflow"] + R["spikes"]["outflow"]
        if not sp:
            return i18n.T("spike_none", lang)
        return L(f"Spike month(s): {', '.join(sorted(set(sp)))}. Open the Timeline tab "
                 f"and pick one to see who sent/received.",
                 f"أشهر القفزات: {', '.join(sorted(set(sp)))}. افتح تبويب الخط الزمني "
                 f"واختر شهرًا لمعرفة من أرسل/استلم.")

    # top senders / beneficiaries
    if any(w in q for w in ["sender", "paid the subject", "from whom", "مرسل", "مرسلين"]):
        n = _topn(q); rows = R["senders"][:n]
        if not rows:
            return L("No external senders in scope.", "لا يوجد مرسلون خارجيون في النطاق.")
        body = "; ".join(f"{i+1}. {r['name']} — {money(r['amount'])} ({r['count']})"
                         for i, r in enumerate(rows))
        return L(f"Top {n} senders by inflow: {body}.", f"أعلى {n} مرسلين: {body}.")
    if any(w in q for w in ["beneficiar", "recipient", "paid to", "to whom", "مستفيد", "مستلم"]):
        n = _topn(q); rows = R["beneficiaries"][:n]
        if not rows:
            return L("No external beneficiaries in scope.", "لا يوجد مستفيدون خارجيون في النطاق.")
        body = "; ".join(f"{i+1}. {r['name']} — {money(r['amount'])} ({r['count']})"
                         for i, r in enumerate(rows))
        return L(f"Top {n} beneficiaries by outflow: {body}.", f"أعلى {n} مستفيدين: {body}.")

    # counterparty lookup by name (specific entity beats generic keywords)
    names = [c for c in df.counterparty.unique()
             if isinstance(c, str) and c not in ("POI", "Unknown", "Internal transfer")]
    hit = None
    for c in sorted(names, key=len, reverse=True):
        toks = [w for w in re.split(r"[^a-z0-9]+", c.lower()) if len(w) >= 4]
        if toks and any(w in q for w in toks):
            hit = c; break

    # typology explanation — only on distinctive tokens, not generic words
    STOP = {"transactions", "transaction", "activity", "movement", "transfers",
            "transfer", "deposits", "deposit", "account", "cash", "high", "value",
            "rapid", "identical", "frequent", "unusual", "abnormal", "behaviour",
            "normal", "outside", "round", "dollar"}
    if not hit:
        for key, meta in i18n.TYPOLOGY.items():
            title = meta["title"]["en"].lower()
            kws = [key.replace("_", " ")] + [w for w in title.replace("/", " ").split()
                                             if len(w) > 3 and w not in STOP]
            if any(kw in q for kw in kws):
                is_active = any(f["key"] == key for f in R["findings"])
                plain = i18n.typ_plain(key, lang)
                state = L("detected in this data" if is_active else "not detected in this data",
                          "مكتشف في هذه البيانات" if is_active else "غير مكتشف في هذه البيانات")
                return f"**{i18n.typ_title(key, lang)}** — {plain} ({state})."

    if hit:
        sub = df[df.counterparty == hit]
        inflow = sub[sub.direction == "in"].amount.sum()
        outflow = sub[sub.direction == "out"].amount.sum()
        return L(f"With **{hit}**: {len(sub)} transactions — in {money(inflow)}, "
                 f"out {money(outflow)}, net {money(inflow - outflow)}. "
                 f"Use the ‘Focus counterparty’ filter to isolate them.",
                 f"مع **{hit}**: {len(sub)} معاملة — وارد {money(inflow)}، "
                 f"صادر {money(outflow)}، صافٍ {money(inflow - outflow)}. "
                 f"استخدم عامل «التركيز على طرف مقابل» لعزلها.")

    # period
    if any(w in q for w in ["period", "date", "when", "فترة", "تاريخ", "متى"]):
        return L(f"Analysis period: {R['period_str']}.", f"فترة التحليل: {R['period_str']}.")

    return L("I can answer about totals, top senders/beneficiaries, a specific "
             "counterparty, risk, spikes, methods, or a typology. Try “top 5 "
             "beneficiaries” or “transactions with Sterling Consulting”.",
             "يمكنني الإجابة عن الإجماليات، أبرز المرسلين/المستفيدين، طرف مقابل معيّن، "
             "المخاطر، القفزات، الطرق، أو نمط معيّن. جرّب «أكبر 5 مستفيدين» أو "
             "«معاملات مع Sterling Consulting».")
