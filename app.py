import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import llm

DISCLAIMER = "Educational hackathon project. Not financial advice."
USE_FAKE = os.getenv("USE_FAKE_FACTS") == "1"  # set to 1 to fall back to fake_facts.py

st.set_page_config(page_title="Pension AI Analyst", page_icon="📊", layout="wide")


def footer():
    st.divider()
    st.caption(DISCLAIMER)


@st.cache_data(show_spinner=False)
def get_facts(assets: int, annual_payment: int, years: int) -> dict:
    if USE_FAKE:
        from fake_facts import FAKE_FACTS
        return FAKE_FACTS
    from engine import build_facts
    return build_facts(assets=assets, annual_payment=annual_payment, years=years)


# ---------- Sidebar ----------
with st.sidebar:
    st.header("Fund inputs")
    assets = st.number_input("Assets ($)", min_value=10_000, max_value=100_000_000,
                             value=100_000, step=10_000)
    annual_payment = st.number_input("Annual payment ($)", min_value=100, max_value=10_000_000,
                                     value=5_000, step=500)
    years = st.number_input("Years", min_value=1, max_value=60, value=20, step=1)
    run = st.button("Run analysis", type="primary", use_container_width=True)

if run:
    try:
        st.session_state["facts"] = get_facts(int(assets), int(annual_payment), int(years))
        st.session_state["chat"] = []
    except Exception as e:
        st.sidebar.error(f"Engine failed: {e}")

st.title("📊 AI Analyst for a Defined Benefit Pension Fund")

facts = st.session_state.get("facts")
tab1, tab2, tab3, tab4 = st.tabs(["Recommendation", "Committee", "Stress test", "Challenge"])

if facts is None:
    for t in (tab1, tab2, tab3, tab4):
        with t:
            st.info("Set the inputs in the sidebar and click **Run analysis**.")
            footer()
    st.stop()

# ---------- Tab 1: Recommendation ----------
with tab1:
    alloc = pd.DataFrame(facts["allocation"])
    show = pd.DataFrame({
        "Pool": alloc["pool"].str.capitalize(),
        "Ticker": alloc["ticker"],
        "Weight (%)": (alloc["weight"] * 100).round(1),
        "Dollars ($)": alloc["dollars"].map("{:,.0f}".format),
    })
    st.subheader("Recommended allocation")
    st.dataframe(show, hide_index=True, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        by_pool = alloc.groupby("pool", as_index=False)["weight"].sum()
        by_pool["pool"] = by_pool["pool"].str.capitalize()
        st.plotly_chart(px.pie(by_pool, names="pool", values="weight", title="By pool", hole=0.4),
                        use_container_width=True)
    with c2:
        st.plotly_chart(px.pie(alloc, names="ticker", values="weight", title="By ticker", hole=0.4),
                        use_container_width=True)

    m, b = facts["metrics"], facts["benchmark"]
    st.subheader("Portfolio vs 60/40 benchmark")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Expected return", f"{m['expected_return']:.1%}",
              f"{(m['expected_return'] - b['expected_return']) * 100:+.1f} pp vs benchmark")
    k2.metric("Volatility", f"{m['volatility']:.1%}",
              f"{(m['volatility'] - b['volatility']) * 100:+.1f} pp vs benchmark", delta_color="inverse")
    k3.metric("Max drawdown", f"{m['max_drawdown']:.1%}",
              f"{(m['max_drawdown'] - b['max_drawdown']) * 100:+.1f} pp vs benchmark")
    k4.metric("Funding ratio", f"{m['funding_ratio']:.2f}",
              f"{m['funding_ratio'] - b['funding_ratio']:+.2f} vs benchmark")

    a = facts.get("assumptions")
    if a:
        st.caption(
            f"Assumptions: discount rate {a['discount_rate']:.1%}, inflation {a['inflation']:.1%}, "
            f"risk-free {a['risk_free']:.1%}, data to {a['data_end_date']}."
        )
    footer()

# ---------- Tab 2: Committee ----------
with tab2:
    st.subheader("Investment committee")
    with st.spinner("Committee is deliberating..."):
        try:
            st.markdown(llm.run_committee(facts))
        except Exception as e:
            st.error(f"Committee call failed: {e}")
    footer()

# ---------- Tab 3: Stress test ----------
with tab3:
    st.subheader("Stress scenarios")
    st_df = pd.DataFrame(facts["stress"])
    table = pd.DataFrame({
        "Scenario": st_df["scenario"],
        "Portfolio value ($)": st_df["portfolio_value"].map("{:,.0f}".format),
        "Funding ratio": st_df["funding_ratio"].round(2),
        "Obligations met": st_df["obligations_met"].map({True: "✅ Yes", False: "❌ No"}),
    })
    st.dataframe(table, hide_index=True, use_container_width=True)

    fig = go.Figure(go.Bar(
        x=st_df["scenario"], y=st_df["funding_ratio"],
        marker_color=["green" if ok else "red" for ok in st_df["obligations_met"]],
        text=st_df["funding_ratio"].round(2), textposition="outside",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="black", annotation_text="Fully funded (1.0)")
    fig.update_layout(yaxis_title="Funding ratio", xaxis_title="", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    footer()

# ---------- Tab 4: Challenge ----------
with tab4:
    st.subheader("Challenge the recommendation")
    chat = st.session_state.setdefault("chat", [])
    for msg in chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask or challenge, e.g. 'Why so little equity?'")
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = llm.challenge(facts, list(chat), question)
                except Exception as e:
                    answer = f"Call failed: {e}"
            st.markdown(answer)
        chat.append({"role": "user", "content": question})
        chat.append({"role": "assistant", "content": answer})
    footer()
