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
        st.metric("Average Sentiment", "—")
    else:
        avg_sent = df_filtered["sentiment_score"].mean()
        st.metric("Average Sentiment", f"{avg_sent:+.3f}")

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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "By Topic", "By Source", "Posts", "Summary"])

_no_data_msg = "Select topics and source categories in the sidebar to view data."

with tab1:
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        # ── Snapshot row ──
        st.markdown("### Snapshot")
        snap_a, snap_b, snap_c = st.columns(3)

        with snap_a:
            st.markdown("##### Posts per Topic")
            topic_counts = df_filtered["topic"].value_counts().sort_values()
            fig = go.Figure(go.Bar(
                x=topic_counts.values, y=topic_counts.index,
                orientation="h", marker_color=THEME["primary"],
            ))
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Posts")
            st.plotly_chart(fig, use_container_width=True)

        with snap_b:
            st.markdown("##### Sentiment Split")
            if "sentiment_label" in df_filtered.columns:
                sent_counts = df_filtered["sentiment_label"].value_counts()
            else:
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
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with snap_c:
            st.markdown("##### By Source Category")
            cat_counts = df_filtered["source_category"].value_counts()
            fig = go.Figure(go.Pie(
                labels=cat_counts.index, values=cat_counts.values, hole=0.45,
            ))
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # ── Sentiment trends ──
        st.markdown("### Sentiment Trends Over Time")

        daily_all = df_filtered.groupby(["date", "topic"])["sentiment_score"].mean().reset_index()
        daily_all = daily_all.sort_values(["topic", "date"])

        # Only offer topics that have enough data points to show a meaningful trend
        points_per_topic = daily_all.groupby("topic").size()
        rich_topics = points_per_topic[points_per_topic >= 3].index.tolist()
        sparse_topics = points_per_topic[points_per_topic < 3].index.tolist()

        ctrl_a, ctrl_b, ctrl_c = st.columns([3, 1, 1])
        with ctrl_a:
            topic_selection = st.multiselect(
                "Compare topics",
                options=sorted(daily_all["topic"].unique()),
                default=sorted(rich_topics),
                help="Topics with fewer than 3 data points may not show a clear trend.",
            )
        with ctrl_b:
            smooth = st.checkbox("7-day avg", value=False)
        with ctrl_c:
            scale_mode = st.selectbox("Scale", ["Raw", "Z-score"], index=0,
                                      help="Z-score: each topic centred on its own mean. Shows relative spikes, not absolute values.")

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

        fig = px.line(
            daily, x="date", y="sentiment_score", color="topic",
            markers=True,
            labels={"sentiment_score": y_label, "date": "Date", "topic": "Topic"},
        )
        fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %d, %Y}<br>" + y_label + ": %{y:+.2f}<extra></extra>"
        )
        fig.add_hline(y=0, line_dash="dot", line_color=THEME["text"], opacity=0.25,
                      annotation_text=zero_label, annotation_position="bottom right",
                      annotation_font=dict(color=THEME["text_muted"], size=10))
        fig.update_layout(height=450, legend=dict(orientation="v", x=1.01, y=1, xanchor="left"))
        st.plotly_chart(fig, use_container_width=True)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### Stance Distribution")
            stance_df = df_filtered.groupby(["topic", "stance"]).size().reset_index(name="count")
            stance_total = stance_df.groupby("topic")["count"].transform("sum")
            stance_df["pct"] = stance_df["count"] / stance_total * 100
            fig = px.bar(stance_df, x="topic", y="pct", color="stance",
                         color_discrete_map={"for": THEME["positive"], "against": THEME["negative"], "neutral": THEME["neutral"]},
                         labels={"pct": "Percentage (%)"})
            fig.update_layout(height=400, barmode="stack")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.markdown("### Avg Sentiment per Topic")
            topic_sent = df_filtered.groupby("topic")["sentiment_score"].mean().sort_values()
            colors = [THEME["negative"] if v < 0 else THEME["positive"] for v in topic_sent.values]
            fig = go.Figure(go.Bar(
                x=topic_sent.values, y=topic_sent.index,
                orientation="h", marker_color=colors,
            ))
            fig.update_layout(height=400, xaxis_title="Avg Sentiment")
            st.plotly_chart(fig, use_container_width=True)

        # ── Opinion River ──
        st.markdown("### Opinion River — Stance Proportions Over Time")
        stance_time = df_filtered.groupby(["date", "stance"]).size().reset_index(name="count")
        stance_total_day = stance_time.groupby("date")["count"].transform("sum")
        stance_time["pct"] = stance_time["count"] / stance_total_day * 100
        fig = px.area(
            stance_time, x="date", y="pct", color="stance",
            color_discrete_map={"for": THEME["positive"], "against": THEME["negative"], "neutral": THEME["neutral"]},
            labels={"pct": "Share (%)", "date": "Date"},
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        filtered_topics = sorted(df_filtered["topic"].unique())
        selected_topic = st.selectbox("Choose a topic to drill down", filtered_topics)
        topic_df = df_filtered[df_filtered["topic"] == selected_topic]

        st.markdown(f"### {selected_topic.title()} — {len(topic_df)} posts")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Avg Sentiment", f"{topic_df['sentiment_score'].mean():+.3f}" if not topic_df.empty else "—")
        col_b.metric("% In Favor", f"{(topic_df['stance']=='for').mean()*100:.1f}%" if not topic_df.empty else "—")
        col_c.metric("% Against", f"{(topic_df['stance']=='against').mean()*100:.1f}%" if not topic_df.empty else "—")

        st.markdown("#### Sentiment Over Time")
        daily = topic_df.groupby("date")["sentiment_score"].mean().reset_index()
        fig = px.line(daily, x="date", y="sentiment_score", markers=True)
        fig.update_traces(line_color=THEME["primary"])
        fig.add_hline(y=0, line_dash="dash", line_color=THEME["text_muted"], opacity=0.5)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### Top Sources")
            src_counts = topic_df["source_name"].value_counts().head(10).sort_values(ascending=True)
            fig = go.Figure(go.Bar(x=src_counts.values, y=src_counts.index, orientation="h",
                                   marker_color=THEME["primary"]))
            fig.update_layout(height=380, xaxis_title="Posts")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.markdown("#### Stance Breakdown")
            _stance_order = ["for", "against", "neutral"]
            _stance_colors = [THEME["positive"], THEME["negative"], THEME["neutral"]]
            stance_counts = topic_df["stance"].value_counts().reindex(_stance_order, fill_value=0)
            fig = go.Figure(go.Pie(
                labels=stance_counts.index, values=stance_counts.values,
                marker_colors=_stance_colors,
                hole=0.45,
            ))
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)

        if EMOTIONS_AVAILABLE:
            st.markdown("#### Emotion Profile")
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
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 0.5])), height=400)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    if df_filtered.empty:
        st.info(_no_data_msg)
    else:
        st.markdown("### Sentiment Heatmap: Topic × Source Category")
        heatmap_data = df_filtered.groupby(["topic", "source_category"])["sentiment_score"].mean().reset_index()
        heatmap_pivot = heatmap_data.pivot(index="topic", columns="source_category", values="sentiment_score")
        fig = px.imshow(
            heatmap_pivot,
            labels=dict(x="Source Category", y="Topic", color="Avg Sentiment"),
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            aspect="auto",
        )
        fig.update_layout(height=max(300, len(heatmap_pivot) * 45 + 80))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Sentiment by Source Category")
        cat_sent = df_filtered.groupby(["source_category", "topic"])["sentiment_score"].mean().reset_index()
        fig = px.bar(cat_sent, x="topic", y="sentiment_score", color="source_category",
                     barmode="group", labels={"sentiment_score": "Avg Sentiment"})
        fig.add_hline(y=0, line_dash="dash", line_color=THEME["text_muted"], opacity=0.5)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Posts by Source")
        src_counts = df_filtered["source_name"].value_counts().head(15).sort_values(ascending=False)
        fig = go.Figure(go.Bar(x=src_counts.index, y=src_counts.values, marker_color=THEME["primary"]))
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Posts")
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
Updated every 5 minutes  ·  
Built with Streamlit, Supabase, and HuggingFace
</div>
""", unsafe_allow_html=True)