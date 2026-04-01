import pandas as pd
import streamlit as st

from app.analysis_utils import (
    load_turn_log_df,
    normalize_is_break_value,
    render_score_trend_chart,
    safe_str,
)

st.set_page_config(page_title="データ分析", layout="wide")
st.title("データ分析")

turn_df, err = load_turn_log_df()
if err:
    st.warning(err)
    st.stop()

required_cols = {"match_id", "turn_no", "point_winner", "offense_start_team", "is_break", "team_a_name", "team_b_name"}
missing = required_cols - set(turn_df.columns)
if missing:
    st.error(f"turn_log の列が不足しています: {', '.join(sorted(missing))}")
    st.stop()

if "match_format" not in turn_df.columns:
    turn_df["match_format"] = "-"
if "drop_count" not in turn_df.columns:
    turn_df["drop_count"] = 0

turn_df["turn_no"] = pd.to_numeric(turn_df["turn_no"], errors="coerce").fillna(0).astype(int)
turn_df["drop_count"] = pd.to_numeric(turn_df["drop_count"], errors="coerce").fillna(0).astype(int)
turn_df["is_break"] = turn_df["is_break"].apply(normalize_is_break_value)

match_options = (
    turn_df[["match_id", "match_date", "match_title", "match_format", "team_a_name", "team_b_name"]]
    .drop_duplicates(subset=["match_id"], keep="last")
    .copy()
)
match_options["label"] = (
    match_options["match_date"].astype(str)
    + " | "
    + match_options["match_title"].astype(str)
    + " | "
    + match_options["match_format"].astype(str)
    + " | "
    + match_options["team_a_name"].astype(str)
    + " vs "
    + match_options["team_b_name"].astype(str)
)


def resolve_own_team_code(row: pd.Series) -> str:
    return "A"


match_options["own_team_code"] = match_options.apply(resolve_own_team_code, axis=1)

with st.container(border=True):
    st.subheader("① 試合一覧KPI")
    st.caption("試合全体を俯瞰して、比較したい試合を絞り込みます。")

    format_choices = sorted([x for x in match_options["match_format"].dropna().astype(str).unique().tolist() if x.strip()])
    selected_formats = st.multiselect("試合フォーマットで絞り込み", options=format_choices, default=format_choices)
    filtered_match_options = match_options.copy()
    if selected_formats:
        filtered_match_options = filtered_match_options[filtered_match_options["match_format"].astype(str).isin(selected_formats)]

    kpi_rows: list[dict] = []
    for _, match_row in filtered_match_options.iterrows():
        match_id = safe_str(match_row.get("match_id", ""), "")
        own_code = safe_str(match_row.get("own_team_code", "A"), "A")
        team_a_name = safe_str(match_row.get("team_a_name", "Aチーム"), "Aチーム")
        team_b_name = safe_str(match_row.get("team_b_name", "Bチーム"), "Bチーム")
        own_label = team_a_name if own_code == "A" else team_b_name

        g = turn_df[turn_df["match_id"].astype(str) == match_id].copy()
        g = g.sort_values("turn_no")
        offense = g[g["offense_start_team"] == own_code]
        defense = g[g["offense_start_team"] != own_code]

        off_n = len(offense)
        def_n = len(defense)
        keep_n = int((offense["point_winner"] == own_code).sum()) if off_n else 0
        break_n = int((defense["point_winner"] == own_code).sum()) if def_n else 0
        against_break_n = int((offense["point_winner"] != own_code).sum()) if off_n else 0
        clean_keep_n = int(((offense["point_winner"] == own_code) & (offense["drop_count"] == 0)).sum()) if off_n else 0

        kpi_rows.append(
            {
                "match_id": match_id,
                "試合": safe_str(match_row.get("label", ""), ""),
                "フォーマット": safe_str(match_row.get("match_format", "-"), "-"),
                "自チーム": own_label,
                "オフェンス回数": off_n,
                "ディフェンス回数": def_n,
                "キープ率": (keep_n / off_n) if off_n else 0.0,
                "ブレイク率": (break_n / def_n) if def_n else 0.0,
                "被ブレイク率": (against_break_n / off_n) if off_n else 0.0,
                "クリーンキープ率": (clean_keep_n / off_n) if off_n else 0.0,
            }
        )

    if kpi_rows:
        kpi_df = pd.DataFrame(kpi_rows)
        for col in ["キープ率", "ブレイク率", "被ブレイク率", "クリーンキープ率"]:
            kpi_df[col] = (kpi_df[col] * 100).map(lambda x: f"{x:.1f}%")
        st.dataframe(
            kpi_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("表示対象の試合がありません。")

st.divider()

with st.container(border=True):
    st.subheader("② 分析対象の試合")
    st.caption("ここで選んだ1試合に対して、下の詳細分析を表示します。")
    selected_match_id = st.selectbox(
        "分析対象の試合",
        options=filtered_match_options["match_id"].tolist() if not filtered_match_options.empty else match_options["match_id"].tolist(),
        format_func=lambda x: match_options.loc[match_options["match_id"] == x, "label"].iloc[0],
    )

df = turn_df[turn_df["match_id"].astype(str) == str(selected_match_id)].copy()
if df.empty:
    st.info("この試合のデータがありません。")
    st.stop()

df = df.sort_values("turn_no")

team_a = safe_str(df.iloc[-1].get("team_a_name", "Aチーム"), "Aチーム")
team_b = safe_str(df.iloc[-1].get("team_b_name", "Bチーム"), "Bチーム")

df["A_score"] = (df["point_winner"] == "A").cumsum()
df["B_score"] = (df["point_winner"] == "B").cumsum()

st.subheader("現在スコア")
latest = df.iloc[-1]
c1, c2 = st.columns(2)
c1.metric(team_a, int(latest["A_score"]))
c2.metric(team_b, int(latest["B_score"]))

st.subheader("得点推移")
render_score_trend_chart(df, team_a, team_b)

st.subheader("ブレイク集計")
break_a = int(((df["point_winner"] == "A") & (df["is_break"])).sum())
break_b = int(((df["point_winner"] == "B") & (df["is_break"])).sum())
b1, b2 = st.columns(2)
b1.metric(f"{team_a}のブレイク数", break_a)
b2.metric(f"{team_b}のブレイク数", break_b)

st.subheader("メンバー分析（被ブレイク率 / クリーンキープ率）")
selected_match_row = match_options[match_options["match_id"].astype(str) == str(selected_match_id)].iloc[0]
default_team_code = resolve_own_team_code(selected_match_row)
team_code = st.radio(
    "分析するチーム",
    ["A", "B"],
    horizontal=True,
    index=0 if default_team_code == "A" else 1,
    format_func=lambda x: team_a if x == "A" else team_b,
)

member_col = "team_a_member" if team_code == "A" else "team_b_member"
opponent_force_col = "team_b_force" if team_code == "A" else "team_a_force"
opponent_defense_col = "team_b_defense_type" if team_code == "A" else "team_a_defense_type"
opponent_wind_col = "team_b_wind" if team_code == "A" else "team_a_wind"

for col in [member_col, opponent_force_col, opponent_defense_col, opponent_wind_col]:
    if col not in df.columns:
        df[col] = "-"

member_options = sorted([m for m in df[member_col].dropna().astype(str).unique().tolist() if m.strip()])
if not member_options:
    st.info("この試合にメンバー情報がありません。")
else:
    selected_member = st.selectbox("メンバー", options=member_options)

    offense_df = df[(df["offense_start_team"] == team_code) & (df[member_col].astype(str) == selected_member)].copy()

    if offense_df.empty:
        st.caption("このメンバーのオフェンス開始ターンがありません。")
    else:
        against_break_num = int((offense_df["point_winner"] != team_code).sum())
        against_break_den = int(len(offense_df))
        against_break_rate = against_break_num / against_break_den if against_break_den else 0.0

        clean_keep_num = int(((offense_df["point_winner"] == team_code) & (offense_df["drop_count"] == 0)).sum())
        clean_keep_den = int(len(offense_df))
        clean_keep_rate = clean_keep_num / clean_keep_den if clean_keep_den else 0.0

        m1, m2 = st.columns(2)
        m1.metric("被ブレイク率", f"{against_break_rate:.1%}", help=f"{against_break_num} / {against_break_den}")
        m2.metric("クリーンキープ率", f"{clean_keep_rate:.1%}", help=f"{clean_keep_num} / {clean_keep_den}")

        st.markdown("##### 条件別比較（相手フォース / 相手Dタイプ / 相手風向き）")

        compare_cols = [
            (opponent_force_col, "相手フォース"),
            (opponent_defense_col, "相手ディフェンスタイプ"),
            (opponent_wind_col, "相手風向き"),
        ]

        tables = []
        for key_col, label in compare_cols:
            work = offense_df.copy()
            work[key_col] = work[key_col].astype(str).replace("", "-")
            grouped = work.groupby(key_col, dropna=False)

            summary = grouped.agg(
                ターン数=("turn_no", "count"),
                被ブレイク数=("point_winner", lambda s: int((s != team_code).sum())),
                クリーンキープ数=("point_winner", lambda s: 0),
            ).reset_index()

            clean_counts = (
                work.assign(_clean=((work["point_winner"] == team_code) & (work["drop_count"] == 0)).astype(int))
                .groupby(key_col, dropna=False)["_clean"]
                .sum()
                .reset_index(name="クリーンキープ数")
            )
            summary = summary.drop(columns=["クリーンキープ数"]).merge(clean_counts, on=key_col, how="left")

            summary["被ブレイク率"] = summary["被ブレイク数"] / summary["ターン数"]
            summary["クリーンキープ率"] = summary["クリーンキープ数"] / summary["ターン数"]
            summary.insert(0, "比較軸", label)
            summary = summary.rename(columns={key_col: "条件"})
            tables.append(summary)

        compare_df = pd.concat(tables, ignore_index=True)
        st.dataframe(compare_df, use_container_width=True, hide_index=True)

st.subheader("ターンログ（分析用）")
show_cols = [
    "turn_no",
    "offense_start_team",
    "point_winner",
    "is_break",
    "A_score",
    "B_score",
]
show_df = df[show_cols].copy()
show_df["offense_start_team"] = show_df["offense_start_team"].replace({"A": team_a, "B": team_b})
show_df["point_winner"] = show_df["point_winner"].replace({"A": team_a, "B": team_b})
show_df = show_df.rename(columns={"A_score": team_a, "B_score": team_b})
st.dataframe(show_df, use_container_width=True, hide_index=True)
