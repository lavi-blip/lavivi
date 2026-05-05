"""Streamlit web interface for the Lavivi RFP intake tool."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="צומחים מחדש — כלי קולות קוראים",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── RTL style ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  body, .stApp { direction: rtl; }
  .stTextInput input, .stTextArea textarea { direction: rtl; text-align: right; }
  .stSelectbox select { direction: rtl; }
  .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ── sidebar — configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🌱 צומחים מחדש")
    st.caption("כלי ניהול קולות קוראים")
    st.divider()

    st.subheader("🤖 ספק AI")
    provider = st.radio(
        "בחר ספק",
        options=["claude", "gemini"],
        format_func=lambda x: "Claude (Anthropic)" if x == "claude" else "Gemini (Google AI Studio)",
        index=0,
        label_visibility="collapsed",
    )

    st.subheader("🔑 מפתחות API")
    if provider == "claude":
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            type="password",
            placeholder="sk-ant-...",
        )
        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        gemini_key = None
    else:
        gemini_key = st.text_input(
            "Gemini API Key",
            value=os.environ.get("GEMINI_API_KEY", ""),
            type="password",
            placeholder="AIza...",
            help="השג מפתח ב-aistudio.google.com/app/apikey",
        )
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
        anthropic_key = None

    monday_key = st.text_input(
        "Monday.com API Key",
        value=os.environ.get("MONDAY_API_KEY", ""),
        type="password",
    )
    if monday_key:
        os.environ["MONDAY_API_KEY"] = monday_key

    st.divider()
    executor = st.text_input("מבצע/ת ברירת מחדל", placeholder="לביא", help="יוקצה לכל הסאב-אייטמס")

    st.divider()
    with st.expander("💡 Google AI Studio"):
        st.markdown("""
עצב פרומפטים ב-[aistudio.google.com](https://aistudio.google.com) ← בחר **Gemini** כספק כאן.

הכלי ישתמש אוטומטית במפתח ה-Gemini שלך.
        """)


def _get_llm():
    from src.llm import LLMClient
    return LLMClient(provider=provider)


def _check_keys() -> bool:
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("הכנס Anthropic API Key בסרגל הצד.")
        return False
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        st.error("הכנס Gemini API Key בסרגל הצד.")
        return False
    return True


# ── tabs ──────────────────────────────────────────────────────────────────────
tab_specific, tab_scan, tab_profile = st.tabs([
    "🎯 קול קורא ספציפי",
    "🔍 סריקה שיגרתית",
    "🏢 פרופיל ארגון",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — specific RFP
# ════════════════════════════════════════════════════════════════════════════
with tab_specific:
    st.header("ניתוח קול קורא ספציפי")

    col1, col2 = st.columns([3, 1])
    with col1:
        url = st.text_input("קישור לקול הקורא", placeholder="https://...")
    with col2:
        deep_mode = st.checkbox("ניתוח עמוק", value=True,
                                help="זוחל דפים נוספים + בודק התאמה מול פרופיל הארגון")

    uploaded = st.file_uploader("או העלה קובץ PDF", type=["pdf", "txt", "html"])
    create_in_monday = st.checkbox("צור ב-Monday לאחר הניתוח", value=True)

    analyze_btn = st.button("🔍 נתח", type="primary", use_container_width=True)

    if analyze_btn:
        if not _check_keys():
            st.stop()
        if not url and not uploaded:
            st.warning("הכנס קישור או העלה קובץ.")
            st.stop()

        with st.spinner("מוריד ומנתח..."):
            try:
                if uploaded:
                    import tempfile, os as _os
                    suffix = Path(uploaded.name).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                        f.write(uploaded.read())
                        tmp_path = f.name
                    from src.fetcher import read_file
                    content = read_file(tmp_path)
                    _os.unlink(tmp_path)
                elif deep_mode:
                    from src.crawler import crawl
                    content = crawl(url)
                else:
                    from src.fetcher import fetch_url
                    content = fetch_url(url)

                llm = _get_llm()

                if deep_mode:
                    from src import profile as org_profile_mod
                    from src.fit_checker import check_fit
                    org_profile = org_profile_mod.load()
                    report = check_fit(content, org_profile, llm=llm)
                    st.session_state["last_report"] = report
                    st.session_state["last_mode"] = "deep"
                else:
                    from src.analyzer import analyze_rfp
                    analysis = analyze_rfp(content, llm=llm)
                    st.session_state["last_analysis"] = analysis
                    st.session_state["last_mode"] = "simple"
            except Exception as e:
                st.error(f"שגיאה: {e}")
                st.stop()

    # ── display results ───────────────────────────────────────────────────
    if st.session_state.get("last_mode") == "deep" and "last_report" in st.session_state:
        _show_fit_report(st.session_state["last_report"], create_in_monday, executor)
    elif st.session_state.get("last_mode") == "simple" and "last_analysis" in st.session_state:
        _show_simple_analysis(st.session_state["last_analysis"], create_in_monday, executor)


def _show_fit_report(report, create_in_monday: bool, executor: str) -> None:
    score_emoji = {"גבוה": "🟢", "בינוני": "🟡", "נמוך": "🔴", "לא מתאים": "⛔"}
    score_color = {"גבוה": "green", "בינוני": "orange", "נמוך": "red", "לא מתאים": "red"}
    emoji = score_emoji.get(report.fit_score, "⚪")
    color = score_color.get(report.fit_score, "gray")

    st.subheader(report.title_he)
    cols = st.columns(4)
    cols[0].metric("גוף מפרסם", report.funder or "—")
    cols[1].metric("מועד הגשה", report.deadline.isoformat())
    cols[2].metric("התאמה", f"{emoji} {report.fit_score}")
    cols[3].metric("סכום", f"${report.requested_amount_usd:,.0f}" if report.requested_amount_usd else "—")

    st.markdown(f"**המלצה:** {report.recommendation_he}")

    if report.disqualifiers:
        st.error("⚠️ פסילות: " + " | ".join(report.disqualifiers))
    if report.fit_reasons:
        st.success("✅ " + " | ".join(report.fit_reasons))

    auto = [r for r in report.requirements if r.is_autonomous]
    human = [r for r in report.requirements if not r.is_autonomous]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**🤖 משימות אוטומטיות ({len(auto)})**")
        for r in auto:
            with st.expander(f"{r.name_he} — {r.estimated_hours:g}ש׳"):
                st.caption(f"סוג: {r.action_type} | {r.days_before_deadline} ימים לפני")
                if r.prepared_content:
                    st.text_area("תוכן מוכן", r.prepared_content, height=150, key=f"auto_{r.name_he}")
    with col2:
        st.markdown(f"**👤 נדרשת פעולה ידנית ({len(human)})**")
        for r in human:
            with st.expander(f"{r.name_he} — {r.estimated_hours:g}ש׳"):
                st.caption(f"סוג: {r.action_type} | {r.days_before_deadline} ימים לפני")
                if r.human_instructions:
                    st.info(r.human_instructions)

    if report.questions:
        st.markdown(f"**📝 שאלות הבקשה ({len(report.questions)})**")
        for q in report.questions:
            with st.expander(q.question_he[:80]):
                st.text_area("טיוטת תשובה", q.draft_answer_he, height=120, key=f"q_{q.question_he[:30]}")

    if create_in_monday and os.environ.get("MONDAY_API_KEY"):
        if st.button("✅ צור ב-Monday", type="primary"):
            _create_deep_in_monday(report, executor)


def _show_simple_analysis(analysis, create_in_monday: bool, executor: str) -> None:
    from src.preview import render_preview
    st.subheader(analysis.title_he)
    cols = st.columns(4)
    cols[0].metric("גוף מפרסם", analysis.funder or "—")
    cols[1].metric("מועד הגשה", analysis.deadline.isoformat())
    cols[2].metric("קבוצה", "ישראל" if analysis.origin == "israel" else "חו\"ל")
    cols[3].metric("סכום", f"${analysis.requested_amount_usd:,.0f}" if analysis.requested_amount_usd else "—")

    st.markdown(f"**ניתוח:** {analysis.submission_analysis_he}")

    st.markdown(f"**משימות ({len(analysis.tasks)})**")
    for t in analysis.tasks:
        st.markdown(f"- {t.name_he} — {t.estimated_hours:g}ש׳ | {t.days_before_deadline} ימים לפני")

    if create_in_monday and os.environ.get("MONDAY_API_KEY"):
        if st.button("✅ צור ב-Monday", type="primary"):
            _create_simple_in_monday(analysis, executor)


def _create_deep_in_monday(report, executor: str) -> None:
    from src import config
    from src.monday import MondayClient, build_fit_report_column_values, build_requirement_column_values
    with st.spinner("יוצר ב-Monday..."):
        try:
            client = MondayClient()
            group_title = config.GROUP_TITLE_ISRAEL if report.origin == "israel" else config.GROUP_TITLE_ABROAD
            group_id = client.resolve_group_id(group_title)
            item_id = client.create_item(
                group_id=group_id,
                item_name=report.title_he,
                column_values=build_fit_report_column_values(report),
            )
            for req in report.requirements:
                sub_id = client.create_subitem(
                    parent_item_id=item_id,
                    item_name=req.name_he,
                    column_values=build_requirement_column_values(req, report.deadline, executor=executor or None),
                )
                body = (
                    f"## {req.name_he}\n\n{req.prepared_content}" if req.is_autonomous and req.prepared_content
                    else f"## {req.name_he} — ידני\n\n{req.human_instructions}" if req.human_instructions
                    else ""
                )
                if body:
                    client.create_update(item_id=sub_id, body=body)
            if report.questions:
                qa = "## שאלות הבקשה\n\n" + "\n\n".join(
                    f"**{q.question_he}**\n{q.draft_answer_he}" for q in report.questions
                )
                client.create_update(item_id=item_id, body=qa)
            st.success(f"✅ נוצר! [פתח ב-Monday](https://monday.com/boards/{config.BOARD_ID}/pulses/{item_id})")
        except Exception as e:
            st.error(f"שגיאה ביצירה ב-Monday: {e}")


def _create_simple_in_monday(analysis, executor: str) -> None:
    from src import config
    from src.monday import MondayClient, build_main_column_values, build_subitem_column_values
    with st.spinner("יוצר ב-Monday..."):
        try:
            client = MondayClient()
            group_title = config.GROUP_TITLE_ISRAEL if analysis.origin == "israel" else config.GROUP_TITLE_ABROAD
            group_id = client.resolve_group_id(group_title)
            item_id = client.create_item(
                group_id=group_id,
                item_name=analysis.title_he,
                column_values=build_main_column_values(analysis),
            )
            for task in analysis.tasks:
                client.create_subitem(
                    parent_item_id=item_id,
                    item_name=task.name_he,
                    column_values=build_subitem_column_values(task, analysis.deadline, executor=executor or None),
                )
            st.success(f"✅ נוצר! [פתח ב-Monday](https://monday.com/boards/{config.BOARD_ID}/pulses/{item_id})")
        except Exception as e:
            st.error(f"שגיאה ביצירה ב-Monday: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — routine scan
# ════════════════════════════════════════════════════════════════════════════
with tab_scan:
    st.header("סריקה שיגרתית — פלטפורמות")
    st.caption("הכלי סורק את כל הפלטפורמות ב-sources.yaml ומציג קולות קוראים חדשים.")

    if st.button("🔍 סרוק עכשיו", type="primary", use_container_width=True):
        with st.spinner("סורק פלטפורמות..."):
            from src.scanner import scan_all
            found = scan_all()
            st.session_state["scan_results"] = found

    if "scan_results" in st.session_state:
        found = st.session_state["scan_results"]
        if not found:
            st.success("אין קולות קוראים חדשים.")
        else:
            st.info(f"נמצאו **{len(found)}** קולות קוראים חדשים.")
            selected = {}
            for i, rfp in enumerate(found):
                col1, col2, col3 = st.columns([0.5, 5, 2])
                selected[i] = col1.checkbox("", value=True, key=f"sel_{i}")
                col2.markdown(f"**{rfp.title[:70]}**")
                col3.caption(rfp.platform)

            if st.button("✅ צור ב-Monday את הסומנים", type="primary"):
                if not os.environ.get("MONDAY_API_KEY"):
                    st.error("חסר Monday API Key בסרגל הצד.")
                else:
                    chosen = [found[i] for i, v in selected.items() if v]
                    _create_scan_items(chosen)


def _create_scan_items(items) -> None:
    from src import config
    from src.monday import MondayClient
    from src.scanner import mark_seen
    with st.spinner(f"יוצר {len(items)} פריטים..."):
        try:
            client = MondayClient()
            group_id_cache = {}
            created = 0
            for rfp in items:
                group_title = (
                    config.GROUP_TITLE_ISRAEL
                    if rfp.category in {"ממשל / רשויות", "קרנות פילנתרופיות", "מגזר שלישי"}
                    else config.GROUP_TITLE_ABROAD
                )
                if group_title not in group_id_cache:
                    group_id_cache[group_title] = client.resolve_group_id(group_title)
                client.create_item(
                    group_id=group_id_cache[group_title],
                    item_name=rfp.title[:255],
                    column_values={
                        config.COL_REQUEST_TYPE: {"label": config.REQUEST_TYPE_VALUE},
                        config.COL_OUR_STAGE: {"label": config.INITIAL_OUR_STAGE},
                        config.COL_SOURCE: {"label": rfp.category},
                        config.COL_SUBMISSION_ANALYSIS: {"text": f"מקור: {rfp.platform}\nקישור: {rfp.url}"},
                    },
                )
                created += 1
            mark_seen(items)
            st.success(f"✅ נוצרו {created} פריטים ב-Monday.")
        except Exception as e:
            st.error(f"שגיאה: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — org profile
# ════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.header("פרופיל ארגון")
    st.caption("הכלי קורא את הפרופיל הזה לפני כל ניתוח התאמה. עדכן לפי הצורך.")

    profile_path = Path("org_profile.md")
    current = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""

    edited = st.text_area("תוכן הפרופיל (Markdown)", value=current, height=500)

    col1, col2 = st.columns(2)
    if col1.button("💾 שמור"):
        profile_path.write_text(edited, encoding="utf-8")
        st.success("נשמר ✓")

    if col2.button("🔄 עדכן מ-Monday (הגשות קודמות)"):
        if not os.environ.get("MONDAY_API_KEY"):
            st.error("חסר Monday API Key.")
        else:
            with st.spinner("שולף נתונים מ-Monday..."):
                from src.monday import MondayClient
                from src import profile as org_profile_mod
                history = org_profile_mod.build_and_save(MondayClient())
                st.success("הפרופיל עודכן מהגשות קודמות ✓")
                st.rerun()
