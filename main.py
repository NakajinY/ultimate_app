import json
import importlib
from datetime import date
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="アルティメット記録・分析", layout="wide")

OFFENSE_LINEUP_OPTIONS = ["Oセット", "下げO","-"]
DEFENSE_LINEUP_OPTIONS = ["Dセット", "上げマンD", "上げゾーンD","-"]
MEMBER_OPTIONS = OFFENSE_LINEUP_OPTIONS + DEFENSE_LINEUP_OPTIONS
FORCE_OPTIONS = ["サイド", "バック","FM","-"]
DEFENSE_TYPE_OPTIONS = ["マンツー", "ゾーン","-"]
WIND_OPTIONS = ["-","追い風", "横風", "向かい風","無風"]
EVENT_TYPE_OPTIONS = ["ミス", "ナイスディフェンス", "シュート"]
NICE_DEFENSE_TYPE_OPTIONS = ["ストブロ/アウト", "ミート狩り", "シュート狩り"]
DROP_TYPE_OPTIONS = [
    "キャッチミス",
    "スローミス",
]
SHOT_TYPE_OPTIONS = ["ストレート", "ボンバー", "裏シュート","対角シュート"]
THROW_CATEGORY_OPTIONS = ["ミート", "シュート", "ハンド展開"]
THROW_DETAIL_OPTIONS = {
    "ミート": ["インサイ", "オープン"],
    "シュート": ["ストレート", "ボンバー", "裏シュート","対角シュート"],
    "ハンド展開": ["インサイド", "裏", "オープン", "かけ上がり","ダンプ"],
}
PLACE_SIDE_OPTIONS = ["ハメ側","真ん中", "アンハメ側"]
PLACE_END_OPTIONS = ["序盤", "中盤", "エンド前"]
SCORE_PATTERN_OPTIONS = ["シュートがドーン", "ミート、展開コツコツ", "TOからの速攻"]
GSHEETS_WORKSHEET = "turn_log"
GSHEETS_EVENTS_WORKSHEET = "event_log"
UNKNOWN_VALUE = "-"


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    if text.lower() == "nan":
        return default
    return text


def normalize_unknown(value: object) -> str:
    text = safe_str(value, "").strip()
    return text if text else UNKNOWN_VALUE


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def build_match_id(match_date: object, match_title: str, team_a_name: str, team_b_name: str) -> str:
    date_str = safe_str(match_date, "")
    return f"{normalize_unknown(date_str)}_{normalize_unknown(match_title)}_{normalize_unknown(team_a_name)}_vs_{normalize_unknown(team_b_name)}"


def build_turn_id(match_id: str, turn_no: int) -> str:
    return f"{match_id}-{turn_no}"


def parse_date_text_or_today(value: object) -> date:
    text = safe_str(value, "").strip()
    try:
        return date.fromisoformat(text) if text else date.today()
    except ValueError:
        return date.today()


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


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


def build_match_index(turns: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for turn in turns:
        match_id = normalize_unknown(
            turn.get(
                "match_id",
                build_match_id(
                    turn.get("match_date", ""),
                    turn.get("match_title", ""),
                    turn.get("team_a_name", ""),
                    turn.get("team_b_name", ""),
                ),
            )
        )
        if match_id in index:
            continue
        match_date = safe_str(turn.get("match_date", ""), "")
        match_title = safe_str(turn.get("match_title", ""), UNKNOWN_VALUE)
        team_a = safe_str(turn.get("team_a_name", ""), "Aチーム")
        team_b = safe_str(turn.get("team_b_name", ""), "Bチーム")
        label = f"{match_date} | {match_title} | {team_a} vs {team_b}"
        index[match_id] = {
            "match_id": match_id,
            "match_date": parse_date_text_or_today(match_date),
            "match_title": match_title,
            "team_a_name": team_a,
            "team_b_name": team_b,
            "label": label,
        }
    return index


def parse_events_json(value: object) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    text = safe_str(value)
    if text == "":
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return []
    return []


def get_team_label(code: str) -> str:
    team_a = safe_str(st.session_state.get("team_a_name", ""), "").strip() or "Aチーム"
    team_b = safe_str(st.session_state.get("team_b_name", ""), "").strip() or "Bチーム"
    return team_a if code == "A" else team_b


def team_name_from_code(code: str, team_a_name: str, team_b_name: str) -> str:
    return team_a_name if code == "A" else team_b_name


def normalize_team_code(value: object, team_a_name: str, team_b_name: str, default: str = "A") -> str:
    text = safe_str(value, default).strip()
    if text in {"A", "B"}:
        return text
    if text == team_a_name:
        return "A"
    if text == team_b_name:
        return "B"
    return default


def initialize_state() -> None:
    if "turns" not in st.session_state:
        st.session_state.turns = []
    if "gsheets_bootstrapped" not in st.session_state:
        st.session_state.gsheets_bootstrapped = False
    if "last_sync_ok" not in st.session_state:
        st.session_state.last_sync_ok = None
    if "last_sync_message" not in st.session_state:
        st.session_state.last_sync_message = ""


def initialize_input_state() -> None:
    defaults = {
        "match_date": date.today(),
        "match_title": "練習試合",
        "team_a_name": "Aチーム",
        "team_b_name": "Bチーム",
        "input_by": UNKNOWN_VALUE,
        "offense_start_team": "A",
        "team_a_member": MEMBER_OPTIONS[0],
        "team_b_member": MEMBER_OPTIONS[2],
        "team_a_force": FORCE_OPTIONS[0],
        "team_b_force": FORCE_OPTIONS[0],
        "team_a_wind": WIND_OPTIONS[0],
        "team_b_wind": WIND_OPTIONS[0],
        "team_a_defense_type": DEFENSE_TYPE_OPTIONS[0],
        "team_b_defense_type": DEFENSE_TYPE_OPTIONS[0],
        "drop_count": 0,
        "score_pattern": SCORE_PATTERN_OPTIONS[0],
        "score_from_player": UNKNOWN_VALUE,
        "score_to_player": UNKNOWN_VALUE,
        "match_input_mode": "",
        "selected_match_id": "",
        "last_selected_match_id": "",
        "pending_turn_input_reset": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_turn_inputs() -> None:
    st.session_state.offense_start_team = "A"
    st.session_state.team_a_member = MEMBER_OPTIONS[0]
    st.session_state.team_b_member = MEMBER_OPTIONS[2]
    st.session_state.team_a_force = FORCE_OPTIONS[0]
    st.session_state.team_b_force = FORCE_OPTIONS[0]
    st.session_state.team_a_wind = WIND_OPTIONS[0]
    st.session_state.team_b_wind = WIND_OPTIONS[0]
    st.session_state.team_a_defense_type = DEFENSE_TYPE_OPTIONS[0]
    st.session_state.team_b_defense_type = DEFENSE_TYPE_OPTIONS[0]
    st.session_state.drop_count = 0
    st.session_state.score_pattern = SCORE_PATTERN_OPTIONS[0]
    st.session_state.score_from_player = UNKNOWN_VALUE
    st.session_state.score_to_player = UNKNOWN_VALUE

    for key in list(st.session_state.keys()):
        if key.startswith("event_"):
            del st.session_state[key]


def schedule_turn_input_reset() -> None:
    st.session_state.pending_turn_input_reset = True


def get_gsheets_connection():
    try:
        gsheets_module = importlib.import_module("streamlit_gsheets")
        gsheets_connection_class = getattr(gsheets_module, "GSheetsConnection")
        return st.connection("gsheets", type=gsheets_connection_class)
    except Exception:
        return None


def load_turns_from_gsheets() -> tuple[bool, str]:
    conn = get_gsheets_connection()
    if conn is None:
        return False, "Google Sheets接続が見つかりません。設定または依存パッケージを確認してください。"

    try:
        loaded_df = conn.read(worksheet=GSHEETS_WORKSHEET, ttl=0)
        if loaded_df is None or loaded_df.empty:
            st.session_state.turns = []
            return True, "Google Sheetsは空です。"

        loaded_df = loaded_df.loc[:, ~loaded_df.columns.astype(str).str.startswith("Unnamed:")]
        st.session_state.turns = dataframe_to_turns(loaded_df)
        return True, f"Google Sheets（{GSHEETS_WORKSHEET}）を読み込みました。"
    except Exception as e:
        return False, f"Google Sheets読込に失敗しました: {e}"


def save_turns_to_gsheets(df: pd.DataFrame) -> tuple[bool, str]:
    conn = get_gsheets_connection()
    if conn is None:
        return False, "Google Sheets接続が見つかりません。設定または依存パッケージを確認してください。"

    try:
        # turn_log: turn_idでUPSERT
        existing_turn_df = conn.read(worksheet=GSHEETS_WORKSHEET, ttl=0)
        if existing_turn_df is None or existing_turn_df.empty:
            merged_turn_df = df.copy()
        else:
            existing_turn_df = existing_turn_df.loc[:, ~existing_turn_df.columns.astype(str).str.startswith("Unnamed:")]
            merged_turn_df = pd.concat([existing_turn_df, df], ignore_index=True)
            if "turn_id" in merged_turn_df.columns:
                merged_turn_df = merged_turn_df.drop_duplicates(subset=["turn_id"], keep="last")

        conn.update(worksheet=GSHEETS_WORKSHEET, data=merged_turn_df)

        # event_log: 追記中心（同一turn_idは置換し、event_id重複は最新を採用）
        event_df = build_event_export_dataframe(st.session_state.turns)
        existing_event_df = conn.read(worksheet=GSHEETS_EVENTS_WORKSHEET, ttl=0)
        if existing_event_df is None or existing_event_df.empty:
            merged_event_df = event_df.copy()
        else:
            existing_event_df = existing_event_df.loc[:, ~existing_event_df.columns.astype(str).str.startswith("Unnamed:")]
            if "turn_id" in existing_event_df.columns and "turn_id" in event_df.columns:
                edited_turn_ids = set(event_df["turn_id"].astype(str).tolist())
                existing_event_df = existing_event_df[~existing_event_df["turn_id"].astype(str).isin(edited_turn_ids)]

            merged_event_df = pd.concat([existing_event_df, event_df], ignore_index=True)
            if "event_id" in merged_event_df.columns:
                merged_event_df = merged_event_df.drop_duplicates(subset=["event_id"], keep="last")

        conn.update(worksheet=GSHEETS_EVENTS_WORKSHEET, data=merged_event_df)
        return True, f"Google Sheets（{GSHEETS_WORKSHEET}:UPSERT / {GSHEETS_EVENTS_WORKSHEET}:APPEND中心）へ保存しました。"
    except Exception as e:
        return False, f"Google Sheets保存に失敗しました: {e}"


def sync_turns_to_gsheets_from_state() -> tuple[bool, str]:
    df = turns_to_dataframe(st.session_state.turns)
    ok, msg = save_turns_to_gsheets(df)
    st.session_state.last_sync_ok = ok
    st.session_state.last_sync_message = msg
    return ok, msg


def build_event_export_dataframe(turns: list[dict]) -> pd.DataFrame:
    columns = [
        "event_id",
        "match_id",
        "turn_id",
        "turn_no",
        "match_date",
        "match_title",
        "team_a_name",
        "team_b_name",
        "created_at",
        "updated_at",
        "input_by",
        "event_type",
        "team",
        "wind_direction",
        "defense_type",
        "force",
        "drop_type",
        "shot_type",
        "throw_category",
        "throw_detail",
        "place_side",
        "place_end",
        "from_player",
        "to_player",
        "defender_name",
        "nice_defense_type",
    ]

    rows: list[dict] = []
    for turn in turns:
        events = turn.get("drop_events", [])
        team_a_name = safe_str(turn.get("team_a_name", "Aチーム"), "Aチーム")
        team_b_name = safe_str(turn.get("team_b_name", "Bチーム"), "Bチーム")
        team_a_wind = safe_str(turn.get("team_a_wind", ""))
        team_b_wind = safe_str(turn.get("team_b_wind", ""))
        match_id = normalize_unknown(turn.get("match_id", ""))
        turn_id = normalize_unknown(turn.get("turn_id", ""))
        created_at = normalize_unknown(turn.get("created_at", ""))
        updated_at = normalize_unknown(turn.get("updated_at", ""))
        input_by = normalize_unknown(turn.get("input_by", ""))

        turn_no = safe_int(turn.get("turn_no", 0), 0)

        # 得点イベント（1ターン=1得点）
        point_winner_code = normalize_team_code(turn.get("point_winner", "A"), team_a_name, team_b_name, "A")
        score_team_name = team_name_from_code(point_winner_code, team_a_name, team_b_name)
        score_wind = team_a_wind if point_winner_code == "A" else team_b_wind
        rows.append(
            {
                "event_id": f"{turn_id}-score",
                "match_id": match_id,
                "turn_id": turn_id,
                "turn_no": turn_no,
                "match_date": safe_str(turn.get("match_date", "")),
                "match_title": safe_str(turn.get("match_title", "")),
                "team_a_name": team_a_name,
                "team_b_name": team_b_name,
                "created_at": created_at,
                "updated_at": updated_at,
                "input_by": input_by,
                "event_type": "得点",
                "team": score_team_name,
                "wind_direction": score_wind,
                "defense_type": "",
                "force": "",
                "drop_type": "",
                "shot_type": "",
                "throw_category": "",
                "throw_detail": "",
                "place_side": "",
                "place_end": "",
                "from_player": safe_str(turn.get("score_from_player", "")),
                "to_player": safe_str(turn.get("score_to_player", "")),
                "defender_name": "",
                "nice_defense_type": "",
            }
        )

        for idx, event in enumerate(events, start=1):
            event_type = safe_str(event.get("cause", ""))
            mistake_team_code = normalize_team_code(
                event.get("mistake_team", ""),
                team_a_name,
                team_b_name,
                "",
            )

            event_team_code = ""
            if event_type in {"ミス", "ナイスディフェンス"}:
                event_team_code = mistake_team_code
            elif event_type == "シュート":
                event_team_code = normalize_team_code(
                    event.get("event_team", ""),
                    team_a_name,
                    team_b_name,
                    "",
                )

            if event_team_code == "A":
                defense_type = safe_str(turn.get("team_a_defense_type", ""))
                force = safe_str(turn.get("team_a_force", ""))
                wind_direction = team_a_wind
            elif event_team_code == "B":
                defense_type = safe_str(turn.get("team_b_defense_type", ""))
                force = safe_str(turn.get("team_b_force", ""))
                wind_direction = team_b_wind
            else:
                defense_type = ""
                force = ""
                wind_direction = ""

            rows.append(
                {
                    "event_id": f"{turn_id}-event-{idx}",
                    "match_id": match_id,
                    "turn_id": turn_id,
                    "turn_no": turn_no,
                    "match_date": safe_str(turn.get("match_date", "")),
                    "match_title": safe_str(turn.get("match_title", "")),
                    "team_a_name": team_a_name,
                    "team_b_name": team_b_name,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "input_by": input_by,
                    "event_type": event_type,
                    "team": team_name_from_code(event_team_code, team_a_name, team_b_name)
                    if event_team_code in {"A", "B"}
                    else "",
                    "wind_direction": wind_direction,
                    "defense_type": defense_type,
                    "force": force,
                    "drop_type": safe_str(event.get("drop_type", "")),
                    "shot_type": safe_str(event.get("shot_type", "")),
                    "throw_category": safe_str(event.get("throw_category", "")),
                    "throw_detail": safe_str(event.get("throw_detail", "")),
                    "place_side": safe_str(event.get("place_side", "")),
                    "place_end": safe_str(event.get("place_end", "")),
                    "from_player": safe_str(event.get("from_player", "")),
                    "to_player": safe_str(event.get("to_player", "")),
                    "defender_name": safe_str(event.get("defender_name", "")),
                    "nice_defense_type": safe_str(event.get("nice_defense_type", "")),
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def dataframe_to_turns(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    records: list[dict] = []
    for _, row in df.iterrows():
        events = []
        if "drop_events_json" in df.columns:
            events = parse_events_json(row.get("drop_events_json", ""))
        else:
            # 旧フォーマット互換
            old_happened = parse_bool(row.get("drop_happened", False))
            if old_happened:
                events = [
                    {
                        "cause": "ミス",
                        "drop_type": safe_str(row.get("drop_type", "")),
                        "shot_type": "",
                        "throw_category": "",
                        "throw_detail": "",
                        "place_side": "",
                        "place_end": "",
                        "mistake_team": safe_str(row.get("mistake_team", "")),
                        "event_team": "",
                        "from_player": safe_str(row.get("from_player", "")),
                        "to_player": safe_str(row.get("to_player", "")),
                        "defender_name": "",
                        "nice_defense_type": "",
                    }
                ]

        records.append(
            {
                "turn_no": int(row.get("turn_no", len(records) + 1)),
                "match_id": normalize_unknown(
                    row.get(
                        "match_id",
                        build_match_id(
                            row.get("match_date", ""),
                            safe_str(row.get("match_title", "練習試合"), "練習試合"),
                            safe_str(row.get("team_a_name", "Aチーム"), "Aチーム"),
                            safe_str(row.get("team_b_name", "Bチーム"), "Bチーム"),
                        ),
                    )
                ),
                "turn_id": safe_str(row.get("turn_id", "")),
                "match_date": safe_str(row.get("match_date", "")),
                "match_title": safe_str(row.get("match_title", "練習試合"), "練習試合"),
                "team_a_name": safe_str(row.get("team_a_name", "Aチーム"), "Aチーム"),
                "team_b_name": safe_str(row.get("team_b_name", "Bチーム"), "Bチーム"),
                "offense_start_team": normalize_team_code(
                    row.get("offense_start_team", "A"),
                    safe_str(row.get("team_a_name", "Aチーム"), "Aチーム"),
                    safe_str(row.get("team_b_name", "Bチーム"), "Bチーム"),
                    "A",
                ),
                "point_winner": normalize_team_code(
                    row.get("point_winner", "A"),
                    safe_str(row.get("team_a_name", "Aチーム"), "Aチーム"),
                    safe_str(row.get("team_b_name", "Bチーム"), "Bチーム"),
                    "A",
                ),
                "team_a_member": safe_str(
                    row.get(
                        "team_a_member",
                        row.get(
                            "offense_lineup" if safe_str(row.get("offense_start_team", "A"), "A") == "A" else "defense_lineup",
                            "Oセット",
                        ),
                    ),
                    "Oセット",
                ),
                "team_b_member": safe_str(
                    row.get(
                        "team_b_member",
                        row.get(
                            "offense_lineup" if safe_str(row.get("offense_start_team", "A"), "A") == "B" else "defense_lineup",
                            "Dセット",
                        ),
                    ),
                    "Dセット",
                ),
                "team_a_force": safe_str(row.get("team_a_force", row.get("force", "サイド")), "サイド"),
                "team_b_force": safe_str(row.get("team_b_force", row.get("force", "サイド")), "サイド"),
                "team_a_wind": safe_str(row.get("team_a_wind", WIND_OPTIONS[0]), WIND_OPTIONS[0]),
                "team_b_wind": safe_str(row.get("team_b_wind", WIND_OPTIONS[0]), WIND_OPTIONS[0]),
                "team_a_defense_type": safe_str(
                    row.get("team_a_defense_type", row.get("defense_type", "マンツー")), "マンツー"
                ),
                "team_b_defense_type": safe_str(
                    row.get("team_b_defense_type", row.get("defense_type", "マンツー")), "マンツー"
                ),
                "score_pattern": safe_str(row.get("score_pattern", "")),
                "score_from_player": safe_str(row.get("score_from_player", "")),
                "score_to_player": safe_str(row.get("score_to_player", "")),
                "input_by": normalize_unknown(row.get("input_by", "")),
                "created_at": normalize_unknown(row.get("created_at", now_iso())),
                "updated_at": normalize_unknown(row.get("updated_at", now_iso())),
                "drop_count": len(events),
                "drop_events": events,
                "drop_events_json": json.dumps(events, ensure_ascii=False),
                "is_break": parse_bool(row.get("is_break", False)),
            }
        )

    for record in records:
        if safe_str(record.get("turn_id", "")).strip() == "":
            record["turn_id"] = build_turn_id(record["match_id"], safe_int(record.get("turn_no", 1), 1))

    return records


def turns_to_dataframe(turns: list[dict]) -> pd.DataFrame:
    if not turns:
        return pd.DataFrame(
            columns=[
                "turn_no",
                "match_id",
                "turn_id",
                "match_date",
                "match_title",
                "team_a_name",
                "team_b_name",
                "created_at",
                "updated_at",
                "input_by",
                "offense_start_team",
                "offense_start_team_name",
                "point_winner",
                "point_winner_name",
                "team_a_member",
                "team_b_member",
                "team_a_force",
                "team_b_force",
                "team_a_wind",
                "team_b_wind",
                "team_a_defense_type",
                "team_b_defense_type",
                "score_pattern",
                "score_from_player",
                "score_to_player",
                "drop_count",
                "drop_events_json",
                "is_break",
            ]
        )

    rows: list[dict] = []
    for i, turn in enumerate(turns, start=1):
        events = turn.get("drop_events", [])
        turn_no = safe_int(turn.get("turn_no", i), i)
        match_id = normalize_unknown(
            turn.get(
                "match_id",
                build_match_id(
                    turn.get("match_date", ""),
                    turn.get("match_title", "練習試合"),
                    turn.get("team_a_name", "Aチーム"),
                    turn.get("team_b_name", "Bチーム"),
                ),
            )
        )
        created_at = normalize_unknown(turn.get("created_at", now_iso()))
        updated_at = normalize_unknown(turn.get("updated_at", created_at))
        rows.append(
            {
                "turn_no": turn_no,
                "match_id": match_id,
                "turn_id": safe_str(turn.get("turn_id", ""), "") or build_turn_id(match_id, turn_no),
                "match_date": turn.get("match_date", ""),
                "match_title": turn.get("match_title", "練習試合"),
                "team_a_name": turn.get("team_a_name", "Aチーム"),
                "team_b_name": turn.get("team_b_name", "Bチーム"),
                "created_at": created_at,
                "updated_at": updated_at,
                "input_by": normalize_unknown(turn.get("input_by", "")),
                "offense_start_team": turn.get("offense_start_team", "A"),
                "offense_start_team_name": team_name_from_code(
                    turn.get("offense_start_team", "A"),
                    turn.get("team_a_name", "Aチーム"),
                    turn.get("team_b_name", "Bチーム"),
                ),
                "point_winner": turn.get("point_winner", "A"),
                "point_winner_name": team_name_from_code(
                    turn.get("point_winner", "A"),
                    turn.get("team_a_name", "Aチーム"),
                    turn.get("team_b_name", "Bチーム"),
                ),
                "team_a_member": turn.get("team_a_member", "Oセット"),
                "team_b_member": turn.get("team_b_member", "Dセット"),
                "team_a_force": turn.get("team_a_force", "サイド"),
                "team_b_force": turn.get("team_b_force", "サイド"),
                "team_a_wind": turn.get("team_a_wind", WIND_OPTIONS[0]),
                "team_b_wind": turn.get("team_b_wind", WIND_OPTIONS[0]),
                "team_a_defense_type": turn.get("team_a_defense_type", "マンツー"),
                "team_b_defense_type": turn.get("team_b_defense_type", "マンツー"),
                "score_pattern": turn.get("score_pattern", ""),
                "score_from_player": turn.get("score_from_player", ""),
                "score_to_player": turn.get("score_to_player", ""),
                "drop_count": len(events),
                "drop_events_json": json.dumps(events, ensure_ascii=False),
                "is_break": turn.get("is_break", False),
            }
        )

    return pd.DataFrame(rows)


def add_turn(
    point_winner: str,
    offense_start_team: str,
    team_a_member: str,
    team_b_member: str,
    team_a_force: str,
    team_b_force: str,
    team_a_wind: str,
    team_b_wind: str,
    team_a_defense_type: str,
    team_b_defense_type: str,
    score_pattern: str,
    score_from_player: str,
    score_to_player: str,
    match_date: object,
    match_title: str,
    team_a_name: str,
    team_b_name: str,
    input_by: str,
    drop_events: list[dict],
    match_id_override: str = "",
) -> None:
    created_at = now_iso()
    safe_match_title = normalize_unknown(match_title)
    safe_team_a_name = normalize_unknown(team_a_name)
    safe_team_b_name = normalize_unknown(team_b_name)
    match_id = normalize_unknown(match_id_override)
    if match_id == UNKNOWN_VALUE:
        match_id = build_match_id(match_date, safe_match_title, safe_team_a_name, safe_team_b_name)

    clean_events: list[dict] = []
    for event in drop_events:
        cause = safe_str(event.get("cause", ""))
        clean_event = {
            "cause": cause,
            "drop_type": normalize_unknown(event.get("drop_type", "")),
            "shot_type": normalize_unknown(event.get("shot_type", "")),
            "throw_category": normalize_unknown(event.get("throw_category", "")),
            "throw_detail": normalize_unknown(event.get("throw_detail", "")),
            "place_side": normalize_unknown(event.get("place_side", "")),
            "place_end": normalize_unknown(event.get("place_end", "")),
            "mistake_team": safe_str(event.get("mistake_team", "")),
            "event_team": safe_str(event.get("event_team", "")),
            "from_player": normalize_unknown(event.get("from_player", "")),
            "to_player": normalize_unknown(event.get("to_player", "")),
            "defender_name": normalize_unknown(event.get("defender_name", "")),
            "nice_defense_type": normalize_unknown(event.get("nice_defense_type", "")),
        }

        if cause == "ナイスディフェンス":
            clean_event["drop_type"] = UNKNOWN_VALUE
            clean_event["shot_type"] = UNKNOWN_VALUE
            clean_event["place_side"] = UNKNOWN_VALUE
            clean_event["place_end"] = UNKNOWN_VALUE
            clean_event["from_player"] = UNKNOWN_VALUE
            clean_event["to_player"] = UNKNOWN_VALUE
            clean_event["event_team"] = UNKNOWN_VALUE
        elif cause == "シュート":
            clean_event["drop_type"] = UNKNOWN_VALUE
            clean_event["mistake_team"] = UNKNOWN_VALUE
            clean_event["defender_name"] = UNKNOWN_VALUE
            clean_event["nice_defense_type"] = UNKNOWN_VALUE
        else:
            clean_event["shot_type"] = UNKNOWN_VALUE
            clean_event["event_team"] = UNKNOWN_VALUE
            clean_event["defender_name"] = UNKNOWN_VALUE
            clean_event["nice_defense_type"] = UNKNOWN_VALUE

        clean_events.append(clean_event)

    existing_turn_numbers = [
        safe_int(t.get("turn_no", 0), 0)
        for t in st.session_state.turns
        if normalize_unknown(t.get("match_id", "")) == match_id
    ]
    turn_no = (max(existing_turn_numbers) + 1) if existing_turn_numbers else 1
    new_turn = {
        "turn_no": turn_no,
        "match_id": match_id,
        "turn_id": build_turn_id(match_id, turn_no),
        "created_at": created_at,
        "updated_at": created_at,
        "input_by": normalize_unknown(input_by),
        "match_date": str(match_date) if match_date is not None else "",
        "match_title": safe_match_title,
        "team_a_name": safe_team_a_name,
        "team_b_name": safe_team_b_name,
        "offense_start_team": offense_start_team,
        "point_winner": point_winner,
        "team_a_member": team_a_member,
        "team_b_member": team_b_member,
        "team_a_force": team_a_force,
        "team_b_force": team_b_force,
        "team_a_wind": team_a_wind,
        "team_b_wind": team_b_wind,
        "team_a_defense_type": team_a_defense_type,
        "team_b_defense_type": team_b_defense_type,
        "score_pattern": normalize_unknown(score_pattern),
        "score_from_player": normalize_unknown(score_from_player),
        "score_to_player": normalize_unknown(score_to_player),
        "drop_count": len(clean_events),
        "drop_events": clean_events,
        "is_break": point_winner != offense_start_team,
    }
    st.session_state.turns.append(new_turn)


def validate_turn_input(score_to_player: str, drop_events: list[dict]) -> list[str]:
    # 空欄は保存時に「-」へ統一する運用
    _ = normalize_unknown(score_to_player)
    for event in drop_events:
        for key in [
            "drop_type",
            "shot_type",
            "throw_category",
            "throw_detail",
            "place_side",
            "place_end",
            "from_player",
            "to_player",
            "defender_name",
            "nice_defense_type",
            "mistake_team",
            "event_team",
        ]:
            event[key] = normalize_unknown(event.get(key, ""))

    return []


def collect_turn_events(drop_count: int) -> list[dict]:
    events: list[dict] = []
    for i in range(drop_count):
        event_type = safe_str(st.session_state.get(f"event_{i}_cause", "ミス"), "ミス")
        event_team = safe_str(st.session_state.get(f"event_{i}_drop_team", "A"), "A")
        if event_type == "ナイスディフェンス":
            throw_category = safe_str(
                st.session_state.get(f"event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            throw_detail_options = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
            events.append(
                {
                    "cause": event_type,
                    "drop_type": "",
                    "shot_type": "",
                    "throw_category": throw_category,
                    "throw_detail": safe_str(
                        st.session_state.get(f"event_{i}_throw_detail", throw_detail_options[0]),
                        throw_detail_options[0],
                    ),
                    "place_side": "",
                    "place_end": "",
                    "mistake_team": event_team,
                    "event_team": "",
                    "from_player": "",
                    "to_player": "",
                    "defender_name": safe_str(st.session_state.get(f"event_{i}_defender_name", "")),
                    "nice_defense_type": safe_str(
                        st.session_state.get(f"event_{i}_nice_defense_type", NICE_DEFENSE_TYPE_OPTIONS[0]),
                        NICE_DEFENSE_TYPE_OPTIONS[0],
                    ),
                }
            )
        elif event_type == "シュート":
            events.append(
                {
                    "cause": "シュート",
                    "drop_type": "",
                    "shot_type": safe_str(
                        st.session_state.get(f"event_{i}_shot_type", SHOT_TYPE_OPTIONS[0]),
                        SHOT_TYPE_OPTIONS[0],
                    ),
                    "throw_category": "",
                    "throw_detail": "",
                    "place_side": safe_str(
                        st.session_state.get(f"event_{i}_place_side", PLACE_SIDE_OPTIONS[0]),
                        PLACE_SIDE_OPTIONS[0],
                    ),
                    "place_end": safe_str(
                        st.session_state.get(f"event_{i}_place_end", PLACE_END_OPTIONS[0]),
                        PLACE_END_OPTIONS[0],
                    ),
                    "mistake_team": "",
                    "event_team": event_team,
                    "from_player": safe_str(st.session_state.get(f"event_{i}_from_player", "")),
                    "to_player": safe_str(st.session_state.get(f"event_{i}_to_player", "")),
                    "defender_name": "",
                    "nice_defense_type": "",
                }
            )
        else:
            throw_category = safe_str(
                st.session_state.get(f"event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            throw_detail_options = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
            events.append(
                {
                    "cause": "ミス",
                    "drop_type": safe_str(st.session_state.get(f"event_{i}_drop_type", "")),
                    "shot_type": "",
                    "throw_category": throw_category,
                    "throw_detail": safe_str(
                        st.session_state.get(f"event_{i}_throw_detail", throw_detail_options[0]),
                        throw_detail_options[0],
                    ),
                    "place_side": safe_str(
                        st.session_state.get(f"event_{i}_place_side", PLACE_SIDE_OPTIONS[0]),
                        PLACE_SIDE_OPTIONS[0],
                    ),
                    "place_end": safe_str(
                        st.session_state.get(f"event_{i}_place_end", PLACE_END_OPTIONS[0]),
                        PLACE_END_OPTIONS[0],
                    ),
                    "mistake_team": event_team,
                    "event_team": "",
                    "from_player": safe_str(st.session_state.get(f"event_{i}_from_player", "")),
                    "to_player": safe_str(st.session_state.get(f"event_{i}_to_player", "")),
                    "defender_name": "",
                    "nice_defense_type": "",
                }
            )
    return events


def collect_edit_events(edit_drop_count: int) -> list[dict]:
    events: list[dict] = []
    for i in range(edit_drop_count):
        event_type = safe_str(st.session_state.get(f"edit_event_{i}_cause", "ミス"), "ミス")
        event_team = safe_str(st.session_state.get(f"edit_event_{i}_drop_team", "A"), "A")
        if event_type == "ナイスディフェンス":
            throw_category = safe_str(
                st.session_state.get(f"edit_event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            throw_detail_options = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
            events.append(
                {
                    "cause": event_type,
                    "drop_type": "",
                    "shot_type": "",
                    "throw_category": throw_category,
                    "throw_detail": safe_str(
                        st.session_state.get(f"edit_event_{i}_throw_detail", throw_detail_options[0]),
                        throw_detail_options[0],
                    ),
                    "place_side": "",
                    "place_end": "",
                    "mistake_team": event_team,
                    "event_team": "",
                    "from_player": "",
                    "to_player": "",
                    "defender_name": safe_str(st.session_state.get(f"edit_event_{i}_defender_name", "")),
                    "nice_defense_type": safe_str(
                        st.session_state.get(f"edit_event_{i}_nice_defense_type", NICE_DEFENSE_TYPE_OPTIONS[0]),
                        NICE_DEFENSE_TYPE_OPTIONS[0],
                    ),
                }
            )
        elif event_type == "シュート":
            events.append(
                {
                    "cause": "シュート",
                    "drop_type": "",
                    "shot_type": safe_str(
                        st.session_state.get(f"edit_event_{i}_shot_type", SHOT_TYPE_OPTIONS[0]),
                        SHOT_TYPE_OPTIONS[0],
                    ),
                    "throw_category": "",
                    "throw_detail": "",
                    "place_side": safe_str(
                        st.session_state.get(f"edit_event_{i}_place_side", PLACE_SIDE_OPTIONS[0]),
                        PLACE_SIDE_OPTIONS[0],
                    ),
                    "place_end": safe_str(
                        st.session_state.get(f"edit_event_{i}_place_end", PLACE_END_OPTIONS[0]),
                        PLACE_END_OPTIONS[0],
                    ),
                    "mistake_team": "",
                    "event_team": event_team,
                    "from_player": safe_str(st.session_state.get(f"edit_event_{i}_from_player", "")),
                    "to_player": safe_str(st.session_state.get(f"edit_event_{i}_to_player", "")),
                    "defender_name": "",
                    "nice_defense_type": "",
                }
            )
        else:
            throw_category = safe_str(
                st.session_state.get(f"edit_event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            throw_detail_options = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
            events.append(
                {
                    "cause": "ミス",
                    "drop_type": safe_str(st.session_state.get(f"edit_event_{i}_drop_type", "")),
                    "shot_type": "",
                    "throw_category": throw_category,
                    "throw_detail": safe_str(
                        st.session_state.get(f"edit_event_{i}_throw_detail", throw_detail_options[0]),
                        throw_detail_options[0],
                    ),
                    "place_side": safe_str(
                        st.session_state.get(f"edit_event_{i}_place_side", PLACE_SIDE_OPTIONS[0]),
                        PLACE_SIDE_OPTIONS[0],
                    ),
                    "place_end": safe_str(
                        st.session_state.get(f"edit_event_{i}_place_end", PLACE_END_OPTIONS[0]),
                        PLACE_END_OPTIONS[0],
                    ),
                    "mistake_team": event_team,
                    "event_team": "",
                    "from_player": safe_str(st.session_state.get(f"edit_event_{i}_from_player", "")),
                    "to_player": safe_str(st.session_state.get(f"edit_event_{i}_to_player", "")),
                    "defender_name": "",
                    "nice_defense_type": "",
                }
            )
    return events


def load_turn_into_edit_state(turn_index: int) -> None:
    turn = st.session_state.turns[turn_index]
    st.session_state.edit_target_turn_no = turn_index + 1
    raw_match_date = turn.get("match_date", "")
    if isinstance(raw_match_date, date):
        st.session_state.edit_match_date = raw_match_date
    else:
        raw_text = safe_str(raw_match_date, "").strip()
        try:
            st.session_state.edit_match_date = date.fromisoformat(raw_text) if raw_text else date.today()
        except ValueError:
            st.session_state.edit_match_date = date.today()
    st.session_state.edit_match_title = turn.get("match_title", "練習試合")
    st.session_state.edit_team_a_name = turn.get("team_a_name", "Aチーム")
    st.session_state.edit_team_b_name = turn.get("team_b_name", "Bチーム")
    st.session_state.edit_input_by = turn.get("input_by", UNKNOWN_VALUE)
    st.session_state.edit_offense_start_team = turn.get("offense_start_team", "A")
    st.session_state.edit_point_winner = turn.get("point_winner", "A")
    st.session_state.edit_team_a_member = turn.get("team_a_member", MEMBER_OPTIONS[0])
    st.session_state.edit_team_b_member = turn.get("team_b_member", MEMBER_OPTIONS[2])
    st.session_state.edit_team_a_force = turn.get("team_a_force", FORCE_OPTIONS[0])
    st.session_state.edit_team_b_force = turn.get("team_b_force", FORCE_OPTIONS[0])
    st.session_state.edit_team_a_wind = turn.get("team_a_wind", WIND_OPTIONS[0])
    st.session_state.edit_team_b_wind = turn.get("team_b_wind", WIND_OPTIONS[0])
    st.session_state.edit_team_a_defense_type = turn.get("team_a_defense_type", DEFENSE_TYPE_OPTIONS[0])
    st.session_state.edit_team_b_defense_type = turn.get("team_b_defense_type", DEFENSE_TYPE_OPTIONS[0])
    st.session_state.edit_score_pattern = turn.get("score_pattern", SCORE_PATTERN_OPTIONS[0])
    st.session_state.edit_score_from_player = turn.get("score_from_player", "")
    st.session_state.edit_score_to_player = turn.get("score_to_player", "")

    events = turn.get("drop_events", [])
    st.session_state.edit_drop_count = len(events)
    for i, event in enumerate(events):
        st.session_state[f"edit_event_{i}_cause"] = event.get("cause", "ミス")
        st.session_state[f"edit_event_{i}_drop_team"] = event.get("mistake_team") or event.get("event_team", "A")
        st.session_state[f"edit_event_{i}_drop_type"] = event.get("drop_type", "")
        st.session_state[f"edit_event_{i}_shot_type"] = event.get("shot_type", SHOT_TYPE_OPTIONS[0])
        st.session_state[f"edit_event_{i}_throw_category"] = event.get("throw_category", THROW_CATEGORY_OPTIONS[0])
        throw_category = st.session_state[f"edit_event_{i}_throw_category"]
        details = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
        st.session_state[f"edit_event_{i}_throw_detail"] = event.get("throw_detail", details[0])
        st.session_state[f"edit_event_{i}_place_side"] = event.get("place_side", PLACE_SIDE_OPTIONS[0])
        st.session_state[f"edit_event_{i}_place_end"] = event.get("place_end", PLACE_END_OPTIONS[0])
        st.session_state[f"edit_event_{i}_from_player"] = event.get("from_player", "")
        st.session_state[f"edit_event_{i}_to_player"] = event.get("to_player", "")
        st.session_state[f"edit_event_{i}_defender_name"] = event.get("defender_name", "")
        st.session_state[f"edit_event_{i}_nice_defense_type"] = event.get("nice_defense_type", NICE_DEFENSE_TYPE_OPTIONS[0])


def load_match_info_into_edit_state(match_id: str) -> None:
    target = None
    for turn in st.session_state.turns:
        if normalize_unknown(turn.get("match_id", "")) == normalize_unknown(match_id):
            target = turn
            break

    if target is None:
        return

    st.session_state.edit_match_target_id = normalize_unknown(match_id)
    st.session_state.edit_matchinfo_date = parse_date_text_or_today(target.get("match_date", ""))
    st.session_state.edit_matchinfo_title = safe_str(target.get("match_title", ""), UNKNOWN_VALUE)
    st.session_state.edit_matchinfo_team_a_name = safe_str(target.get("team_a_name", ""), "Aチーム")
    st.session_state.edit_matchinfo_team_b_name = safe_str(target.get("team_b_name", ""), "Bチーム")


def apply_match_info_to_match_id(match_id: str, match_date: object, match_title: str, team_a_name: str, team_b_name: str) -> int:
    target_id = normalize_unknown(match_id)
    updated_at = now_iso()
    updated = 0

    for i, turn in enumerate(st.session_state.turns):
        if normalize_unknown(turn.get("match_id", "")) != target_id:
            continue

        turn["match_date"] = str(match_date) if match_date is not None else ""
        turn["match_title"] = normalize_unknown(match_title)
        turn["team_a_name"] = normalize_unknown(team_a_name)
        turn["team_b_name"] = normalize_unknown(team_b_name)
        turn["updated_at"] = updated_at
        st.session_state.turns[i] = turn
        updated += 1

    return updated


def apply_edit_to_turn(turn_index: int) -> None:
    old_turn = st.session_state.turns[turn_index]
    old_turn_no = safe_int(old_turn.get("turn_no", turn_index + 1), turn_index + 1)
    old_match_id = normalize_unknown(old_turn.get("match_id", ""))
    old_match_title = normalize_unknown(old_turn.get("match_title", "練習試合"))
    old_team_a_name = normalize_unknown(old_turn.get("team_a_name", "Aチーム"))
    old_team_b_name = normalize_unknown(old_turn.get("team_b_name", "Bチーム"))
    old_match_date = safe_str(old_turn.get("match_date", ""), "")
    match_id = old_match_id if old_match_id != UNKNOWN_VALUE else build_match_id(
        old_match_date,
        old_match_title,
        old_team_a_name,
        old_team_b_name,
    )
    old_turn_id = safe_str(old_turn.get("turn_id", ""), "")
    updated_at = now_iso()
    updated_events = collect_edit_events(int(st.session_state.edit_drop_count))
    updated_turn = {
        "turn_no": old_turn_no,
        "match_id": match_id,
        "turn_id": old_turn_id if old_turn_id else build_turn_id(match_id, old_turn_no),
        "created_at": normalize_unknown(old_turn.get("created_at", updated_at)),
        "updated_at": updated_at,
        "input_by": normalize_unknown(st.session_state.get("edit_input_by", st.session_state.get("input_by", UNKNOWN_VALUE))),
        "match_date": old_match_date,
        "match_title": old_match_title,
        "team_a_name": old_team_a_name,
        "team_b_name": old_team_b_name,
        "offense_start_team": safe_str(st.session_state.edit_offense_start_team, "A"),
        "point_winner": safe_str(st.session_state.edit_point_winner, "A"),
        "team_a_member": safe_str(st.session_state.edit_team_a_member, MEMBER_OPTIONS[0]),
        "team_b_member": safe_str(st.session_state.edit_team_b_member, MEMBER_OPTIONS[2]),
        "team_a_force": safe_str(st.session_state.edit_team_a_force, FORCE_OPTIONS[0]),
        "team_b_force": safe_str(st.session_state.edit_team_b_force, FORCE_OPTIONS[0]),
        "team_a_wind": safe_str(st.session_state.edit_team_a_wind, WIND_OPTIONS[0]),
        "team_b_wind": safe_str(st.session_state.edit_team_b_wind, WIND_OPTIONS[0]),
        "team_a_defense_type": safe_str(st.session_state.edit_team_a_defense_type, DEFENSE_TYPE_OPTIONS[0]),
        "team_b_defense_type": safe_str(st.session_state.edit_team_b_defense_type, DEFENSE_TYPE_OPTIONS[0]),
        "score_pattern": normalize_unknown(st.session_state.edit_score_pattern),
        "score_from_player": normalize_unknown(st.session_state.edit_score_from_player),
        "score_to_player": normalize_unknown(st.session_state.edit_score_to_player),
        "drop_count": len(updated_events),
        "drop_events": updated_events,
        "is_break": safe_str(st.session_state.edit_point_winner, "A")
        != safe_str(st.session_state.edit_offense_start_team, "A"),
    }
    st.session_state.turns[turn_index] = updated_turn


def build_events_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in df.iterrows():
        events = parse_events_json(row.get("drop_events_json", ""))
        for event in events:
            rows.append(
                {
                    "turn_no": int(row["turn_no"]),
                    "event_type": safe_str(event.get("cause", "")),
                    "drop_type": safe_str(event.get("drop_type", "")),
                    "shot_type": safe_str(event.get("shot_type", "")),
                    "throw_category": safe_str(event.get("throw_category", "")),
                    "throw_detail": safe_str(event.get("throw_detail", "")),
                    "place_side": safe_str(event.get("place_side", "")),
                    "place_end": safe_str(event.get("place_end", "")),
                    "team": safe_str(event.get("mistake_team", "")),
                    "from_player": safe_str(event.get("from_player", "")),
                    "to_player": safe_str(event.get("to_player", "")),
                    "defender_name": safe_str(event.get("defender_name", "")),
                    "nice_defense_type": safe_str(event.get("nice_defense_type", "")),
                }
            )
    return pd.DataFrame(rows)


initialize_state()
initialize_input_state()

if not st.session_state.gsheets_bootstrapped:
    ok, msg = load_turns_from_gsheets()
    st.session_state.last_sync_ok = ok
    st.session_state.last_sync_message = msg
    st.session_state.gsheets_bootstrapped = True

# ウィジェットを描画する前にリセット予約を処理する
if st.session_state.pending_turn_input_reset:
    reset_turn_inputs()
    st.session_state.pending_turn_input_reset = False

match_index = build_match_index(st.session_state.turns)
match_ids = list(match_index.keys())
if not st.session_state.match_input_mode:
    st.session_state.match_input_mode = "既存試合に追記/編集" if match_ids else "新規試合作成"

if st.session_state.match_input_mode == "既存試合に追記/編集" and not match_ids:
    st.session_state.match_input_mode = "新規試合作成"

if match_ids and st.session_state.selected_match_id not in match_ids:
    st.session_state.selected_match_id = match_ids[0]

if (
    st.session_state.match_input_mode == "既存試合に追記/編集"
    and st.session_state.selected_match_id in match_index
):
    selected_match = match_index[st.session_state.selected_match_id]
    st.session_state.match_date = selected_match["match_date"]
    st.session_state.match_title = selected_match["match_title"]
    st.session_state.team_a_name = selected_match["team_a_name"]
    st.session_state.team_b_name = selected_match["team_b_name"]
    st.session_state.last_selected_match_id = st.session_state.selected_match_id

if st.session_state.match_input_mode == "既存試合に追記/編集" and st.session_state.selected_match_id in match_index:
    active_match_id = st.session_state.selected_match_id
else:
    active_match_id = build_match_id(
        st.session_state.match_date,
        st.session_state.match_title,
        st.session_state.team_a_name,
        st.session_state.team_b_name,
    )

active_turns = [
    t for t in st.session_state.turns if normalize_unknown(t.get("match_id", "")) == normalize_unknown(active_match_id)
]

st.markdown(
    """
    <style>
    .block-container {padding-top: 0.7rem; padding-left: 0.8rem; padding-right: 0.8rem;}
    div.stButton > button {
        width: 100%;
        min-height: 52px;
        font-size: 1rem;
        border-radius: 10px;
    }
    [data-testid="stHorizontalBlock"] {gap: 0.45rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.subheader("入力（スマホ最適化）")

if st.session_state.last_sync_ok is True and st.session_state.last_sync_message:
    st.caption(f"同期状態: {st.session_state.last_sync_message}")
elif st.session_state.last_sync_ok is False and st.session_state.last_sync_message:
    st.warning(st.session_state.last_sync_message)

with st.container(border=True):
    st.markdown("#### 1) 試合情報")
    st.radio(
        "入力対象",
        ["既存試合に追記/編集", "新規試合作成"],
        key="match_input_mode",
        horizontal=True,
    )
    if st.session_state.match_input_mode == "既存試合に追記/編集":
        if match_ids:
            st.selectbox(
                "対象試合",
                options=match_ids,
                key="selected_match_id",
                format_func=lambda mid: match_index[mid]["label"],
            )
        else:
            st.info("既存試合がないため、新規試合作成を選択してください。")

    lock_match_info = st.session_state.match_input_mode == "既存試合に追記/編集" and bool(match_ids)
    st.date_input("試合日", key="match_date", disabled=lock_match_info)
    st.text_input("試合タイトル", key="match_title", placeholder="例: 春季リーグ 第2節", disabled=lock_match_info)
    st.text_input("Aチーム名", key="team_a_name", placeholder="例: 東京アルティメット", disabled=lock_match_info)
    st.text_input("Bチーム名", key="team_b_name", placeholder="例: 京都アルティメット", disabled=lock_match_info)
    st.text_input("入力者", key="input_by", placeholder="例: nakajima（不明なら -）")

with st.container(border=True):
    st.markdown("#### 2) ターン基本情報")
    st.radio(
        "ターン開始時のオフェンスチーム",
        ["A", "B"],
        horizontal=True,
        key="offense_start_team",
        format_func=get_team_label,
    )
    st.markdown(f"**{get_team_label('A')}**")
    st.selectbox("メンバー", MEMBER_OPTIONS, key="team_a_member")
    st.selectbox(
        "ディフェンスタイプ（TO後）" if st.session_state.offense_start_team == "A" else "ディフェンスタイプ",
        DEFENSE_TYPE_OPTIONS,
        key="team_a_defense_type",
    )
    st.selectbox(
        "フォース（TO後）" if st.session_state.offense_start_team == "A" else "フォース",
        FORCE_OPTIONS,
        key="team_a_force",
    )
    st.selectbox("風向き", WIND_OPTIONS, key="team_a_wind")

    st.markdown(f"**{get_team_label('B')}**")
    st.selectbox("メンバー", MEMBER_OPTIONS, key="team_b_member")
    st.selectbox(
        "ディフェンスタイプ（TO後）" if st.session_state.offense_start_team == "B" else "ディフェンスタイプ",
        DEFENSE_TYPE_OPTIONS,
        key="team_b_defense_type",
    )
    st.selectbox(
        "フォース（TO後）" if st.session_state.offense_start_team == "B" else "フォース",
        FORCE_OPTIONS,
        key="team_b_force",
    )
    st.selectbox("風向き", WIND_OPTIONS, key="team_b_wind")

with st.container(border=True):
    st.markdown("#### 3) ターン内イベント")
    c_cnt = st.columns([1])[0]
    c_cnt.markdown(
        f"<div style='text-align:center;padding-top:0.7rem;'>件数: <b>{int(st.session_state.drop_count)}</b></div>",
        unsafe_allow_html=True,
    )

drop_count = int(st.session_state.drop_count)
for i in range(drop_count):
    with st.container(border=True):
        st.markdown(f"**イベント {i + 1}**")
        st.selectbox("イベント種別", EVENT_TYPE_OPTIONS, key=f"event_{i}_cause")
        st.radio(
            "該当チーム",
            ["A", "B"],
            horizontal=True,
            key=f"event_{i}_drop_team",
            format_func=get_team_label,
        )

        if st.session_state.get(f"event_{i}_cause", "ミス") == "ナイスディフェンス":
            st.selectbox("スローの種類", THROW_CATEGORY_OPTIONS, key=f"event_{i}_throw_category")
            selected_throw_category = safe_str(
                st.session_state.get(f"event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            st.selectbox(
                "スロー詳細",
                THROW_DETAIL_OPTIONS.get(selected_throw_category, ["-"]),
                key=f"event_{i}_throw_detail",
            )
            st.selectbox(
                "ナイスディフェンスの種類",
                NICE_DEFENSE_TYPE_OPTIONS,
                key=f"event_{i}_nice_defense_type",
            )
            st.text_input("ディフェンスした人", key=f"event_{i}_defender_name", placeholder="例: 高橋")
        elif st.session_state.get(f"event_{i}_cause", "ミス") == "シュート":
            st.selectbox("シュートの種類", SHOT_TYPE_OPTIONS, key=f"event_{i}_shot_type")
            st.selectbox("場所（左右）", PLACE_SIDE_OPTIONS, key=f"event_{i}_place_side")
            st.selectbox("場所（局面）", PLACE_END_OPTIONS, key=f"event_{i}_place_end")
            st.text_input("誰から（パサー）", key=f"event_{i}_from_player", placeholder="例: 田中")
            st.text_input("誰へ（シューター）", key=f"event_{i}_to_player", placeholder="例: 佐藤")
        else:
            st.selectbox("ミスの種類", DROP_TYPE_OPTIONS, key=f"event_{i}_drop_type")
            st.selectbox("スローの種類", THROW_CATEGORY_OPTIONS, key=f"event_{i}_throw_category")
            selected_throw_category = safe_str(
                st.session_state.get(f"event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            st.selectbox(
                "スロー詳細",
                THROW_DETAIL_OPTIONS.get(selected_throw_category, ["-"]),
                key=f"event_{i}_throw_detail",
            )
            st.selectbox("場所（左右）", PLACE_SIDE_OPTIONS, key=f"event_{i}_place_side")
            st.selectbox("場所（局面）", PLACE_END_OPTIONS, key=f"event_{i}_place_end")
            st.text_input("誰から（パサー）", key=f"event_{i}_from_player", placeholder="例: 田中")
            st.text_input("誰へ（レシーバー）", key=f"event_{i}_to_player", placeholder="例: 佐藤")

with st.container(border=True):
    event_btn_add, event_btn_del = st.columns(2)
    if event_btn_add.button("＋ イベント追加", key="add_event_bottom", use_container_width=True):
        st.session_state.drop_count = min(int(st.session_state.drop_count) + 1, 10)
        st.rerun()
    if event_btn_del.button("－ イベント削除", key="remove_event_bottom", use_container_width=True):
        st.session_state.drop_count = max(int(st.session_state.drop_count) - 1, 0)
        st.rerun()

with st.container(border=True):
    st.markdown("#### 4) 得点入力（1ターン=1得点）")
    st.selectbox("得点の取り方", SCORE_PATTERN_OPTIONS, key="score_pattern")
    score_pass_col1, score_pass_col2 = st.columns(2)
    score_pass_col1.text_input("誰から", key="score_from_player", placeholder="例: そう")
    score_pass_col2.text_input("誰へ（得点者）", key="score_to_player", placeholder="例: かない")
    col_a, col_b = st.columns(2)

if col_a.button(f"{get_team_label('A')} 得点", use_container_width=True, type="primary"):
    submit_events = collect_turn_events(drop_count)
    submit_errors = validate_turn_input(st.session_state.score_to_player, submit_events)
    if submit_errors:
        for err in submit_errors:
            st.error(err)
        st.stop()

    add_turn(
        point_winner="A",
        offense_start_team=st.session_state.offense_start_team,
        team_a_member=st.session_state.team_a_member,
        team_b_member=st.session_state.team_b_member,
        team_a_force=st.session_state.team_a_force,
        team_b_force=st.session_state.team_b_force,
        team_a_wind=st.session_state.team_a_wind,
        team_b_wind=st.session_state.team_b_wind,
        team_a_defense_type=st.session_state.team_a_defense_type,
        team_b_defense_type=st.session_state.team_b_defense_type,
        score_pattern=st.session_state.score_pattern,
        score_from_player=st.session_state.score_from_player,
        score_to_player=st.session_state.score_to_player,
        match_date=st.session_state.match_date,
        match_title=st.session_state.match_title,
        team_a_name=st.session_state.team_a_name,
        team_b_name=st.session_state.team_b_name,
        input_by=st.session_state.input_by,
        drop_events=submit_events,
        match_id_override=active_match_id if st.session_state.match_input_mode == "既存試合に追記/編集" else "",
    )
    sync_turns_to_gsheets_from_state()
    schedule_turn_input_reset()
    st.rerun()

if col_b.button(f"{get_team_label('B')} 得点", use_container_width=True, type="primary"):
    submit_events = collect_turn_events(drop_count)
    submit_errors = validate_turn_input(st.session_state.score_to_player, submit_events)
    if submit_errors:
        for err in submit_errors:
            st.error(err)
        st.stop()

    add_turn(
        point_winner="B",
        offense_start_team=st.session_state.offense_start_team,
        team_a_member=st.session_state.team_a_member,
        team_b_member=st.session_state.team_b_member,
        team_a_force=st.session_state.team_a_force,
        team_b_force=st.session_state.team_b_force,
        team_a_wind=st.session_state.team_a_wind,
        team_b_wind=st.session_state.team_b_wind,
        team_a_defense_type=st.session_state.team_a_defense_type,
        team_b_defense_type=st.session_state.team_b_defense_type,
        score_pattern=st.session_state.score_pattern,
        score_from_player=st.session_state.score_from_player,
        score_to_player=st.session_state.score_to_player,
        match_date=st.session_state.match_date,
        match_title=st.session_state.match_title,
        team_a_name=st.session_state.team_a_name,
        team_b_name=st.session_state.team_b_name,
        input_by=st.session_state.input_by,
        drop_events=submit_events,
        match_id_override=active_match_id if st.session_state.match_input_mode == "既存試合に追記/編集" else "",
    )
    sync_turns_to_gsheets_from_state()
    schedule_turn_input_reset()
    st.rerun()

with st.container(border=True):
    st.markdown("#### 5) 操作")
    op1 = st.columns(1)[0]
    if op1.button("直前ターンを削除", use_container_width=True):
        active_indices = [
            idx
            for idx, turn in enumerate(st.session_state.turns)
            if normalize_unknown(turn.get("match_id", "")) == normalize_unknown(active_match_id)
        ]
        if active_indices:
            del st.session_state.turns[active_indices[-1]]
            sync_turns_to_gsheets_from_state()
        st.rerun()

df = turns_to_dataframe(active_turns)

with st.expander("試合情報編集（同一match_idを一括更新）", expanded=False):
    if not active_turns:
        st.info("対象試合のデータがありません。")
    else:
        st.caption(f"対象match_id: {normalize_unknown(active_match_id)}")
        if st.button("現在の試合情報を編集欄に読み込む", use_container_width=True):
            load_match_info_into_edit_state(active_match_id)
            st.rerun()

        if "edit_match_target_id" in st.session_state and st.session_state.edit_match_target_id == normalize_unknown(active_match_id):
            with st.container(border=True):
                st.date_input("試合日", key="edit_matchinfo_date")
                st.text_input("試合タイトル", key="edit_matchinfo_title")
                st.text_input("Aチーム名", key="edit_matchinfo_team_a_name")
                st.text_input("Bチーム名", key="edit_matchinfo_team_b_name")

            if st.button("この試合情報を全ターンに反映", type="primary", use_container_width=True):
                updated_count = apply_match_info_to_match_id(
                    active_match_id,
                    st.session_state.edit_matchinfo_date,
                    st.session_state.edit_matchinfo_title,
                    st.session_state.edit_matchinfo_team_a_name,
                    st.session_state.edit_matchinfo_team_b_name,
                )
                if updated_count > 0:
                    sync_turns_to_gsheets_from_state()
                    st.success(f"{updated_count}ターンの試合情報を更新しました。")
                    st.rerun()
                else:
                    st.warning("更新対象がありませんでした。")

with st.expander("過去ターン修正", expanded=False):
    active_entries = [
        (idx, turn)
        for idx, turn in enumerate(st.session_state.turns)
        if normalize_unknown(turn.get("match_id", "")) == normalize_unknown(active_match_id)
    ]
    active_entries = sorted(active_entries, key=lambda x: safe_int(x[1].get("turn_no", 0), 0))

    if not active_entries:
        st.info("修正対象のターンがありません。")
    else:
        selected_turn_pos = st.selectbox(
            "修正するターン",
            options=list(range(len(active_entries))),
            format_func=lambda x: f"ターン {int(active_entries[x][1].get('turn_no', x + 1))}",
            key="edit_turn_selector",
        )
        selected_turn_index = active_entries[selected_turn_pos][0]
        selected_turn_no = safe_int(active_entries[selected_turn_pos][1].get("turn_no", selected_turn_pos + 1), selected_turn_pos + 1)

        edit_actions_col1, edit_actions_col2 = st.columns(2)
        if edit_actions_col1.button("選択ターンを編集欄に読み込む", use_container_width=True):
            load_turn_into_edit_state(selected_turn_index)
            st.rerun()

        if edit_actions_col2.button("選択ターンを削除", use_container_width=True):
            del st.session_state.turns[selected_turn_index]
            sync_turns_to_gsheets_from_state()
            st.success(f"ターン {selected_turn_no} を削除しました。")
            st.rerun()

        if "edit_target_turn_no" in st.session_state:
            st.markdown(f"**編集対象: ターン {st.session_state.edit_target_turn_no}**")
            with st.container(border=True):
                st.markdown("##### ターン情報")
                st.text_input("入力者", key="edit_input_by")

                st.radio("ターン開始時のオフェンスチーム", ["A", "B"], horizontal=True, key="edit_offense_start_team")
                st.radio("得点チーム", ["A", "B"], horizontal=True, key="edit_point_winner")

                st.markdown("##### チーム設定")
                st.selectbox("Aメンバー", MEMBER_OPTIONS, key="edit_team_a_member")
                st.selectbox("Aディフェンスタイプ", DEFENSE_TYPE_OPTIONS, key="edit_team_a_defense_type")
                st.selectbox("Aフォース", FORCE_OPTIONS, key="edit_team_a_force")
                st.selectbox("A風向き", WIND_OPTIONS, key="edit_team_a_wind")
                st.selectbox("Bメンバー", MEMBER_OPTIONS, key="edit_team_b_member")
                st.selectbox("Bディフェンスタイプ", DEFENSE_TYPE_OPTIONS, key="edit_team_b_defense_type")
                st.selectbox("Bフォース", FORCE_OPTIONS, key="edit_team_b_force")
                st.selectbox("B風向き", WIND_OPTIONS, key="edit_team_b_wind")

                st.markdown("##### 得点情報")
                st.selectbox("得点の取り方", SCORE_PATTERN_OPTIONS, key="edit_score_pattern")
                edit_score_cols = st.columns(2)
                edit_score_cols[0].text_input("誰から", key="edit_score_from_player")
                edit_score_cols[1].text_input("誰へ（得点者）", key="edit_score_to_player")

            with st.container(border=True):
                st.markdown("##### イベント修正")
                st.number_input("イベント数", min_value=0, max_value=20, step=1, key="edit_drop_count")
                for i in range(int(st.session_state.edit_drop_count)):
                    with st.container(border=True):
                        st.markdown(f"**編集イベント {i + 1}**")
                        st.selectbox("イベント種別", EVENT_TYPE_OPTIONS, key=f"edit_event_{i}_cause")
                        st.radio("該当チーム", ["A", "B"], horizontal=True, key=f"edit_event_{i}_drop_team")

                        if st.session_state.get(f"edit_event_{i}_cause", "ミス") == "ナイスディフェンス":
                            st.selectbox("スローの種類", THROW_CATEGORY_OPTIONS, key=f"edit_event_{i}_throw_category")
                            selected_throw_category = safe_str(
                                st.session_state.get(f"edit_event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                                THROW_CATEGORY_OPTIONS[0],
                            )
                            st.selectbox(
                                "スロー詳細",
                                THROW_DETAIL_OPTIONS.get(selected_throw_category, ["-"]),
                                key=f"edit_event_{i}_throw_detail",
                            )
                            st.selectbox("ナイスディフェンスの種類", NICE_DEFENSE_TYPE_OPTIONS, key=f"edit_event_{i}_nice_defense_type")
                            st.text_input("ディフェンスした人", key=f"edit_event_{i}_defender_name")
                        elif st.session_state.get(f"edit_event_{i}_cause", "ミス") == "シュート":
                            st.selectbox("シュートの種類", SHOT_TYPE_OPTIONS, key=f"edit_event_{i}_shot_type")
                            st.selectbox("場所（左右）", PLACE_SIDE_OPTIONS, key=f"edit_event_{i}_place_side")
                            st.selectbox("場所（局面）", PLACE_END_OPTIONS, key=f"edit_event_{i}_place_end")
                            st.text_input("誰から（パサー）", key=f"edit_event_{i}_from_player")
                            st.text_input("誰へ（シューター）", key=f"edit_event_{i}_to_player")
                        else:
                            st.selectbox("ミスの種類", DROP_TYPE_OPTIONS, key=f"edit_event_{i}_drop_type")
                            st.selectbox("スローの種類", THROW_CATEGORY_OPTIONS, key=f"edit_event_{i}_throw_category")
                            selected_throw_category = safe_str(
                                st.session_state.get(f"edit_event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                                THROW_CATEGORY_OPTIONS[0],
                            )
                            st.selectbox(
                                "スロー詳細",
                                THROW_DETAIL_OPTIONS.get(selected_throw_category, ["-"]),
                                key=f"edit_event_{i}_throw_detail",
                            )
                            st.selectbox("場所（左右）", PLACE_SIDE_OPTIONS, key=f"edit_event_{i}_place_side")
                            st.selectbox("場所（局面）", PLACE_END_OPTIONS, key=f"edit_event_{i}_place_end")
                            st.text_input("誰から（パサー）", key=f"edit_event_{i}_from_player")
                            st.text_input("誰へ（レシーバー）", key=f"edit_event_{i}_to_player")

            if st.button("このターンの修正を保存", type="primary", use_container_width=True):
                target_index = int(st.session_state.edit_target_turn_no) - 1
                if 0 <= target_index < len(st.session_state.turns):
                    edit_events = collect_edit_events(int(st.session_state.edit_drop_count))
                    edit_errors = validate_turn_input(st.session_state.edit_score_to_player, edit_events)
                    if edit_errors:
                        for err in edit_errors:
                            st.error(err)
                        st.stop()

                    apply_edit_to_turn(target_index)
                    sync_turns_to_gsheets_from_state()
                    st.success(f"ターン {target_index + 1} を更新しました。")
                    st.rerun()
                else:
                    st.error("編集対象ターンが見つかりません。再度読み込んでください。")

with st.expander("Google Sheets連携", expanded=False):
    st.caption("Streamlit公開URLからの入力は、得点/削除/リセット時に自動でGoogle Sheetsへ同期されます。")
    if st.button("Google Sheetsに保存", use_container_width=True):
        ok, msg = sync_turns_to_gsheets_from_state()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    if st.button("Google Sheetsから読み込む", use_container_width=True):
        ok, msg = load_turns_from_gsheets()
        st.session_state.last_sync_ok = ok
        st.session_state.last_sync_message = msg
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with st.expander("CSVエクスポート/インポート（任意）", expanded=False):

    st.download_button(
        label="CSVをダウンロード",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="ultimate_turn_log.csv",
        mime="text/csv",
        use_container_width=True,
    )

    uploaded_file = st.file_uploader("CSVを読み込み", type=["csv"])
    if uploaded_file is not None and st.button("読み込んだCSVを反映", use_container_width=True):
        loaded_df = pd.read_csv(uploaded_file)
        st.session_state.turns = dataframe_to_turns(loaded_df)
        st.rerun()

match_date_display = str(st.session_state.match_date) if st.session_state.match_date else ""
match_title_display = st.session_state.match_title.strip() or "練習試合"
team_a_name_display = st.session_state.team_a_name.strip() or "Aチーム"
team_b_name_display = st.session_state.team_b_name.strip() or "Bチーム"

title_prefix = f"{match_date_display} " if match_date_display else ""
st.title(f"{title_prefix}{match_title_display} - アルティメット記録・分析")

st.subheader("現在の入力プレビュー")
preview_events = collect_turn_events(drop_count)
preview_events_df = pd.DataFrame(preview_events)
if not preview_events_df.empty:
    preview_events_df["mistake_team"] = preview_events_df["mistake_team"].replace(
        {"A": team_a_name_display, "B": team_b_name_display}
    )

preview_col1, preview_col2 = st.columns(2)
preview_col1.write(f"- ターン開始オフェンス: {team_a_name_display if st.session_state.offense_start_team == 'A' else team_b_name_display}")
preview_col1.write(
    f"- {team_a_name_display}: メンバー={st.session_state.team_a_member} / D={st.session_state.team_a_defense_type}{'（TO後）' if st.session_state.offense_start_team == 'A' else ''} / フォース={st.session_state.team_a_force}"
)
preview_col1.write(f"- {team_a_name_display}: 風向き={st.session_state.team_a_wind}")
preview_col1.write(
    f"- {team_b_name_display}: メンバー={st.session_state.team_b_member} / D={st.session_state.team_b_defense_type}{'（TO後）' if st.session_state.offense_start_team == 'B' else ''} / フォース={st.session_state.team_b_force}"
)
preview_col1.write(f"- {team_b_name_display}: 風向き={st.session_state.team_b_wind}")
preview_col2.write(f"- イベント数: {drop_count}")
preview_col2.write(f"- 得点パターン: {st.session_state.score_pattern}")
score_route_preview = " -> ".join(
    [x for x in [st.session_state.score_from_player.strip(), st.session_state.score_to_player.strip()] if x]
)
preview_col2.write(f"- 得点ルート: {score_route_preview if score_route_preview else '未入力'}")

if preview_events_df.empty:
    st.caption("このターンのイベント入力はありません。")
else:
    st.dataframe(preview_events_df, use_container_width=True, hide_index=True)

if df.empty:
    st.info("画面上部の入力フォームで属性を選び、得点ボタンでターンを記録してください。")
    st.stop()

if "team_a_name" in df.columns:
    team_a_name_display = safe_str(df.iloc[-1].get("team_a_name", team_a_name_display), team_a_name_display)
if "team_b_name" in df.columns:
    team_b_name_display = safe_str(df.iloc[-1].get("team_b_name", team_b_name_display), team_b_name_display)
if "match_title" in df.columns:
    match_title_display = safe_str(df.iloc[-1].get("match_title", match_title_display), match_title_display)

if "match_date" in df.columns:
    match_date_display = safe_str(df.iloc[-1].get("match_date", match_date_display), match_date_display)

st.caption(f"試合: {match_date_display} {match_title_display}".strip())

df["A_score"] = (df["point_winner"] == "A").cumsum()
df["B_score"] = (df["point_winner"] == "B").cumsum()

latest = df.iloc[-1]
st.subheader("現在スコア")
score_col1, score_col2 = st.columns(2)
score_col1.metric(team_a_name_display, int(latest["A_score"]))
score_col2.metric(team_b_name_display, int(latest["B_score"]))

st.subheader("得点推移")
render_score_trend_chart(df, team_a_name_display, team_b_name_display)

st.subheader("ブレイク集計")
break_a = int(((df["point_winner"] == "A") & (df["is_break"])).sum())
break_b = int(((df["point_winner"] == "B") & (df["is_break"])).sum())
c1, c2 = st.columns(2)
c1.metric(f"{team_a_name_display}のブレイク数", break_a)
c2.metric(f"{team_b_name_display}のブレイク数", break_b)

st.subheader("得点パターン分析")
score_left, score_right = st.columns(2)
with score_left:
    if "score_pattern" in df.columns and not df["score_pattern"].dropna().empty:
        st.dataframe(
            df[df["score_pattern"].astype(str).str.strip() != ""]["score_pattern"]
            .value_counts()
            .rename_axis("score_pattern")
            .reset_index(name="count"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("得点パターン記録はまだありません。")

with score_right:
    if {"score_pattern", "score_from_player", "score_to_player"}.issubset(df.columns):
        fast_break_df = df[df["score_pattern"] == "TOからの速攻"].copy()
        fast_break_df = fast_break_df[
            (fast_break_df["score_from_player"].astype(str).str.strip() != "")
            & (fast_break_df["score_to_player"].astype(str).str.strip() != "")
        ]
        if fast_break_df.empty:
            st.write("TOからの速攻（誰→誰）の記録はまだありません。")
        else:
            fast_break_df["route"] = (
                fast_break_df["score_from_player"].astype(str).str.strip()
                + " -> "
                + fast_break_df["score_to_player"].astype(str).str.strip()
            )
            st.dataframe(
                fast_break_df["route"].value_counts().rename_axis("route").reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

st.subheader("キープ率")
keep_col1, keep_col2 = st.columns(2)

o_keep_mask_a = (df["offense_start_team"] == "A") 
o_keep_den_a = int(o_keep_mask_a.sum())
o_keep_num_a = int(((df["point_winner"] == "A") & o_keep_mask_a).sum())
o_keep_rate_a = (o_keep_num_a / o_keep_den_a) if o_keep_den_a > 0 else 0.0
keep_col1.metric(
    f"{team_a_name_display}",
    f"{o_keep_rate_a:.1%}",
    help=f"{o_keep_num_a} / {o_keep_den_a}",
)

o_keep_mask_b = (df["offense_start_team"] == "B") 
o_keep_den_b = int(o_keep_mask_b.sum())
o_keep_num_b = int(((df["point_winner"] == "B") & o_keep_mask_b).sum())
o_keep_rate_b = (o_keep_num_b / o_keep_den_b) if o_keep_den_b > 0 else 0.0
keep_col2.metric(
    f"{team_b_name_display}",
    f"{o_keep_rate_b:.1%}",
    help=f"{o_keep_num_b} / {o_keep_den_b}",
)


events_df = build_event_export_dataframe(active_turns)
st.subheader("ターンログ")
show_df = df[
    [
        "turn_no",
        "offense_start_team",
        "point_winner",
        "is_break",
        "team_a_member",
        "team_a_defense_type",
        "team_a_force",
        "team_a_wind",
        "team_b_member",
        "team_b_defense_type",
        "team_b_force",
        "score_pattern",
        "score_from_player",
        "score_to_player",
        "drop_count",
        "A_score",
        "B_score",
    ]
].copy()

show_df["offense_start_team"] = show_df["offense_start_team"].replace(
    {"A": team_a_name_display, "B": team_b_name_display}
)
show_df["point_winner"] = show_df["point_winner"].replace(
    {"A": team_a_name_display, "B": team_b_name_display}
)
show_df = show_df.rename(
    columns={
        "team_a_member": f"{team_a_name_display}_メンバー",
        "team_a_defense_type": f"{team_a_name_display}_Dタイプ",
        "team_a_force": f"{team_a_name_display}_フォース",
        "team_a_wind": f"{team_a_name_display}_風向き",
        "team_b_member": f"{team_b_name_display}_メンバー",
        "team_b_defense_type": f"{team_b_name_display}_Dタイプ",
        "team_b_force": f"{team_b_name_display}_フォース",
        "score_pattern": "得点の取り方",
        "score_from_player": "誰から",
        "score_to_player": "誰へ（得点者）",
    }
)
show_df = show_df.rename(columns={"A_score": team_a_name_display, "B_score": team_b_name_display})
st.dataframe(show_df, use_container_width=True, hide_index=True)

st.subheader("イベント詳細")
if events_df.empty:
    st.write("イベント詳細はありません。")
else:
    detail_df = events_df.copy()
    st.dataframe(detail_df, use_container_width=True, hide_index=True)
