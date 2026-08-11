"""
Bilingual (English / Arabic) UI strings + RTL helpers.

T(key, lang) returns the localized string. Dynamic analytic narrative (numbers)
stays language-neutral; everything the user reads as chrome — labels, tabs,
buttons, tooltips, typology titles and plain-language explanations — is here.
"""

from __future__ import annotations

LANGS = {"en": "English", "ar": "العربية"}

STR = {
    # brand / header
    "brand": {"en": "AML INTELLIGENCE TERMINAL", "ar": "منصّة استخبارات مكافحة غسل الأموال"},
    "brand_sub": {"en": "Transaction Monitoring · Financial-Crime Analytics",
                  "ar": "مراقبة المعاملات · تحليلات الجرائم المالية"},
    "classification": {"en": "CONFIDENTIAL · FIU / AML", "ar": "سرّي · وحدة التحرّيات المالية"},
    "subject": {"en": "SUBJECT", "ar": "الشخص محل الاهتمام"},
    "scope": {"en": "SCOPE", "ar": "النطاق"},
    "records": {"en": "RECORDS", "ar": "السجلات"},
    "language": {"en": "Language", "ar": "اللغة"},
    "appearance": {"en": "Appearance", "ar": "المظهر"},
    "night": {"en": "Night", "ar": "ليلي"},
    "day": {"en": "Day", "ar": "نهاري"},
    # data
    "data_source": {"en": "Data source", "ar": "مصدر البيانات"},
    "upload_csv": {"en": "Upload POI transactions CSV", "ar": "ارفع ملف معاملات CSV"},
    "load_sample": {"en": "Load sample", "ar": "تحميل عيّنة"},
    "sample_csv": {"en": "Sample CSV", "ar": "عيّنة CSV"},
    "get_started": {"en": "GET STARTED", "ar": "ابدأ"},
    "welcome": {"en": "AML / Financial-Intelligence Dashboard",
                "ar": "لوحة استخبارات مكافحة غسل الأموال"},
    "welcome_body": {
        "en": "Upload a POI transaction CSV in the sidebar, or click Load sample to explore. "
              "Columns: date, direction (in/out/own_account), account_no, sender, beneficiary, "
              "amount, transaction_method.",
        "ar": "ارفع ملف معاملات بصيغة CSV من الشريط الجانبي، أو اضغط تحميل عيّنة للاستكشاف. "
              "الأعمدة: date, direction, account_no, sender, beneficiary, amount, transaction_method."},
    # filters
    "filters": {"en": "Filters", "ar": "عوامل التصفية"},
    "date_range": {"en": "Date range", "ar": "النطاق الزمني"},
    "quarter": {"en": "Quarter", "ar": "الربع"},
    "direction": {"en": "Direction", "ar": "الاتجاه"},
    "method": {"en": "Method", "ar": "الطريقة"},
    "account": {"en": "Account", "ar": "الحساب"},
    "cp_type": {"en": "Counterparty type", "ar": "نوع الطرف المقابل"},
    "amount_range": {"en": "Amount range", "ar": "نطاق المبلغ"},
    "f_sender_type": {"en": "Sender type", "ar": "نوع المرسل"},
    "f_beneficiary_type": {"en": "Beneficiary type", "ar": "نوع المستفيد"},
    "focus_cp": {"en": "Focus counterparty (money in/out with POI)",
                 "ar": "التركيز على طرف مقابل (الوارد/الصادر مع الشخص)"},
    "focus_all": {"en": "— All counterparties —", "ar": "— كل الأطراف —"},
    "focus_active": {"en": "Focused on", "ar": "التركيز على"},
    "dir_in": {"en": "⬇ Incoming", "ar": "⬇ وارد"},
    "dir_out": {"en": "⬆ Outgoing", "ar": "⬆ صادر"},
    "dir_own": {"en": "🔁 Own-account", "ar": "🔁 بين حسابات الشخص"},
    # POI card
    "poi_profile": {"en": "Subject Profile", "ar": "ملف الشخص"},
    "edit": {"en": "Edit", "ar": "تعديل"},
    "save": {"en": "Save", "ar": "حفظ"},
    "cancel": {"en": "Cancel", "ar": "إلغاء"},
    "full_name": {"en": "Full name", "ar": "الاسم الكامل"},
    "nationality": {"en": "Nationality", "ar": "الجنسية"},
    "doc_id": {"en": "Doc / Customer ID", "ar": "رقم الهوية / العميل"},
    "primary_account": {"en": "Primary account", "ar": "الحساب الرئيسي"},
    "other_info": {"en": "Other info / notes", "ar": "معلومات أخرى / ملاحظات"},
    "photo": {"en": "Photo", "ar": "الصورة"},
    "analysis_period": {"en": "Analysis period", "ar": "فترة التحليل"},
    "risk_rating": {"en": "Risk rating", "ar": "تقييم المخاطر"},
    # KPIs
    "kpi_txns": {"en": "Transactions", "ar": "المعاملات"},
    "kpi_in": {"en": "Total Incoming", "ar": "إجمالي الوارد"},
    "kpi_out": {"en": "Total Outgoing", "ar": "إجمالي الصادر"},
    "kpi_net": {"en": "Net Cash Flow", "ar": "صافي التدفق"},
    "kpi_own": {"en": "Own-Account", "ar": "بين الحسابات"},
    "kpi_accounts": {"en": "Accounts", "ar": "الحسابات"},
    "kpi_senders": {"en": "Unique Senders", "ar": "مرسلون فريدون"},
    "kpi_bens": {"en": "Unique Beneficiaries", "ar": "مستفيدون فريدون"},
    "kpi_largest": {"en": "Largest Txn", "ar": "أكبر معاملة"},
    "kpi_flags": {"en": "Risk Flags", "ar": "مؤشرات الخطر"},
    "credits": {"en": "credits", "ar": "دائن"},
    "debits": {"en": "debits", "ar": "مدين"},
    "internal": {"en": "internal", "ar": "داخلي"},
    "monitored": {"en": "monitored", "ar": "مُراقب"},
    "surplus": {"en": "surplus", "ar": "فائض"},
    "deficit": {"en": "deficit", "ar": "عجز"},
    "high_med": {"en": "{h} high · {m} medium", "ar": "{h} مرتفع · {m} متوسط"},
    # sections / nav
    "sec_flow": {"en": "Money Flow", "ar": "تدفق الأموال"},
    "sec_timeline": {"en": "Timeline", "ar": "الخط الزمني"},
    "sec_cp": {"en": "Counterparties", "ar": "الأطراف المقابلة"},
    "sec_network": {"en": "Link Analysis", "ar": "تحليل الروابط"},
    "sec_crime": {"en": "Financial Crime", "ar": "الجرائم المالية"},
    "sec_risk": {"en": "Risk", "ar": "المخاطر"},
    "sec_txns": {"en": "Transactions", "ar": "المعاملات"},
    "sec_chat": {"en": "Assistant", "ar": "المساعد"},
    "sec_export": {"en": "Export", "ar": "التصدير"},
    "bluf": {"en": "BLUF — BOTTOM LINE UP FRONT", "ar": "الخلاصة أولاً"},
    "risk_word": {"en": "RISK", "ar": "المخاطر"},
    # money flow
    "sankey_title": {"en": "Money-flow Sankey — sources → accounts → destinations",
                     "ar": "مخطط تدفق الأموال — المصادر ← الحسابات ← الوجهات"},
    "acct_throughput": {"en": "Account throughput", "ar": "حركة الحسابات"},
    "inflow_by_type": {"en": "Inflow by source type", "ar": "الوارد حسب نوع المصدر"},
    "account_analysis": {"en": "Account analysis", "ar": "تحليل الحسابات"},
    # timeline
    "tl_title": {"en": "Monthly inflow vs outflow", "ar": "الوارد مقابل الصادر شهريًا"},
    "spike_inspect": {"en": "Inspect a spike — who sent / received", "ar": "افحص القفزة — من أرسل / استلم"},
    "spike_pick": {"en": "Spike month", "ar": "شهر القفزة"},
    "spike_none": {"en": "No statistical spikes in the current scope.", "ar": "لا توجد قفزات إحصائية في النطاق الحالي."},
    "spike_senders": {"en": "Top senders that month", "ar": "أبرز المرسلين في ذلك الشهر"},
    "spike_bens": {"en": "Top beneficiaries that month", "ar": "أبرز المستفيدين في ذلك الشهر"},
    # counterparties
    "top_senders": {"en": "Top senders (by inflow)", "ar": "أبرز المرسلين (حسب الوارد)"},
    "top_bens": {"en": "Top beneficiaries (by outflow)", "ar": "أبرز المستفيدين (حسب الصادر)"},
    "methods_title": {"en": "Transaction methods", "ar": "طرق المعاملات"},
    "top_persons": {"en": "Top Persons", "ar": "أبرز الأفراد"},
    "top_companies": {"en": "Top Companies", "ar": "أبرز الشركات"},
    # counterparty cards
    "cp_cards_title": {"en": "Counterparty cards (editable)", "ar": "بطاقات الأطراف (قابلة للتعديل)"},
    "cp_flow": {"en": "Flow", "ar": "التدفق"},
    "cp_flow_all": {"en": "All", "ar": "الكل"},
    "cp_flow_in": {"en": "Inbound", "ar": "وارد"},
    "cp_flow_out": {"en": "Outbound", "ar": "صادر"},
    "cp_flow_both": {"en": "Both", "ar": "كلاهما"},
    "cp_sort": {"en": "Sort by", "ar": "ترتيب حسب"},
    "cp_sort_in": {"en": "Total inbound", "ar": "إجمالي الوارد"},
    "cp_sort_out": {"en": "Total outbound", "ar": "إجمالي الصادر"},
    "cp_sort_name": {"en": "Name", "ar": "الاسم"},
    "cp_desc": {"en": "Descending", "ar": "تنازلي"},
    "cp_merge_label": {"en": "Select cards to merge (same entity)", "ar": "اختر بطاقات للدمج (نفس الجهة)"},
    "cp_merge_btn": {"en": "Merge selected", "ar": "دمج المحدد"},
    "cp_split": {"en": "Split", "ar": "فصل"},
    "cp_merged_of": {"en": "merged", "ar": "مدمجة"},
    "cp_account": {"en": "Account #", "ar": "رقم الحساب"},
    "cp_type_field": {"en": "Type", "ar": "النوع"},
    "cp_functions": {"en": "Key known functions", "ar": "أهم الوظائف المعروفة"},
    "cp_fill": {"en": "keep empty — I will fill it", "ar": "اتركه فارغًا — سأملؤه"},
    "cp_in": {"en": "Total inbound", "ar": "إجمالي الوارد"},
    "cp_out": {"en": "Total outbound", "ar": "إجمالي الصادر"},
    "cp_count": {"en": "counterparties", "ar": "طرفًا"},
    # export counterparties
    "cp_export_inc": {"en": "Include counterparty cards", "ar": "تضمين بطاقات الأطراف"},
    "cp_export_mode": {"en": "Which counterparties", "ar": "أي الأطراف"},
    "cp_top5": {"en": "Top 5 (by total)", "ar": "أعلى 5 (بالإجمالي)"},
    "cp_top10": {"en": "Top 10 (by total)", "ar": "أعلى 10 (بالإجمالي)"},
    "cp_custom": {"en": "Custom selection", "ar": "اختيار مخصص"},
    "cp_pick": {"en": "Pick counterparties", "ar": "اختر الأطراف"},
    "cp_export_title": {"en": "Counterparties", "ar": "الأطراف المقابلة"},
    # network
    "net_title": {"en": "Link analysis — node size = volume · edge colour = direction",
                  "ar": "تحليل الروابط — حجم العقدة = الحجم · لون الخط = الاتجاه"},
    "annotate_node": {"en": "Annotate a node (name, doc id, photo, notes)",
                      "ar": "توثيق عقدة (اسم، رقم هوية، صورة، ملاحظات)"},
    "node": {"en": "Node", "ar": "العقدة"},
    "display_name": {"en": "Display name", "ar": "الاسم المعروض"},
    "notes": {"en": "Notes", "ar": "ملاحظات"},
    "save_node": {"en": "Save node info", "ar": "حفظ بيانات العقدة"},
    "focus_node": {"en": "Focus a node (highlight its links)", "ar": "تركيز على عقدة (إبراز روابطها)"},
    "txn_between": {"en": "Transactions between two nodes", "ar": "المعاملات بين عقدتين"},
    "node_a": {"en": "Node A", "ar": "العقدة أ"},
    "node_b": {"en": "Node B", "ar": "العقدة ب"},
    "no_direct": {"en": "No direct transactions between these two nodes.", "ar": "لا توجد معاملات مباشرة بين العقدتين."},
    "total": {"en": "total", "ar": "الإجمالي"},
    "net_help": {"en": "Drag nodes to rearrange · scroll to zoom · click a node to focus its "
                       "links · click empty space to reset · hover for details.",
                 "ar": "اسحب العقد لإعادة الترتيب · مرّر للتكبير · اضغط عقدة لإبراز روابطها · "
                       "اضغط على فراغ لإعادة الضبط · مرّر المؤشر لعرض التفاصيل."},
    "lg_poi": {"en": "Subject", "ar": "الشخص"},
    "lg_account": {"en": "Account", "ar": "حساب"},
    "lg_company": {"en": "Company", "ar": "شركة"},
    "lg_unknown": {"en": "Unknown", "ar": "غير معروف"},
    "lg_person": {"en": "Person", "ar": "فرد"},
    "lg_in": {"en": "Incoming", "ar": "وارد"},
    "lg_out": {"en": "Outgoing", "ar": "صادر"},
    "lg_own": {"en": "Own-account", "ar": "بين الحسابات"},
    # balance evidence
    "balance_help": {"en": "How is the current balance calculated?",
                     "ar": "كيف يُحتسب الرصيد الحالي؟"},
    "balance_formula": {"en": "Current balance = external incoming + own-account received "
                              "− external outgoing − own-account sent. Own-account transfers "
                              "move money between the subject's accounts, so they are added to "
                              "the receiving account and subtracted from the sending one. "
                              "(Reflects the transactions currently in view, not a bank opening balance.)",
                        "ar": "الرصيد الحالي = الوارد الخارجي + المستلَم بين الحسابات − الصادر "
                              "الخارجي − المُرسَل بين الحسابات. التحويلات بين حسابات الشخص تُضاف "
                              "للحساب المستلِم وتُخصم من الحساب المُرسِل. (يعكس المعاملات المعروضة "
                              "حاليًا وليس رصيدًا افتتاحيًا من البنك.)"},
    "col_in_ext": {"en": "+ Incoming (external)", "ar": "+ وارد خارجي"},
    "col_in_own": {"en": "+ Own-in", "ar": "+ وارد داخلي"},
    "col_out_ext": {"en": "− Outgoing (external)", "ar": "− صادر خارجي"},
    "col_out_own": {"en": "− Own-out", "ar": "− صادر داخلي"},
    "col_balance_eq": {"en": "= Balance", "ar": "= الرصيد"},
    # crime
    "crime_title": {"en": "Financial-crime typology detection", "ar": "كشف أنماط الجرائم المالية"},
    "crime_note": {"en": "decision-support only, not an allegation", "ar": "لدعم القرار فقط، وليست اتهامًا"},
    "remove": {"en": "Remove", "ar": "إزالة"},
    "removed_title": {"en": "Removed indicators (click to restore)", "ar": "المؤشرات المُزالة (اضغط للاستعادة)"},
    "restore": {"en": "Restore", "ar": "استعادة"},
    "conf": {"en": "Conf", "ar": "الثقة"},
    # risk
    "risk_overall": {"en": "Overall risk", "ar": "المخاطر الإجمالية"},
    "risk_contrib": {"en": "Risk contribution by indicator", "ar": "مساهمة كل مؤشر في المخاطر"},
    "risk_meaning": {"en": "What each indicator means (plain language)", "ar": "معنى كل مؤشر (بلغة بسيطة)"},
    "risk_how": {"en": "How the score is built", "ar": "كيف يُحتسب التقييم"},
    "risk_how_txt": {"en": "The score adds the risk weight of every active typology "
                           "(scaled to 0–100). Removing an indicator recomputes it.",
                     "ar": "يجمع التقييم أوزان كل نمط نشِط (على مقياس 0–100). "
                           "إزالة مؤشر تعيد احتسابه."},
    "acct_cp_risk": {"en": "Account & counterparty risk", "ar": "مخاطر الحسابات والأطراف"},
    # transactions
    "top10_in": {"en": "Top 10 incoming", "ar": "أعلى 10 واردة"},
    "top10_out": {"en": "Top 10 outgoing", "ar": "أعلى 10 صادرة"},
    "all_txns": {"en": "All transactions (filtered)", "ar": "كل المعاملات (بعد التصفية)"},
    "download_csv": {"en": "Download filtered data (CSV)", "ar": "تنزيل البيانات المصفّاة (CSV)"},
    "col_date": {"en": "Date", "ar": "التاريخ"},
    "col_cp": {"en": "Counterparty", "ar": "الطرف المقابل"},
    "col_method": {"en": "Method", "ar": "الطريقة"},
    "col_amount": {"en": "Amount", "ar": "المبلغ"},
    # chat
    "chat_title": {"en": "Ask the data — analytics assistant", "ar": "اسأل البيانات — المساعد التحليلي"},
    "chat_hint": {"en": "Ask about totals, top senders/beneficiaries, a counterparty, "
                        "risk, spikes, methods, or a typology…",
                  "ar": "اسأل عن الإجماليات، أبرز المرسلين/المستفيدين، طرف مقابل، "
                        "المخاطر، القفزات، الطرق، أو نمطًا معينًا…"},
    "chat_placeholder": {"en": "Type your question…", "ar": "اكتب سؤالك…"},
    "chat_intro": {"en": "Hi — I answer from the loaded data. Try: “top 3 beneficiaries”, "
                         "“total outgoing”, “risk score”, “transactions with Blue Harbor Trading”.",
                   "ar": "مرحبًا — أجيب من البيانات المحمّلة. جرّب: «أكبر 3 مستفيدين»، "
                         "«إجمالي الصادر»، «درجة المخاطر»، «معاملات مع Blue Harbor Trading»."},
    # export
    "export_title": {"en": "Build an editable PowerPoint (PPTX)", "ar": "إنشاء عرض PowerPoint قابل للتعديل"},
    "export_note": {"en": "Pick exhibits, add commentary, optionally upload your own .pptx "
                          "template, and export an editable deck.",
                    "ar": "اختر العناصر، أضف تعليقًا، ويمكنك رفع قالب .pptx خاص بك، ثم صدّر عرضًا قابلًا للتعديل."},
    "exhibits": {"en": "Exhibits to include (in order)", "ar": "العناصر المُدرجة (بالترتيب)"},
    "inc_findings": {"en": "Include financial-crime findings slide", "ar": "تضمين شريحة نتائج الجرائم المالية"},
    "report_title": {"en": "Report title", "ar": "عنوان التقرير"},
    "prepared_for": {"en": "Prepared for", "ar": "أُعدّ لـ"},
    "tmpl_upload": {"en": "Upload .pptx template (optional)", "ar": "رفع قالب .pptx (اختياري)"},
    "tmpl_used": {"en": "Using your uploaded template.", "ar": "سيتم استخدام القالب المرفوع."},
    "gen_pptx": {"en": "Generate PPTX", "ar": "إنشاء العرض"},
    "download_pptx": {"en": "Download PowerPoint", "ar": "تنزيل العرض"},
    "commentary": {"en": "Analyst commentary (optional)", "ar": "تعليق المحلل (اختياري)"},
    "rendering": {"en": "Rendering exhibits…", "ar": "جارٍ تجهيز العناصر…"},
    "footer": {"en": "indicators are decision-support only and require analyst review.",
               "ar": "المؤشرات لدعم القرار فقط وتتطلب مراجعة المحلل."},
    "info": {"en": "What is this?", "ar": "ما هذا؟"},
    # login
    "login_secure": {"en": "SECURE ACCESS", "ar": "دخول آمن"},
    "login_prompt": {"en": "Sign in to access the intelligence terminal.",
                     "ar": "سجّل الدخول للوصول إلى المنصّة."},
    "username": {"en": "Username", "ar": "اسم المستخدم"},
    "password": {"en": "Password", "ar": "كلمة المرور"},
    "login_btn": {"en": "Sign in", "ar": "تسجيل الدخول"},
    "login_bad": {"en": "Invalid username or password.", "ar": "اسم المستخدم أو كلمة المرور غير صحيحة."},
    "login_hint": {"en": "Demo: analyst / aml2026 · configure real users via st.secrets "
                         "[auth] or the AML_USERS environment variable.",
                   "ar": "تجريبي: analyst / aml2026 · اضبط المستخدمين عبر st.secrets [auth] "
                         "أو المتغيّر AML_USERS."},
    "logout": {"en": "Sign out", "ar": "تسجيل الخروج"},
    # accounts details
    "sec_accounts": {"en": "Accounts Details", "ar": "تفاصيل الحسابات"},
    "acc_table_title": {"en": "Per-account summary", "ar": "ملخّص كل حساب"},
    "col_incoming": {"en": "Total Incoming", "ar": "إجمالي الوارد"},
    "col_outgoing": {"en": "Total Outgoing", "ar": "إجمالي الصادر"},
    "col_balance": {"en": "Current Balance", "ar": "الرصيد الحالي"},
    "col_spike": {"en": "Spike?", "ar": "قفزة؟"},
    "col_count": {"en": "Txns", "ar": "المعاملات"},
    "yes": {"en": "Yes", "ar": "نعم"}, "no": {"en": "No", "ar": "لا"},
    "spike_txns_title": {"en": "Spike transactions", "ar": "معاملات القفزات"},
    "spike_view": {"en": "⚡ {acc} — spike transactions ({n})", "ar": "⚡ {acc} — معاملات القفزات ({n})"},
    "flow_in": {"en": "IN", "ar": "وارد"}, "flow_out": {"en": "OUT", "ar": "صادر"},
    "col_flow": {"en": "Flow", "ar": "الاتجاه"}, "col_party": {"en": "Party", "ar": "الطرف"},
    "acc_top_title": {"en": "Top 5 senders / receivers per account",
                      "ar": "أعلى 5 مرسلين/مستلمين لكل حساب"},
    "acc_top_senders": {"en": "Top 5 senders", "ar": "أعلى 5 مرسلين"},
    "acc_top_receivers": {"en": "Top 5 receivers", "ar": "أعلى 5 مستلمين"},
    "acc_expander": {"en": "🏦 {acc}", "ar": "🏦 {acc}"},
    "multi_title": {"en": "Counterparties spread across multiple POI accounts",
                    "ar": "أطراف موزّعة عبر عدة حسابات للشخص"},
    "multi_note": {"en": "Same person/company moving money in or out via several of the "
                         "POI's accounts — a spreading pattern worth reviewing.",
                   "ar": "نفس الشخص/الشركة يحرّك أموالًا عبر عدة من حسابات الشخص — نمط توزيع يستحق المراجعة."},
    "min_accounts": {"en": "Minimum # of accounts", "ar": "أدنى عدد للحسابات"},
    "col_naccounts": {"en": "# Accounts", "ar": "عدد الحسابات"},
    "col_accounts": {"en": "POI accounts used", "ar": "حسابات الشخص المستخدمة"},
    "col_direction": {"en": "Direction", "ar": "الاتجاه"},
    "dir_both": {"en": "in & out", "ar": "وارد وصادر"},
    "multi_none": {"en": "No counterparty uses that many accounts.", "ar": "لا يوجد طرف يستخدم هذا العدد من الحسابات."},
    # edit BLUF + stats
    "edit_bluf": {"en": "Edit BLUF", "ar": "تعديل الخلاصة"},
    "reset_auto": {"en": "Reset to auto", "ar": "إعادة للوضع التلقائي"},
    "bluf_saved": {"en": "BLUF updated.", "ar": "تم تحديث الخلاصة."},
    "customize_stats": {"en": "Customize statistics", "ar": "تخصيص الإحصاءات"},
    "stat_show": {"en": "Show which statistics", "ar": "أي إحصاءات تُعرض"},
    "evidence_for": {"en": "Evidence", "ar": "الأدلة"},
    "inc_accounts": {"en": "Include Accounts Details tables", "ar": "تضمين جداول تفاصيل الحسابات"},
}

# chart info tooltips (simple words)
INFO = {
    "sankey": {"en": "Shows where money comes from and where it goes. Left = who paid the "
                     "subject, middle = the subject's accounts, right = who the subject paid. "
                     "Thicker ribbons = more money.",
               "ar": "يوضّح من أين يأتي المال وإلى أين يذهب. اليسار = من دفع للشخص، الوسط = "
                     "حسابات الشخص، اليمين = من دفع له الشخص. الشريط الأعرض = مال أكثر."},
    "accounts": {"en": "For each account, green is money received and red is money paid out.",
                 "ar": "لكل حساب، الأخضر هو المال الوارد والأحمر هو المال الصادر."},
    "type_split": {"en": "Share of incoming money by source: companies, unknown parties, etc.",
                   "ar": "نسبة المال الوارد حسب المصدر: شركات، أطراف غير معروفة، إلخ."},
    "timeline": {"en": "Money in (green) vs out (red) each month. ▲ marks months that are "
                       "unusually high compared with the rest.",
                 "ar": "الوارد (أخضر) مقابل الصادر (أحمر) كل شهر. ▲ يشير إلى الأشهر المرتفعة "
                       "بشكل غير معتاد."},
    "senders": {"en": "The parties that sent the most money to the subject.",
                "ar": "الأطراف التي أرسلت أكبر مبالغ للشخص."},
    "beneficiaries": {"en": "The parties the subject sent the most money to.",
                      "ar": "الأطراف التي أرسل لها الشخص أكبر مبالغ."},
    "methods": {"en": "How transactions were made: transfer, withdrawal, cheque, card…",
                "ar": "كيف تمّت المعاملات: تحويل، سحب، شيك، بطاقة…"},
    "network": {"en": "A map of relationships. The subject and accounts sit in the middle; "
                      "lines connect them to the people/companies they moved money with. "
                      "Bigger dots moved more money.",
                "ar": "خريطة علاقات. الشخص وحساباته في المنتصف؛ الخطوط تربطهم بالأشخاص/الشركات "
                      "الذين جرى تبادل المال معهم. النقاط الأكبر تعني مالًا أكثر."},
    "risk_gauge": {"en": "One number (0–100) summarising overall concern. Higher = more "
                         "review needed. It is the sum of all active indicators.",
                   "ar": "رقم واحد (0–100) يلخّص مستوى القلق. الأعلى = يحتاج مراجعة أكثر. "
                         "وهو مجموع كل المؤشرات النشطة."},
    "risk_contrib": {"en": "How much each red flag adds to the total risk score.",
                     "ar": "كم يضيف كل مؤشر خطر إلى إجمالي درجة المخاطر."},
    # KPI / statistics explanations
    "stat_txns": {"en": "How many transactions are in view after your filters.",
                  "ar": "عدد المعاملات المعروضة بعد التصفية."},
    "stat_in": {"en": "All money received by the subject (credits).",
                "ar": "إجمالي المال الذي استلمه الشخص (دائن)."},
    "stat_out": {"en": "All money the subject paid out (debits).",
                 "ar": "إجمالي المال الذي دفعه الشخص (مدين)."},
    "stat_net": {"en": "Incoming minus outgoing. Positive = more came in than went out.",
                 "ar": "الوارد ناقص الصادر. الموجب يعني أن الوارد أكثر من الصادر."},
    "stat_own": {"en": "Money moved between the subject's own accounts.",
                 "ar": "المال المُحرّك بين حسابات الشخص نفسه."},
    "stat_accounts": {"en": "Number of the subject's accounts seen in the data.",
                      "ar": "عدد حسابات الشخص الظاهرة في البيانات."},
    "stat_senders": {"en": "How many different outside parties sent money to the subject.",
                     "ar": "عدد الأطراف الخارجية المختلفة التي أرسلت مالًا للشخص."},
    "stat_bens": {"en": "How many different outside parties the subject sent money to.",
                  "ar": "عدد الأطراف الخارجية المختلفة التي أرسل لها الشخص مالًا."},
    "stat_largest": {"en": "The single biggest transaction in view.",
                     "ar": "أكبر معاملة منفردة معروضة."},
    "stat_flags": {"en": "How many financial-crime indicators are currently active.",
                   "ar": "عدد مؤشرات الجرائم المالية النشطة حاليًا."},
}

# typology titles + plain-language meaning (bilingual), keyed by finding key
TYPOLOGY = {
    "structuring": {"title": {"en": "Structuring — sub-threshold deposits", "ar": "التجزئة — إيداعات تحت الحد"},
        "plain": {"en": "Breaking a big deposit into several smaller ones kept just under the "
                        "reporting limit, to avoid being reported.",
                  "ar": "تقسيم إيداع كبير إلى مبالغ أصغر تبقى تحت حد الإبلاغ لتفادي الإبلاغ."}},
    "smurfing": {"title": {"en": "Smurfing / fan-in", "ar": "التنميل / التجميع"},
        "plain": {"en": "Many different people each send a small amount into the same account "
                        "in a short time — together forming a large sum.",
                  "ar": "عدة أشخاص يرسل كل منهم مبلغًا صغيرًا إلى الحساب نفسه خلال فترة قصيرة، "
                        "ليشكّلوا معًا مبلغًا كبيرًا."}},
    "funnel": {"title": {"en": "Funnel / layering behaviour", "ar": "التقميع / التمويه الطبقي"},
        "plain": {"en": "Money is gathered in an account then quickly pushed out in a few big "
                        "payments to a small number of parties.",
                  "ar": "يُجمع المال في حساب ثم يُخرج بسرعة في دفعات كبيرة إلى عدد قليل من الأطراف."}},
    "pass_through": {"title": {"en": "Pass-through / rapid in-out", "ar": "المرور السريع"},
        "plain": {"en": "Money arrives and leaves the account within a day or two at almost the "
                        "same amount — the account is just a stop on the way.",
                  "ar": "يصل المال ويغادر خلال يوم أو يومين بنفس المبلغ تقريبًا — الحساب مجرّد محطة عبور."}},
    "round_trip": {"title": {"en": "Round-tripping / circular flow", "ar": "التدوير / التدفق الدائري"},
        "plain": {"en": "Money sent to someone comes back to the subject soon after — going in "
                        "a circle to disguise its origin or fake activity.",
                  "ar": "المال المُرسل يعود للشخص بعد فترة قصيرة — يدور في حلقة لإخفاء مصدره أو لتضخيم النشاط."}},
    "round_dollar": {"title": {"en": "Round-dollar high-value transfers", "ar": "تحويلات كبيرة بأرقام صحيحة"},
        "plain": {"en": "Large payments in exact round numbers (like 50,000), which rarely happen "
                        "in normal business.",
                  "ar": "دفعات كبيرة بأرقام صحيحة تمامًا (مثل 50,000)، وهو أمر نادر في النشاط الطبيعي."}},
    "own_churn": {"title": {"en": "Rapid own-account movement", "ar": "تحريك سريع بين حسابات الشخص"},
        "plain": {"en": "Frequent transfers between the subject's own accounts, which can hide "
                        "the trail of where money really goes.",
                  "ar": "تحويلات متكررة بين حسابات الشخص نفسه، ما قد يُخفي مسار المال الحقيقي."}},
    "fan_out": {"title": {"en": "Fan-out to many beneficiaries", "ar": "التوزيع على مستفيدين كثر"},
        "plain": {"en": "One account pays many different parties in a short period — money is "
                        "dispersed widely.",
                  "ar": "حساب واحد يدفع لعدة أطراف خلال فترة قصيرة — تشتيت واسع للمال."}},
    "dormant_active": {"title": {"en": "Dormant account reactivation", "ar": "إعادة تنشيط حساب خامل"},
        "plain": {"en": "An account that was quiet for a long time suddenly becomes very active.",
                  "ar": "حساب كان خاملًا لفترة طويلة ينشط فجأة بشكل كبير."}},
    "repeated_identical": {"title": {"en": "Repeated identical transfers", "ar": "تحويلات متطابقة متكررة"},
        "plain": {"en": "The same exact amount is sent to the same party many times.",
                  "ar": "نفس المبلغ بالضبط يُرسل إلى نفس الطرف مرات عديدة."}},
    "frequent_withdrawal": {"title": {"en": "Frequent cash withdrawals", "ar": "سحوبات نقدية متكررة"},
        "plain": {"en": "A lot of cash is taken out in a short window — cash is hard to trace.",
                  "ar": "سحب مبالغ نقدية كثيرة خلال فترة قصيرة — والنقد يصعب تتبعه."}},
    "high_value": {"title": {"en": "High-value transactions", "ar": "معاملات مرتفعة القيمة"},
        "plain": {"en": "The largest transactions in the data — worth extra checking of source "
                        "and destination.",
                  "ar": "أكبر المعاملات في البيانات — تستحق تدقيقًا إضافيًا للمصدر والوجهة."}},
    "unusual_cheque": {"title": {"en": "Unusual cheque deposit activity", "ar": "نشاط شيكات غير معتاد"},
        "plain": {"en": "Several sizeable cheque deposits that stand out and may need payee checks.",
                  "ar": "عدة إيداعات شيكات كبيرة لافتة قد تحتاج للتحقق من المستفيد."}},
    "abnormal_frequency": {"title": {"en": "Abnormal transaction frequency", "ar": "تكرار غير طبيعي للمعاملات"},
        "plain": {"en": "Some days have far more transactions than usual — a burst of activity.",
                  "ar": "بعض الأيام بها معاملات أكثر بكثير من المعتاد — دفعة نشاط مفاجئة."}},
    "behavioural_outlier": {"title": {"en": "Transactions outside normal behaviour", "ar": "معاملات خارج السلوك المعتاد"},
        "plain": {"en": "A few transactions are statistically very different from the subject's "
                        "usual pattern.",
                  "ar": "بعض المعاملات تختلف إحصائيًا بشكل كبير عن النمط المعتاد للشخص."}},
}


def T(key: str, lang: str = "en") -> str:
    e = STR.get(key)
    if not e:
        return key
    return e.get(lang, e.get("en", key))


def info_text(key: str, lang: str = "en") -> str:
    e = INFO.get(key, {})
    return e.get(lang, e.get("en", ""))


def typ_title(key: str, lang: str, fallback: str = "") -> str:
    e = TYPOLOGY.get(key, {}).get("title", {})
    return e.get(lang, e.get("en", fallback))


def typ_plain(key: str, lang: str) -> str:
    e = TYPOLOGY.get(key, {}).get("plain", {})
    return e.get(lang, e.get("en", ""))


def is_rtl(lang: str) -> bool:
    return lang == "ar"


def rtl_css(lang: str) -> str:
    if lang != "ar":
        return ""
    return """
    <style>
      .stApp, .block-container { direction: rtl; }
      .stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp p,.stApp label,
      .stApp span,.stApp div { text-align: right; }
      .brand { flex-direction: row-reverse; }
      .brand .spacer { }
      .stMarkdown h5 { padding-left:0; padding-right:14px; }
      .stMarkdown h5::before { left:auto; right:0; }
      .kpi .bar { left:auto; right:0; }
      .bluf { border-left:none; border-right:5px solid var(--amber); }
      section[data-testid="stSidebar"] { direction: rtl; }
      .stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; }
    </style>
    """
