import importlib

import altair as alt
import pandas as pd
import streamlit as st

GSHEETS_WORKSHEET = "turn_log"
UNKNOWN_VALUE = "-"


# safe_str関数: None/nanを安全に文字列化
def safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    if text.lower() == "nan":
        return default
    return text


# parse_optional_bool関数: 真偽判定できない値はNoneで返す
def parse_optional_bool(value: object) -> bool | None:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "t"}:
        return True
    if text in {"false", "0", "no", "n", "f"}:
        return False
    return None


# normalize_is_break_value関数: is_break値をboolへ正規化
def normalize_is_break_value(value: object) -> bool:
    parsed = parse_optional_bool(value)
    return False if parsed is None else parsed


# normalize_unknown関数: 空欄を「-」へ正規化
def normalize_unknown(value: object) -> str:
    text = safe_str(value, "").strip()
    return text if text else UNKNOWN_VALUE


# get_gsheets_connection関数: Google Sheets接続を取得
def get_gsheets_connection():
    try:
        gsheets_module = importlib.import_module("streamlit_gsheets")
        gsheets_connection_class = getattr(gsheets_module, "GSheetsConnection")
        return st.connection("gsheets", type=gsheets_connection_class)
    except Exception:
        return None


# load_turn_log_df関数: turn_logシートをDataFrameとして読み込む
def load_turn_log_df() -> tuple[pd.DataFrame, str]:
    conn = get_gsheets_connection()
    if conn is None:
        return pd.DataFrame(), "Google Sheets接続が見つかりません。"

    try:
        df = conn.read(worksheet=GSHEETS_WORKSHEET, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(), "turn_log が空です。"
        df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed:")]
        return df, ""
    except Exception as e:
        return pd.DataFrame(), f"turn_log の読込に失敗しました: {e}"


# render_score_trend_chart関数: 得点推移グラフを描画
def render_score_trend_chart(df: pd.DataFrame, team_a_name: str, team_b_name: str) -> None:
    if df.empty or "turn_no" not in df.columns:
        st.info("得点推移を表示するデータがありません。")
        return

    plot_df = df[["turn_no", "A_score", "B_score"]].copy()
    plot_df = plot_df.rename(columns={"A_score": team_a_name, "B_score": team_b_name})
    long_df = plot_df.melt(id_vars=["turn_no"], var_name="team", value_name="score")

    line = (
        alt.Chart(long_df)
        .mark_line(point=True, interpolate="step-after", strokeWidth=3)
        .encode(
            x=alt.X("turn_no:Q", title="ターン", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("score:Q", title="得点", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("team:N", title="チーム"),
            tooltip=[
                alt.Tooltip("turn_no:Q", title="ターン"),
                alt.Tooltip("team:N", title="チーム"),
                alt.Tooltip("score:Q", title="得点"),
            ],
        )
    )

    labels = (
        alt.Chart(long_df)
        .transform_window(
            row_number="row_number()",
            sort=[alt.SortField("turn_no", order="descending")],
            groupby=["team"],
        )
        .transform_filter("datum.row_number == 1")
        .mark_text(dx=8, dy=-8, fontSize=12)
        .encode(
            x="turn_no:Q",
            y="score:Q",
            text=alt.Text("score:Q"),
            color="team:N",
        )
    )

    st.altair_chart((line + labels).properties(height=360), use_container_width=True)
