"""Streamlit dashboard for the job-search agent.  Run:  streamlit run app.py"""
import importlib

import pandas as pd
import streamlit as st

from src import db, fetchers, resume, scorer, settings
from src import agent

# Re-read .env on every rerun, so new keys work without restarting Streamlit.
importlib.reload(settings); importlib.reload(fetchers); importlib.reload(scorer); importlib.reload(agent)
run = agent.run

st.set_page_config(page_title="AI Job Search Agent", page_icon="🎯", layout="wide")
st.title("🎯 AI Job Search Agent")
st.caption("Finds fresher jobs, scores them against your profile with Gemini, and tracks your applications.")

con = db.connect()

# ---------------- Sidebar: run + filters ----------------
with st.sidebar:
    st.header("🔎 Run a search")
    has_adzuna = bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)
    has_keys = has_adzuna or bool(settings.RAPIDAPI_KEY)
    st.markdown(
        f"{'✅' if has_adzuna else '❌'} Adzuna key  \n"
        f"{'✅' if settings.RAPIDAPI_KEY else '➖'} JSearch key  \n"
        f"{'✅' if settings.GEMINI_API_KEY else '➖'} Gemini key"
    )
    demo = st.toggle("Demo mode (sample data)", value=not has_keys, key=f"demo_{has_keys}",
                     help="Use offline sample jobs. Turn off to search real jobs with your API keys.")
    if demo and has_keys:
        st.warning("Demo mode is ON, so you'll get sample jobs. Turn it off for real jobs.")
    if st.button("Search now", type="primary", use_container_width=True):
        if not demo and not has_keys:
            st.error("Add ADZUNA_* or RAPIDAPI_KEY to your .env file first.")
        else:
            box = st.status("Running agent…", expanded=True)
            log_lines = []

            def progress(msg):
                if not msg.startswith("Scored "):
                    log_lines.append(msg)
                box.write(msg)

            summary = run(demo=demo, notify=not demo, progress=progress)
            st.session_state["last_run"] = {"log": log_lines, "summary": summary}
            failed = summary["errors"] and summary["fetched"] == 0
            box.update(label=("Search failed — see details on the right" if failed
                              else f"Done — {summary['scored']} new jobs scored"),
                       state="error" if failed else "complete", expanded=False)

    st.divider()
    st.header("📄 My resume")
    st.caption("Gemini scores every job against this. Upload your latest resume to update it.")
    up = st.file_uploader("Upload resume (PDF, TXT or MD)", type=["pdf", "txt", "md"])
    if up is not None and st.session_state.get("resume_loaded") != up.name + str(up.size):
        text = resume.extract_text(up.name, up.getvalue())
        if len(text) < 200:
            st.error("Couldn't read much text from that file. If it's a scanned PDF, upload a text-based PDF.")
        else:
            resume.save_profile(text)
            st.session_state["resume_loaded"] = up.name + str(up.size)
            st.success(f"Resume saved ({len(text):,} characters). New searches will use it.")
    with st.expander("View / edit the profile used for scoring"):
        edited = st.text_area("Profile", resume.load_profile(), height=300, label_visibility="collapsed")
        if st.button("Save profile"):
            resume.save_profile(edited)
            st.success("Saved.")

    st.divider()
    st.header("🧰 Filters")
    min_score = st.slider("Minimum match score", 0, 100, 50, 5)
    status_filter = st.multiselect("Status", ["new", "saved", "applied", "skipped"], default=["new", "saved"])
    search = st.text_input("Search title / company / location")
    resume = st.radio("Resume version", ["All", "Data Analyst", "AI/ML"], horizontal=True)

    st.divider()
    st.caption(f"Scoring: {'Gemini' if settings.GEMINI_API_KEY else 'keyword fallback (add GEMINI_API_KEY)'}")
    st.caption(f"Telegram alerts: {'on' if settings.TELEGRAM_BOT_TOKEN else 'off'}")

# ---------------- Last search details (always visible) ----------------
last = st.session_state.get("last_run")
if last:
    sm = last["summary"]
    with st.expander(f"🔎 Last search: {sm['fetched']} postings found, {sm['scored']} new jobs scored",
                     expanded=sm["scored"] == 0):
        for line in last["log"]:
            st.write(line)

filtered = db.filtered_jobs(con)

# ---------------- Data ----------------
jobs = db.all_jobs(con)
if not jobs:
    if filtered:
        st.warning(f"{len(filtered)} jobs were found but all were filtered out as too senior / needing experience. "
                   "See them below, or raise MAX_YEARS_EXPERIENCE in src/settings.py.")
    else:
        st.info("No jobs yet. Click **Search now** in the sidebar (demo mode works without any API keys).")
    if filtered:
        st.dataframe(pd.DataFrame(filtered), hide_index=True, use_container_width=True,
                     column_config={"url": st.column_config.LinkColumn("Link")})
    st.stop()

df = pd.DataFrame(jobs)
if not demo:
    df = df[df["source"] != "demo"]          # never mix sample jobs with real ones
    if df.empty:
        st.info("No real jobs saved yet. Click **Search now** with Demo mode off.")
        st.stop()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Jobs tracked", len(df))
c2.metric("Strong matches (75+)", int((df["score"] >= 75).sum()))
c3.metric("Applied", int((df["status"] == "applied").sum()))
c4.metric("Saved", int((df["status"] == "saved").sum()))

view = df[(df["score"] >= min_score) & (df["status"].isin(status_filter))]
if resume != "All":
    view = view[view["resume_version"] == resume]
if search:
    s = search.lower()
    view = view[view[["title", "company", "location"]].apply(lambda r: s in " ".join(r).lower(), axis=1)]

tab_cards, tab_table, tab_filtered = st.tabs([f"📋 Matches ({len(view)})", "📊 Table",
                                             f"⛔ Filtered out ({len(filtered)})"])

with tab_cards:
    if view.empty:
        st.write("Nothing matches these filters.")
    for _, j in view.iterrows():
        colour = "🟢" if j["score"] >= 75 else "🟡" if j["score"] >= 55 else "🔴"
        with st.container(border=True):
            left, right = st.columns([5, 2])
            with left:
                st.markdown(f"### {colour} {j['title']}")
                st.markdown(f"**{j['company']}** · 📍 {j['location']} · 🕒 {j['posted_at'] or 'date n/a'} · "
                            f"🔗 [{j['source']}]({j['url']})")
                st.write(f"✅ {j['reason']}")
                if j["matching_skills"]:
                    st.markdown("**You have:** " + ", ".join(f"`{s}`" for s in j["matching_skills"]))
                if j["missing_skills"]:
                    st.markdown("**Add to resume / learn:** " + ", ".join(f"`{s}`" for s in j["missing_skills"]))
                with st.expander("Job description"):
                    st.write(j["description"][:3000] or "No description provided.")
            with right:
                st.metric("Match score", f"{j['score']}/100")
                st.caption(f"📄 Send your **{j['resume_version']}** resume · status: **{j['status']}**")
                b1, b2, b3 = st.columns(3)
                if b1.button("✅", key=f"a{j['uid']}", help="Mark applied"):
                    db.set_status(con, j["uid"], "applied"); st.rerun()
                if b2.button("⭐", key=f"s{j['uid']}", help="Save for later"):
                    db.set_status(con, j["uid"], "saved"); st.rerun()
                if b3.button("✖️", key=f"x{j['uid']}", help="Not interested"):
                    db.set_status(con, j["uid"], "skipped"); st.rerun()

with tab_table:
    st.dataframe(
        view[["score", "title", "company", "location", "posted_at", "resume_version", "status", "url"]],
        column_config={"url": st.column_config.LinkColumn("Apply"),
                       "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
        hide_index=True, use_container_width=True,
    )
    st.download_button("Download as CSV", view.drop(columns=["description"]).to_csv(index=False),
                       "job_matches.csv", "text/csv")

with tab_filtered:
    st.caption("Jobs the fresher filter removed (senior titles or more than "
               f"{settings.MAX_YEARS_EXPERIENCE} year of experience asked).")
    if filtered:
        st.dataframe(pd.DataFrame(filtered), hide_index=True, use_container_width=True,
                     column_config={"url": st.column_config.LinkColumn("Link")})
