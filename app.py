import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════
st.set_page_config(
    page_title="Public Opinion Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════
# NYT-INSPIRED THEME
# ══════════════════════════════════════════
THEME = {
    "bg": "#FFFFFF",
    "panel": "#F7F7F7",
    "border": "#E2E2E2",
    "text": "#121212",
    "text_muted": "#666666",
    "primary": "#326891",       # NYT blue
    "accent": "#DC0000",        # NYT red (sparingly)
    "positive": "#2E7D32",
    "negative": "#C62828",
    "neutral": "#999999",
    "categorical": [
        "#326891", "#A41E22", "#5D8233", "#A4720D",
        "#7B4A8E", "#8C5A3E", "#386F7F", "#A03956",
        "#5C6970",
    ],
}

# One fixed, high-contrast color per topic — spread across the color wheel
TOPIC_COLORS = {
    "artificial intelligence": "#1565C0",  # blue
    "business":                "#E64A19",  # deep orange
    "climate policy":          "#2E7D32",  # green
    "data privacy":            "#6A1B9A",  # purple
    "tech layoffs":            "#C62828",  # red
    "us politics":             "#00838F",  # teal
    "hollywood":               "#AD1457",  # pink
    "world news":              "#6D4C41",  # brown
    "tech news":               "#F9A825",  # amber
    "other":                   "#9E9E9E",  # grey
}

# Custom Plotly template
custom_template = go.layout.Template()
custom_template.layout = go.Layout(
    paper_bgcolor=THEME["bg"],
    plot_bgcolor=THEME["bg"],
    font=dict(family="Georgia, serif", size=12, color=THEME["text"]),
    title=dict(
        font=dict(family="Georgia, serif", size=20, color=THEME["text"]),
        x=0.02, xanchor="left", y=0.95,
    ),
    xaxis=dict(
        gridcolor=THEME["border"], linecolor=THEME["border"],
        tickfont=dict(color=THEME["text_muted"], family="Inter, sans-serif"),
        zerolinecolor=THEME["border"],
    ),
    yaxis=dict(
        gridcolor=THEME["border"], linecolor=THEME["border"],
        tickfont=dict(color=THEME["text_muted"], family="Inter, sans-serif"),
        zerolinecolor=THEME["border"],
    ),
    legend=dict(bgcolor=THEME["bg"], bordercolor=THEME["border"], borderwidth=0),
    margin=dict(l=60, r=40, t=80, b=60),
    hoverlabel=dict(bgcolor=THEME["panel"], bordercolor=THEME["primary"]),
    colorway=THEME["categorical"],
)
pio.templates["nyt"] = custom_template
pio.templates.default = "nyt"

# ══════════════════════════════════════════
# CUSTOM CSS (NYT typography + layout polish)
# ══════════════════════════════════════════
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,600;0,700;1,400&display=swap');
    
    /* Global */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
        color: #121212;
    }
    
    h1, h2, h3 {
        font-family: 'Lora', Georgia, serif;
        font-weight: 700;
        color: #121212;
        letter-spacing: -0.02em;
    }
    
    h1 { font-size: 2.5rem; line-height: 1.1; margin-bottom: 0.5rem; }
    h2 { font-size: 1.75rem; }
    h3 { font-size: 1.3rem; }
    
    /* Hero KPI styling */
    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: 1px solid #E2E2E2;
        border-radius: 4px;
        padding: 1.5rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Lora', Georgia, serif;
        font-size: 2.5rem;
        font-weight: 700;
        color: #326891;
    }
    [data-testid="metric-container"] [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        font-weight: 600;
        color: #666666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F7F7F7;
        border-right: 1px solid #E2E2E2;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid #E2E2E2;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        color: #666666;
        padding: 0.5rem 1.5rem;
    }
    .stTabs [aria-selected="true"] {
        color: #121212;
        border-bottom: 2px solid #326891;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Header divider */
    .nyt-divider {
        border-top: 2px solid #121212;
        margin: 1rem 0 2rem 0;
    }
    
    /* Article-style intro paragraph */
    .lead {
        font-family: 'Lora', Georgia, serif;
        font-size: 1.1rem;
        line-height: 1.6;
        color: #333333;
        font-style: italic;
        max-width: 800px;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

import re

_SCRAPE_ARTIFACTS = re.compile(
    r"(read\s+full\s+article|read\s+more|comments?|share\s+this|click\s+here|"
    r"subscribe\s+now|sign\s+up|advertisement|sponsored|related\s+articles?|"
    r"continue\s+reading|see\s+more|view\s+full\s+story|follow\s+us)[^\w]*$",
    re.IGNORECASE,
)

def sentiment_label(score: float) -> str:
    if score >= 0.5:   return "Very Positive"
    if score >= 0.2:   return "Positive"
    if score >= 0.05:  return "Slightly Positive"
    if score > -0.05:  return "Neutral"
    if score > -0.2:   return "Slightly Negative"
    if score > -0.5:   return "Negative"
    return "Very Negative"


def clean_content(text: str) -> str:
    text = str(text).strip()
    text = _SCRAPE_ARTIFACTS.sub("", text).strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text

# ══════════════════════════════════════════
# DATA LOADING (cached)
# ══════════════════════════════════════════
@st.cache_resource
def get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@st.cache_data(ttl=300) # Cache for 5 minutes
def load_data():
    supabase = get_supabase()
    posts = []
    offset = 0
    batch_size = 1000
    
    while True:
        response = supabase.table("posts").select("*").eq("is_processed", True).range(offset, offset + batch_size - 1).execute()
        batch = response.data if response.data else []
        if not batch:
            break
        posts.extend(batch)
        offset += batch_size
    
    df = pd.DataFrame(posts)
    df["created_at"] = pd.to_datetime(df["created_at"], format="ISO8601", errors="coerce")
    if df["created_at"].dt.tz is not None:
        df["created_at"] = df["created_at"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["date"] = pd.to_datetime(df["created_at"].dt.date)
    
    df = df[df["date"] >= pd.Timestamp("2026-04-01")]
    df = df.drop_duplicates(subset=["content"], keep="first")

    def _parse_emotions(emo):
        if isinstance(emo, str):
            try:
                return json.loads(emo)
            except Exception:
                return {}
        elif isinstance(emo, dict):
            return emo
        return {}

    if "emotions" in df.columns:
        df["emotions_parsed"] = df["emotions"].apply(_parse_emotions)
    else:
        df["emotions_parsed"] = [{} for _ in range(len(df))]

    return df

# ══════════════════════════════════════════
# HEADER    
# ══════════════════════════════════════════
st.markdown("# Public Opinion Pulse")
st.markdown('<div class="lead">Tracking how public opinion evolves across news outlets, social media, and online forums — in near real-time.</div>', unsafe_allow_html=True)
st.markdown('<div class="nyt-divider"></div>', unsafe_allow_html=True)

# Load data
with st.spinner("Loading data..."):
    df = load_data()

if df.empty:
    st.error("No data available. Please check back later.")
    st.stop()

EMOTION_LABELS = ["anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise"]
EMOTIONS_AVAILABLE = df["emotions_parsed"].apply(lambda x: bool(x)).mean() > 0.5
    
# ══════════════════════════════════════════
# SIDEBAR FILTERS
# ══════════════════════════════════════════
st.sidebar.markdown("## Filters")

# Date range
min_date = df["created_at"].min().date()
max_date = df["created_at"].max().date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Topic filter
topics = sorted(df["topic"].unique())
selected_topics = st.sidebar.multiselect("Topics", topics, default=[])

# Source category filter
source_categories = sorted(df["source_category"].unique())
selected_categories = st.sidebar.multiselect("Source Categories", source_categories, default=[])

# Apply filters
df_filtered = df.copy()
if len(date_range) == 2:
    df_filtered = df_filtered[
        (df_filtered["date"] >= pd.Timestamp(date_range[0])) &
        (df_filtered["date"] <= pd.Timestamp(date_range[1]))
    ]
df_filtered = df_filtered[df_filtered["topic"].isin(selected_topics)]
df_filtered = df_filtered[df_filtered["source_category"].isin(selected_categories)]

if df_filtered.empty:
    st.sidebar.warning("No posts match the current filters.")
else:
    st.sidebar.markdown(f"**{len(df_filtered):,} posts match**")

# ══════════════════════════════════════════
# KPI METRICS
# ══════════════════════════════════════════

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Posts Analyzed", f"{len(df_filtered):,}")

with col2:
    if df_filtered.empty:
        score_color = THEME["text_muted"]
        score_html  = "—"
        label_html  = "—"
        arrow       = ""
    else:
        avg_sent    = df_filtered["sentiment_score"].mean()
        label_html  = sentiment_label(avg_sent)
        score_html  = f"{avg_sent:+.3f}"
        if avg_sent > 0.05:
            score_color, arrow = THEME["positive"], "↑"
        elif avg_sent < -0.05:
            score_color, arrow = THEME["negative"], "↓"
        else:
            score_color, arrow = THEME["neutral"], "→"
    st.markdown(
        f"""<div style="line-height:1.4">
          <p style="font-size:0.875rem;color:{THEME['text_muted']};margin:0 0 4px;font-weight:400">
            Average Sentiment
          </p>
          <p style="font-size:1.75rem;font-weight:700;margin:0;color:{THEME['text']}">
            {label_html}
          </p>
          <p style="font-size:0.85rem;color:{score_color};margin:4px 0 0">
            {arrow} {score_html} &nbsp;<span style="color:{THEME['text_muted']}">scale −1 to +1</span>
          </p>
        </div>""",
        unsafe_allow_html=True,
    )

with col3:
    if df_filtered.empty:
        st.metric("Against (%)", "—")
    else:
        pct_against = (df_filtered["stance"] == "against").mean() * 100
        st.metric("Against (%)", f"{pct_against:.1f}%")

with col4:
    if df_filtered.empty:
        st.metric("In Favor (%)", "—")
    else:
        pct_favor = (df_filtered["stance"] == "for").mean() * 100
        st.metric("In Favor (%)", f"{pct_favor:.1f}%")
    
st.markdown('<br>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# TABS
# ══════════════════════════════════════════    
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Pulse", "Topics", "Sources", "Posts", "Summary"])

_no_data_msg = "Select topics and source categories in the sidebar to view data."

with tab1:  # ── PULSE ──
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        # ── Snapshot ──
        st.markdown("### Snapshot")
        snap_a, snap_b = st.columns(2)

        with snap_a:
            st.markdown("##### Posts per Topic")
            topic_counts = df_filtered["topic"].value_counts().sort_values()
            fig = go.Figure(go.Bar(
                x=topic_counts.values, y=topic_counts.index,
                orientation="h", marker_color=THEME["primary"],
                hovertemplate="%{y}: %{x} posts<extra></extra>",
            ))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Posts")
            st.plotly_chart(fig, use_container_width=True)

        with snap_b:
            st.markdown("##### Sentiment Split")
            bins = pd.cut(df_filtered["sentiment_score"], bins=[-1, -0.05, 0.05, 1],
                          labels=["negative", "neutral", "positive"])
            sent_counts = bins.value_counts()
            _sent_order = ["positive", "negative", "neutral"]
            _sent_colors = [THEME["positive"], THEME["negative"], THEME["neutral"]]
            sent_counts = sent_counts.reindex(_sent_order, fill_value=0)
            fig = go.Figure(go.Pie(
                labels=sent_counts.index, values=sent_counts.values,
                marker_colors=_sent_colors, hole=0.45,
            ))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Conversation Volume Over Time ──
        st.markdown("### Conversation Volume Over Time")
        st.caption("When was each topic most discussed?")

        daily_vol_all = df_filtered.groupby(["date", "topic"]).size().reset_index(name="posts")
        vol_points = daily_vol_all.groupby("topic").size()
        vol_default = sorted(
            vol_points.drop(labels=["other"], errors="ignore").nlargest(5).index.tolist()
        )

        vcol_a, vcol_b = st.columns([3, 1])
        with vcol_a:
            vol_selection = st.multiselect(
                "Compare topics ",
                options=sorted(daily_vol_all["topic"].unique()),
                default=vol_default,
                key="vol_topics",
            )
        with vcol_b:
            vol_smooth = st.checkbox("7-day rolling sum", value=False, key="vol_smooth",
                                     help="Each day shows the total posts from the past 7 days. Smooths out daily spikes to reveal the underlying trend.")

        daily_vol = daily_vol_all[daily_vol_all["topic"].isin(vol_selection)].copy() if vol_selection else daily_vol_all.copy()

        if vol_smooth:
            daily_vol["posts"] = (
                daily_vol.groupby("topic")["posts"]
                .transform(lambda s: s.rolling(7, min_periods=1).sum())
                .round(0).astype(int)
            )

        fig = px.bar(
            daily_vol, x="date", y="posts", color="topic",
            color_discrete_map=TOPIC_COLORS,
            labels={"posts": "Posts", "date": "Date", "topic": "Topic"},
        )
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %d, %Y}<br>Posts: %{y}<extra></extra>"
        )
        fig.update_layout(height=380, barmode="stack")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Opinion River ──
        st.markdown("### Opinion River — Stance Proportions Over Time")
        st.caption("How does the balance of support, opposition, and neutrality shift day to day?")
        stance_time = df_filtered.groupby(["date", "stance"]).size().reset_index(name="count")
        stance_total_day = stance_time.groupby("date")["count"].transform("sum")
        stance_time["pct"] = (stance_time["count"] / stance_total_day * 100).round(2)
        fig = px.area(
            stance_time, x="date", y="pct", color="stance",
            color_discrete_map={"for": THEME["positive"], "against": THEME["negative"], "neutral": THEME["neutral"]},
            labels={"pct": "Share (%)", "date": "Date"},
        )
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %d, %Y}<br>Share: %{y:.2f}%<extra></extra>"
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Controversy Map ──
        st.markdown("### Controversy Map")
        st.caption("Upper-right = polarized (strong opinions both ways). Lower-right = broadly supported. Bubble size = post count.")
        controversy = df_filtered.groupby("topic").agg(
            pct_for=("stance", lambda x: round((x == "for").mean() * 100, 2)),
            pct_against=("stance", lambda x: round((x == "against").mean() * 100, 2)),
            post_count=("stance", "count"),
        ).reset_index()
        fig = px.scatter(
            controversy, x="pct_for", y="pct_against",
            size="post_count", color="topic", text="topic",
            color_discrete_map=TOPIC_COLORS,
            labels={"pct_for": "% In Favor", "pct_against": "% Against", "topic": "Topic", "post_count": "Posts"},
            size_max=60,
        )
        fig.update_traces(
            textposition="top center",
            hovertemplate="<b>%{text}</b><br>In Favor: %{x:.1f}%<br>Against: %{y:.1f}%<br>Posts: %{marker.size}<extra></extra>",
        )
        fig.add_vline(x=25, line_dash="dot", line_color=THEME["border"])
        fig.add_hline(y=25, line_dash="dot", line_color=THEME["border"])
        fig.update_layout(height=480, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with tab2:  # ── TOPICS ──
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        # ── Avg Sentiment per Topic ──
        st.markdown("### How Do Topics Compare?")
        topic_sent = df_filtered.groupby("topic")["sentiment_score"].mean().sort_values().round(4)
        colors = [THEME["negative"] if v < 0 else THEME["positive"] for v in topic_sent.values]
        fig = go.Figure(go.Bar(
            x=topic_sent.values, y=topic_sent.index,
            orientation="h", marker_color=colors,
            hovertemplate="%{y}<br>Avg Sentiment: %{x:+.4f}<extra></extra>",
        ))
        fig.update_layout(height=400, xaxis_title="Avg Sentiment")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Sentiment Trends ──
        st.markdown("### Sentiment Trends Over Time")
        daily_all = df_filtered.groupby(["date", "topic"])["sentiment_score"].mean().reset_index()
        daily_all = daily_all.sort_values(["topic", "date"])

        points_per_topic = daily_all.groupby("topic").size()
        sparse_topics = points_per_topic[points_per_topic < 3].index.tolist()
        default_topics = sorted(
            points_per_topic[points_per_topic >= 3]
            .drop(labels=["other"], errors="ignore")
            .nlargest(5).index.tolist()
        )

        ctrl_a, ctrl_b, ctrl_c = st.columns([3, 1, 1])
        with ctrl_a:
            topic_selection = st.multiselect(
                "Compare topics",
                options=sorted(daily_all["topic"].unique()),
                default=default_topics,
                help="Topics with fewer than 3 data points may not show a clear trend.",
            )
        with ctrl_b:
            smooth = st.checkbox("7-day avg", value=True)
        with ctrl_c:
            scale_mode = st.selectbox("Scale", ["Raw", "Z-score"], index=0,
                                      help="Z-score: each topic centred on its own mean.")

        if sparse_topics:
            st.caption(f"Low data (< 3 points): {', '.join(sorted(sparse_topics))} — excluded by default.")

        daily = daily_all[daily_all["topic"].isin(topic_selection)].copy() if topic_selection else daily_all.copy()

        if smooth:
            daily["sentiment_score"] = (
                daily.groupby("topic")["sentiment_score"]
                .transform(lambda s: s.rolling(7, min_periods=1, center=True).mean())
            )

        if scale_mode == "Z-score":
            daily["sentiment_score"] = (
                daily.groupby("topic")["sentiment_score"]
                .transform(lambda s: (s - s.mean()) / s.std() if s.std() > 0 else s - s.mean())
            )
            y_label = "Sentiment (std devs from topic mean)"
            zero_label = "Each topic's average"
        else:
            y_label = "Avg Sentiment"
            zero_label = "Neutral (0)"

        daily["sentiment_score"] = daily["sentiment_score"].round(4)
        fig = px.line(
            daily, x="date", y="sentiment_score", color="topic",
            markers=True, color_discrete_map=TOPIC_COLORS,
            labels={"sentiment_score": y_label, "date": "Date", "topic": "Topic"},
        )
        fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %d, %Y}<br>" + y_label + ": %{y:+.4f}<extra></extra>"
        )
        fig.add_hline(y=0, line_dash="dot", line_color=THEME["text"], opacity=0.25,
                      annotation_text=zero_label, annotation_position="bottom right",
                      annotation_font=dict(color=THEME["text_muted"], size=10))
        fig.update_layout(height=450, legend=dict(orientation="v", x=1.01, y=1, xanchor="left"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Stance Distribution ──
        st.markdown("### Stance Distribution by Topic")
        stance_df = df_filtered.groupby(["topic", "stance"]).size().reset_index(name="count")
        stance_total = stance_df.groupby("topic")["count"].transform("sum")
        stance_df["pct"] = (stance_df["count"] / stance_total * 100).round(2)
        fig = px.bar(stance_df, x="topic", y="pct", color="stance",
                     color_discrete_map={"for": THEME["positive"], "against": THEME["negative"], "neutral": THEME["neutral"]},
                     labels={"pct": "Percentage (%)", "topic": "Topic"})
        fig.update_traces(
            hovertemplate="<b>%{x}</b> · %{fullData.name}<br>Percentage: %{y:.2f}%<extra></extra>"
        )
        fig.update_layout(height=400, barmode="stack")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Per-Topic Drill-down ──
        st.markdown("### Deep Dive by Topic")
        filtered_topics = sorted(df_filtered["topic"].unique())
        selected_topic = st.selectbox("Choose a topic", filtered_topics)
        topic_df = df_filtered[df_filtered["topic"] == selected_topic]

        st.markdown(f"#### {selected_topic.title()} — {len(topic_df)} posts")

        col_a, col_b, col_c = st.columns(3)
        _ts = topic_df["sentiment_score"].mean() if not topic_df.empty else None
        col_a.metric(
            "Avg Sentiment",
            sentiment_label(_ts) if _ts is not None else "—",
            delta=f"{_ts:+.3f}  (scale −1 to +1)" if _ts is not None else None,
            delta_color="normal",
            help="Ranges from −1 (very negative) to +1 (very positive)",
        )
        col_b.metric("% In Favor", f"{(topic_df['stance']=='for').mean()*100:.1f}%" if not topic_df.empty else "—")
        col_c.metric("% Against", f"{(topic_df['stance']=='against').mean()*100:.1f}%" if not topic_df.empty else "—")

        st.markdown("##### Sentiment Over Time")
        daily = topic_df.groupby("date")["sentiment_score"].mean().reset_index()
        daily["sentiment_score"] = daily["sentiment_score"].round(4)
        fig = px.line(daily, x="date", y="sentiment_score", markers=True,
                      labels={"sentiment_score": "Avg Sentiment", "date": "Date"})
        fig.update_traces(
            line_color=THEME["primary"],
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>Avg Sentiment: %{y:+.4f}<extra></extra>",
        )
        fig.add_hline(y=0, line_dash="dash", line_color=THEME["text_muted"], opacity=0.5)
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("##### Top Sources")
            src_counts = topic_df["source_name"].value_counts().head(10).sort_values(ascending=True)
            fig = go.Figure(go.Bar(x=src_counts.values, y=src_counts.index, orientation="h",
                                   marker_color=THEME["primary"]))
            fig.update_layout(height=360, xaxis_title="Posts")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if EMOTIONS_AVAILABLE:
                st.markdown("##### Emotion Profile")
                emo_avgs = {
                    e: topic_df["emotions_parsed"].apply(lambda x: x.get(e, 0) if x else 0).mean()
                    for e in EMOTION_LABELS
                }
                values = list(emo_avgs.values()) + [list(emo_avgs.values())[0]]
                theta = EMOTION_LABELS + [EMOTION_LABELS[0]]
                fig = go.Figure(go.Scatterpolar(
                    r=values, theta=theta, fill="toself",
                    line_color=THEME["primary"], fillcolor=THEME["primary"], opacity=0.3,
                ))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 0.5])), height=360)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.markdown("##### Stance Breakdown")
                _stance_order = ["for", "against", "neutral"]
                _stance_colors = [THEME["positive"], THEME["negative"], THEME["neutral"]]
                stance_counts = topic_df["stance"].value_counts().reindex(_stance_order, fill_value=0)
                fig = go.Figure(go.Pie(
                    labels=stance_counts.index, values=stance_counts.values,
                    marker_colors=_stance_colors, hole=0.45,
                ))
                fig.update_layout(height=360)
                st.plotly_chart(fig, use_container_width=True)

with tab3:  # ── SOURCES ──
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        st.markdown("### Sentiment by Source — Topic Breakdown")
        st.caption(
            "Each panel is a source category. Bars show avg sentiment per topic — "
            "green = positive, red = negative. Missing bars = no coverage of that topic."
        )
        facet_data = (
            df_filtered.groupby(["topic", "source_category"])
            .agg(avg_sentiment=("sentiment_score", "mean"), post_count=("sentiment_score", "count"))
            .reset_index()
        )
        facet_data["avg_sentiment"] = facet_data["avg_sentiment"].round(4)
        facet_data["sentiment_label"] = facet_data["avg_sentiment"].apply(sentiment_label)
        facet_data["bar_color"] = facet_data["avg_sentiment"].apply(
            lambda v: THEME["positive"] if v >= 0.05 else THEME["negative"] if v <= -0.05 else THEME["neutral"]
        )

        n_cats = facet_data["source_category"].nunique()
        n_topics = facet_data["topic"].nunique()

        fig = px.bar(
            facet_data,
            x="avg_sentiment", y="topic",
            facet_col="source_category",
            color="avg_sentiment",
            color_continuous_scale="RdYlGn",
            range_color=[-0.5, 0.5],
            color_continuous_midpoint=0,
            orientation="h",
            custom_data=["sentiment_label", "post_count"],
            labels={"avg_sentiment": "Avg Sentiment", "topic": "Topic", "source_category": ""},
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Sentiment: %{customdata[0]} (%{x:+.4f})<br>"
                "Posts: %{customdata[1]:,}<extra></extra>"
            )
        )
        fig.add_vline(x=0, line_dash="dot", line_color=THEME["text_muted"], opacity=0.5)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1].title()))
        fig.update_layout(
            height=max(400, n_topics * 30 * n_cats + 120),
            coloraxis_showscale=False,
            showlegend=False,
        )
        fig.update_yaxes(matches=None)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        st.markdown("### Posts by Source")
        st.caption("Which outlets and platforms contribute the most content?")
        src_counts = df_filtered["source_name"].value_counts().head(15).sort_values(ascending=True)
        fig = go.Figure(go.Bar(
            x=src_counts.values, y=src_counts.index,
            orientation="h", marker_color=THEME["primary"],
            hovertemplate="%{y}: %{x} posts<extra></extra>",
        ))
        fig.update_layout(height=450, xaxis_title="Posts")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Browse Posts")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        search = st.text_input("Search content", "")
    with col_b:
        sort_by = st.selectbox("Sort by", ["Newest", "Most Engaged", "Most Negative", "Most Positive", "For (Stance)", "Against (Stance)", "Neutral (Stance)"])

    posts_view = df_filtered.copy()
    if search:
        posts_view = posts_view[posts_view["content"].str.contains(search, case=False, na=False)]

    if sort_by == "Newest":
        posts_view = posts_view.sort_values("created_at", ascending=False)
    elif sort_by == "Most Engaged":
        posts_view = posts_view.sort_values("engagement", ascending=False)
    elif sort_by == "Most Negative":
        posts_view = posts_view.sort_values("sentiment_score", ascending=True)
    elif sort_by == "Most Positive":
        posts_view = posts_view.sort_values("sentiment_score", ascending=False)
    elif sort_by == "For (Stance)":
        posts_view = posts_view[posts_view["stance"] == "for"].sort_values("created_at", ascending=False)
    elif sort_by == "Against (Stance)":
        posts_view = posts_view[posts_view["stance"] == "against"].sort_values("created_at", ascending=False)
    elif sort_by == "Neutral (Stance)":
        posts_view = posts_view[posts_view["stance"] == "neutral"].sort_values("created_at", ascending=False)

    posts_view = posts_view.head(20)

    if posts_view.empty:
        st.info(_no_data_msg)
    else:
        for _, row in posts_view.iterrows():
            sentiment_color = THEME["positive"] if row["sentiment_score"] > 0.2 else THEME["negative"] if row["sentiment_score"] < -0.2 else THEME["neutral"]
            content = clean_content(row["content"])
            preview = content[:200] + "..." if len(content) > 200 else content
            label = f"**{row['source_name'].upper()}** · {row['topic']} · Sentiment: {row['sentiment_score']:+.2f} · Stance: {row['stance']}"
            url = None
            pid = str(row.get("platform_id", "")) if pd.notna(row.get("platform_id")) else ""

            if pid.startswith("http"):
                # Guardian and RSS feeds store full article URL directly
                url = pid
            elif pid.startswith("video_"):
                # YouTube video: "video_{video_id}"
                video_id = pid[len("video_"):]
                if video_id:
                    url = f"https://www.youtube.com/watch?v={video_id}"
            elif pid.startswith("comment_"):
                # YouTube comment: "comment_{video_id}_{yt_comment_id}"
                # YouTube comment IDs always start with "Ug", so find the last "_Ug"
                remainder = pid[len("comment_"):]
                ug_idx = remainder.rfind("_Ug")
                if ug_idx > 0:
                    video_id = remainder[:ug_idx]
                    url = f"https://www.youtube.com/watch?v={video_id}"
            with st.expander(preview, expanded=False):
                st.markdown(f"""
                <div style='border-left: 3px solid {sentiment_color}; padding: 0.75rem 1rem; background: {THEME["panel"]};'>
                    <div style='font-size: 0.75rem; color: {THEME["text_muted"]}; margin-bottom: 0.5rem;'>
                        {label}
                    </div>
                    <div style='font-family: Lora, serif; font-size: 1rem; line-height: 1.6;'>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if url:
                    st.markdown(f"[Read original article →]({url})", unsafe_allow_html=False)

with tab5:
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        st.markdown("### Opinion Pulse — Summary by Topic")
        summary = []
        for topic in sorted(df_filtered["topic"].unique()):
            t = df_filtered[df_filtered["topic"] == topic]
            dominant_emotion = "—"
            if EMOTIONS_AVAILABLE:
                emo_sums = {
                    e: t["emotions_parsed"].apply(lambda x: x.get(e, 0) if x else 0).sum()
                    for e in EMOTION_LABELS
                }
                dominant_emotion = max(emo_sums, key=emo_sums.get)
            summary.append({
                "Topic": topic,
                "Posts": len(t),
                "Avg Sentiment": f"{t['sentiment_score'].mean():+.3f}",
                "% For": f"{(t['stance']=='for').mean()*100:.1f}%",
                "% Against": f"{(t['stance']=='against').mean()*100:.1f}%",
                "% Neutral": f"{(t['stance']=='neutral').mean()*100:.1f}%",
                "Dominant Emotion": dominant_emotion,
                "Top Source": t["source_name"].value_counts().index[0],
            })
        summary_df = pd.DataFrame(summary)
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=list(summary_df.columns),
                fill_color=THEME["primary"],
                font=dict(color="white", size=12),
                align="center",
            ),
            cells=dict(
                values=[summary_df[col] for col in summary_df.columns],
                fill_color=[[THEME["panel"] if i % 2 == 0 else THEME["bg"] for i in range(len(summary_df))]],
                font=dict(color=THEME["text"], size=11),
                align="center",
                height=30,
            ),
        )])
        fig.update_layout(height=max(300, len(summary_df) * 40 + 80))
        st.plotly_chart(fig, use_container_width=True)
        
# ══════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════
st.markdown('<div class="nyt-divider"></div>', unsafe_allow_html=True)
st.markdown(f"""
<div style='font-family: Inter, sans-serif; font-size: 0.8rem; color: {THEME["text_muted"]};'>
Data sources: Bluesky, YouTube, The Guardian, Dev.to, RSS feeds  ·
Built with Streamlit, Supabase, and HuggingFace
</div>
""", unsafe_allow_html=True)