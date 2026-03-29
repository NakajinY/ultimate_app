import json
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="アルティメット記録・分析", layout="wide")

OFFENSE_LINEUP_OPTIONS = ["Oセット", "下げO","-"]
DEFENSE_LINEUP_OPTIONS = ["Dセット", "上げマンD", "上げゾーンD","-"]
MEMBER_OPTIONS = OFFENSE_LINEUP_OPTIONS + DEFENSE_LINEUP_OPTIONS
FORCE_OPTIONS = ["サイド", "バック","FM"]
DEFENSE_TYPE_OPTIONS = ["マンツー", "ゾーン"]
EVENT_CAUSE_OPTIONS = ["ミス", "ナイスディフェンス"]
NICE_DEFENSE_TYPE_OPTIONS = ["ストブロ", "ミート狩り", "シュート狩り"]
DROP_TYPE_OPTIONS = [
    "キャッチミス",
    "スローミス",
]
THROW_CATEGORY_OPTIONS = ["ミート", "シュート", "ハンド展開"]
THROW_DETAIL_OPTIONS = {
    "ミート": ["インサイ", "オープン"],
    "シュート": ["シュート"],
    "ハンド展開": ["インサイド", "裏", "オープン", "かけ上がり"],
}
PLACE_SIDE_OPTIONS = ["ハメ側", "アンハメ側"]
PLACE_END_OPTIONS = ["エンド前", "Not"]

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "turn_log.csv"


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    if text.lower() == "nan":
        return default
    return text


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


def initialize_state() -> None:
    if "turns" not in st.session_state:
        st.session_state.turns = []


def initialize_input_state() -> None:
    defaults = {
        "match_title": "練習試合",
        "team_a_name": "Aチーム",
        "team_b_name": "Bチーム",
        "offense_start_team": "A",
        "team_a_member": MEMBER_OPTIONS[0],
        "team_b_member": MEMBER_OPTIONS[2],
        "team_a_force": FORCE_OPTIONS[0],
        "team_b_force": FORCE_OPTIONS[0],
        "team_a_defense_type": DEFENSE_TYPE_OPTIONS[0],
        "team_b_defense_type": DEFENSE_TYPE_OPTIONS[0],
        "drop_count": 0,
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
    st.session_state.team_a_defense_type = DEFENSE_TYPE_OPTIONS[0]
    st.session_state.team_b_defense_type = DEFENSE_TYPE_OPTIONS[0]
    st.session_state.drop_count = 0

    for key in list(st.session_state.keys()):
        if key.startswith("event_"):
            del st.session_state[key]


def schedule_turn_input_reset() -> None:
    st.session_state.pending_turn_input_reset = True


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
                        "throw_category": "",
                        "throw_detail": "",
                        "place_side": "",
                        "place_end": "",
                        "mistake_team": safe_str(row.get("mistake_team", "")),
                        "from_player": safe_str(row.get("from_player", "")),
                        "to_player": safe_str(row.get("to_player", "")),
                        "defender_name": "",
                        "nice_defense_type": "",
                    }
                ]

        records.append(
            {
                "turn_no": int(row.get("turn_no", len(records) + 1)),
                "match_title": safe_str(row.get("match_title", "練習試合"), "練習試合"),
                "team_a_name": safe_str(row.get("team_a_name", "Aチーム"), "Aチーム"),
                "team_b_name": safe_str(row.get("team_b_name", "Bチーム"), "Bチーム"),
                "offense_start_team": safe_str(row.get("offense_start_team", "A"), "A"),
                "point_winner": safe_str(row.get("point_winner", "A"), "A"),
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
                "team_a_defense_type": safe_str(
                    row.get("team_a_defense_type", row.get("defense_type", "マンツー")), "マンツー"
                ),
                "team_b_defense_type": safe_str(
                    row.get("team_b_defense_type", row.get("defense_type", "マンツー")), "マンツー"
                ),
                "drop_count": len(events),
                "drop_events": events,
                "drop_events_json": json.dumps(events, ensure_ascii=False),
                "is_break": parse_bool(row.get("is_break", False)),
            }
        )

    for i, record in enumerate(records, start=1):
        record["turn_no"] = i

    return records


def turns_to_dataframe(turns: list[dict]) -> pd.DataFrame:
    if not turns:
        return pd.DataFrame(
            columns=[
                "turn_no",
                "match_title",
                "team_a_name",
                "team_b_name",
                "offense_start_team",
                "point_winner",
                "team_a_member",
                "team_b_member",
                "team_a_force",
                "team_b_force",
                "team_a_defense_type",
                "team_b_defense_type",
                "drop_count",
                "drop_events_json",
                "is_break",
            ]
        )

    rows: list[dict] = []
    for i, turn in enumerate(turns, start=1):
        events = turn.get("drop_events", [])
        rows.append(
            {
                "turn_no": i,
                "match_title": turn.get("match_title", "練習試合"),
                "team_a_name": turn.get("team_a_name", "Aチーム"),
                "team_b_name": turn.get("team_b_name", "Bチーム"),
                "offense_start_team": turn.get("offense_start_team", "A"),
                "point_winner": turn.get("point_winner", "A"),
                "team_a_member": turn.get("team_a_member", "Oセット"),
                "team_b_member": turn.get("team_b_member", "Dセット"),
                "team_a_force": turn.get("team_a_force", "サイド"),
                "team_b_force": turn.get("team_b_force", "サイド"),
                "team_a_defense_type": turn.get("team_a_defense_type", "マンツー"),
                "team_b_defense_type": turn.get("team_b_defense_type", "マンツー"),
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
    team_a_defense_type: str,
    team_b_defense_type: str,
    match_title: str,
    team_a_name: str,
    team_b_name: str,
    drop_events: list[dict],
) -> None:
    clean_events: list[dict] = []
    for event in drop_events:
        cause = safe_str(event.get("cause", ""))
        clean_event = {
            "cause": cause,
            "drop_type": safe_str(event.get("drop_type", "")),
            "throw_category": safe_str(event.get("throw_category", "")),
            "throw_detail": safe_str(event.get("throw_detail", "")),
            "place_side": safe_str(event.get("place_side", "")),
            "place_end": safe_str(event.get("place_end", "")),
            "mistake_team": safe_str(event.get("mistake_team", "")),
            "from_player": safe_str(event.get("from_player", "")).strip(),
            "to_player": safe_str(event.get("to_player", "")).strip(),
            "defender_name": safe_str(event.get("defender_name", "")).strip(),
            "nice_defense_type": safe_str(event.get("nice_defense_type", "")).strip(),
        }

        if cause == "ナイスディフェンス":
            clean_event["drop_type"] = ""
            clean_event["place_side"] = ""
            clean_event["place_end"] = ""
            clean_event["from_player"] = ""
            clean_event["to_player"] = ""
        else:
            clean_event["defender_name"] = ""
            clean_event["nice_defense_type"] = ""

        clean_events.append(clean_event)

    new_turn = {
        "turn_no": len(st.session_state.turns) + 1,
        "match_title": match_title.strip() if match_title.strip() else "練習試合",
        "team_a_name": team_a_name.strip() if team_a_name.strip() else "Aチーム",
        "team_b_name": team_b_name.strip() if team_b_name.strip() else "Bチーム",
        "offense_start_team": offense_start_team,
        "point_winner": point_winner,
        "team_a_member": team_a_member,
        "team_b_member": team_b_member,
        "team_a_force": team_a_force,
        "team_b_force": team_b_force,
        "team_a_defense_type": team_a_defense_type,
        "team_b_defense_type": team_b_defense_type,
        "drop_count": len(clean_events),
        "drop_events": clean_events,
        "is_break": point_winner != offense_start_team,
    }
    st.session_state.turns.append(new_turn)


def collect_turn_events(drop_count: int) -> list[dict]:
    events: list[dict] = []
    for i in range(drop_count):
        cause = safe_str(st.session_state.get(f"event_{i}_cause", "ミス"), "ミス")
        drop_team = safe_str(st.session_state.get(f"event_{i}_drop_team", "A"), "A")
        if cause == "ナイスディフェンス":
            throw_category = safe_str(
                st.session_state.get(f"event_{i}_throw_category", THROW_CATEGORY_OPTIONS[0]),
                THROW_CATEGORY_OPTIONS[0],
            )
            throw_detail_options = THROW_DETAIL_OPTIONS.get(throw_category, ["-"])
            events.append(
                {
                    "cause": cause,
                    "drop_type": "",
                    "throw_category": throw_category,
                    "throw_detail": safe_str(
                        st.session_state.get(f"event_{i}_throw_detail", throw_detail_options[0]),
                        throw_detail_options[0],
                    ),
                    "place_side": "",
                    "place_end": "",
                    "mistake_team": drop_team,
                    "from_player": "",
                    "to_player": "",
                    "defender_name": safe_str(st.session_state.get(f"event_{i}_defender_name", "")),
                    "nice_defense_type": safe_str(
                        st.session_state.get(f"event_{i}_nice_defense_type", NICE_DEFENSE_TYPE_OPTIONS[0]),
                        NICE_DEFENSE_TYPE_OPTIONS[0],
                    ),
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
                    "mistake_team": drop_team,
                    "from_player": safe_str(st.session_state.get(f"event_{i}_from_player", "")),
                    "to_player": safe_str(st.session_state.get(f"event_{i}_to_player", "")),
                    "defender_name": "",
                    "nice_defense_type": "",
                }
            )
    return events


def save_csv(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")


def build_events_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in df.iterrows():
        events = parse_events_json(row.get("drop_events_json", ""))
        for event in events:
            rows.append(
                {
                    "turn_no": int(row["turn_no"]),
                    "cause": safe_str(event.get("cause", "")),
                    "drop_type": safe_str(event.get("drop_type", "")),
                    "throw_category": safe_str(event.get("throw_category", "")),
                    "throw_detail": safe_str(event.get("throw_detail", "")),
                    "place_side": safe_str(event.get("place_side", "")),
                    "place_end": safe_str(event.get("place_end", "")),
                    "mistake_team": safe_str(event.get("mistake_team", "")),
                    "from_player": safe_str(event.get("from_player", "")),
                    "to_player": safe_str(event.get("to_player", "")),
                    "defender_name": safe_str(event.get("defender_name", "")),
                    "nice_defense_type": safe_str(event.get("nice_defense_type", "")),
                }
            )
    return pd.DataFrame(rows)


initialize_state()
initialize_input_state()

# ウィジェットを描画する前にリセット予約を処理する
if st.session_state.pending_turn_input_reset:
    reset_turn_inputs()
    st.session_state.pending_turn_input_reset = False

st.sidebar.title("入力")

with st.sidebar.container(border=True):
    st.markdown("#### 試合情報")
    st.text_input("試合タイトル", key="match_title", placeholder="例: 春季リーグ 第2節")
    st.text_input("Aチーム名", key="team_a_name", placeholder="例: 東京アルティメット")
    st.text_input("Bチーム名", key="team_b_name", placeholder="例: 京都アルティメット")

with st.sidebar.container(border=True):
    st.markdown("#### ターン基本情報")
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
        "ディフェンスタイプ" + "（TO後）" if st.session_state.offense_start_team == "A" else "ディフェンスタイプ",
        DEFENSE_TYPE_OPTIONS,
        key="team_a_defense_type",
    )
    st.selectbox("フォース", FORCE_OPTIONS, key="team_a_force")

    st.markdown(f"**{get_team_label('B')}**")
    st.selectbox("メンバー", MEMBER_OPTIONS, key="team_b_member")
    st.selectbox(
        "ディフェンスタイプ" + "（TO後）" if st.session_state.offense_start_team == "B" else "ディフェンスタイプ",
        DEFENSE_TYPE_OPTIONS,
        key="team_b_defense_type",
    )
    st.selectbox("フォース", FORCE_OPTIONS, key="team_b_force")

with st.sidebar.container(border=True):
    st.markdown("#### ターン内イベント")
    st.number_input("このターンのドロップ/ディフェンスイベント数", min_value=0, max_value=10, step=1, key="drop_count")

drop_count = int(st.session_state.drop_count)
for i in range(drop_count):
    with st.sidebar.container(border=True):
        st.markdown(f"**イベント {i + 1}**")
        st.selectbox("原因", EVENT_CAUSE_OPTIONS, key=f"event_{i}_cause")
        st.radio(
            "ドロップしたチーム",
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
            st.selectbox("場所（ハメ側/アンハメ側）", PLACE_SIDE_OPTIONS, key=f"event_{i}_place_side")
            st.selectbox("場所（エンド前/Not）", PLACE_END_OPTIONS, key=f"event_{i}_place_end")
            st.text_input("誰から（パサー）", key=f"event_{i}_from_player", placeholder="例: 田中")
            st.text_input("誰へ（レシーバー）", key=f"event_{i}_to_player", placeholder="例: 佐藤")

with st.sidebar.container(border=True):
    st.subheader("得点入力（1ターン=1得点）")
    col_a, col_b = st.columns(2)

if col_a.button(f"{get_team_label('A')} 得点", use_container_width=True, type="primary"):
    add_turn(
        point_winner="A",
        offense_start_team=st.session_state.offense_start_team,
        team_a_member=st.session_state.team_a_member,
        team_b_member=st.session_state.team_b_member,
        team_a_force=st.session_state.team_a_force,
        team_b_force=st.session_state.team_b_force,
        team_a_defense_type=st.session_state.team_a_defense_type,
        team_b_defense_type=st.session_state.team_b_defense_type,
        match_title=st.session_state.match_title,
        team_a_name=st.session_state.team_a_name,
        team_b_name=st.session_state.team_b_name,
        drop_events=collect_turn_events(drop_count),
    )
    schedule_turn_input_reset()
    st.rerun()

if col_b.button(f"{get_team_label('B')} 得点", use_container_width=True, type="primary"):
    add_turn(
        point_winner="B",
        offense_start_team=st.session_state.offense_start_team,
        team_a_member=st.session_state.team_a_member,
        team_b_member=st.session_state.team_b_member,
        team_a_force=st.session_state.team_a_force,
        team_b_force=st.session_state.team_b_force,
        team_a_defense_type=st.session_state.team_a_defense_type,
        team_b_defense_type=st.session_state.team_b_defense_type,
        match_title=st.session_state.match_title,
        team_a_name=st.session_state.team_a_name,
        team_b_name=st.session_state.team_b_name,
        drop_events=collect_turn_events(drop_count),
    )
    schedule_turn_input_reset()
    st.rerun()

with st.sidebar.container(border=True):
    if st.button("直前ターンを削除", use_container_width=True):
        if st.session_state.turns:
            st.session_state.turns.pop()
        st.rerun()

    if st.button("全データをリセット", use_container_width=True):
        st.session_state.turns = []
        if CSV_PATH.exists():
            CSV_PATH.unlink()
        st.success("セッションデータと保存CSVをリセットしました。")
        st.rerun()

df = turns_to_dataframe(st.session_state.turns)

with st.sidebar.container(border=True):
    st.markdown("#### 保存・読込")
    if st.button("CSVに保存", use_container_width=True):
        save_csv(df)
        st.success(f"保存しました: {CSV_PATH.name}")

    if st.button("保存済みCSVを読み込む", use_container_width=True):
        if CSV_PATH.exists():
            loaded_df = pd.read_csv(CSV_PATH)
            st.session_state.turns = dataframe_to_turns(loaded_df)
            st.success(f"読み込みました: {CSV_PATH.name}")
            st.rerun()
        else:
            st.info("保存済みCSVが見つかりません。")

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

match_title_display = st.session_state.match_title.strip() or "練習試合"
team_a_name_display = st.session_state.team_a_name.strip() or "Aチーム"
team_b_name_display = st.session_state.team_b_name.strip() or "Bチーム"

st.title(f"{match_title_display} - アルティメット記録・分析")

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
preview_col1.write(
    f"- {team_b_name_display}: メンバー={st.session_state.team_b_member} / D={st.session_state.team_b_defense_type}{'（TO後）' if st.session_state.offense_start_team == 'B' else ''} / フォース={st.session_state.team_b_force}"
)
preview_col2.write(f"- イベント数: {drop_count}")

if preview_events_df.empty:
    st.caption("このターンのイベント入力はありません。")
else:
    st.dataframe(preview_events_df, use_container_width=True, hide_index=True)

if df.empty:
    st.info("サイドバーで属性を選び、A得点/B得点ボタンでターンを記録してください。")
    st.stop()

if "team_a_name" in df.columns:
    team_a_name_display = safe_str(df.iloc[-1].get("team_a_name", team_a_name_display), team_a_name_display)
if "team_b_name" in df.columns:
    team_b_name_display = safe_str(df.iloc[-1].get("team_b_name", team_b_name_display), team_b_name_display)
if "match_title" in df.columns:
    match_title_display = safe_str(df.iloc[-1].get("match_title", match_title_display), match_title_display)

st.caption(f"試合: {match_title_display}")

df["A_score"] = (df["point_winner"] == "A").cumsum()
df["B_score"] = (df["point_winner"] == "B").cumsum()

latest = df.iloc[-1]
st.subheader("現在スコア")
score_col1, score_col2 = st.columns(2)
score_col1.metric(team_a_name_display, int(latest["A_score"]))
score_col2.metric(team_b_name_display, int(latest["B_score"]))

st.subheader("得点推移")
score_chart = df[["turn_no", "A_score", "B_score"]].set_index("turn_no")
score_chart = score_chart.rename(columns={"A_score": team_a_name_display, "B_score": team_b_name_display})
st.line_chart(score_chart)

st.subheader("ブレイク集計")
break_a = int(((df["point_winner"] == "A") & (df["is_break"])).sum())
break_b = int(((df["point_winner"] == "B") & (df["is_break"])).sum())
c1, c2 = st.columns(2)
c1.metric(f"{team_a_name_display}のブレイク数", break_a)
c2.metric(f"{team_b_name_display}のブレイク数", break_b)

st.subheader("Oセット キープ率")
keep_col1, keep_col2 = st.columns(2)

o_keep_mask_a = (df["offense_start_team"] == "A") & (df["team_a_member"] == "Oセット")
o_keep_den_a = int(o_keep_mask_a.sum())
o_keep_num_a = int(((df["point_winner"] == "A") & o_keep_mask_a).sum())
o_keep_rate_a = (o_keep_num_a / o_keep_den_a) if o_keep_den_a > 0 else 0.0
keep_col1.metric(
    f"{team_a_name_display}",
    f"{o_keep_rate_a:.1%}",
    help=f"{o_keep_num_a} / {o_keep_den_a}",
)

o_keep_mask_b = (df["offense_start_team"] == "B") & (df["team_b_member"] == "Oセット")
o_keep_den_b = int(o_keep_mask_b.sum())
o_keep_num_b = int(((df["point_winner"] == "B") & o_keep_mask_b).sum())
o_keep_rate_b = (o_keep_num_b / o_keep_den_b) if o_keep_den_b > 0 else 0.0
keep_col2.metric(
    f"{team_b_name_display}",
    f"{o_keep_rate_b:.1%}",
    help=f"{o_keep_num_b} / {o_keep_den_b}",
)

st.subheader("イベント分析（ミス / ナイスディフェンス）")
events_df = build_events_dataframe(df)

if events_df.empty:
    st.write("イベント記録はまだありません。")
else:
    left, right = st.columns(2)
    with left:
        st.write("原因別 件数")
        st.dataframe(
            events_df["cause"].value_counts().rename_axis("cause").reset_index(name="count"),
            use_container_width=True,
            hide_index=True,
        )

        mistake_only = events_df[events_df["cause"] == "ミス"]
        if not mistake_only.empty:
            st.write("ミス種類別 件数")
            st.dataframe(
                mistake_only["drop_type"]
                .value_counts()
                .rename_axis("drop_type")
                .reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

            st.write("スロー種類別 件数")
            st.dataframe(
                mistake_only["throw_category"]
                .value_counts()
                .rename_axis("throw_category")
                .reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

            st.write("スロー詳細別 件数")
            st.dataframe(
                mistake_only["throw_detail"]
                .value_counts()
                .rename_axis("throw_detail")
                .reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

            st.write("場所（ハメ側/アンハメ側）件数")
            st.dataframe(
                mistake_only["place_side"]
                .value_counts()
                .rename_axis("place_side")
                .reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

            st.write("場所（エンド前/Not）件数")
            st.dataframe(
                mistake_only["place_end"]
                .value_counts()
                .rename_axis("place_end")
                .reset_index(name="count"),
                use_container_width=True,
                hide_index=True,
            )

    with right:
        nice_df = events_df[events_df["cause"] == "ナイスディフェンス"]
        if nice_df.empty:
            st.write("ナイスディフェンス記録はまだありません。")
        else:
            st.write("ナイスディフェンスした人")
            defender_counts = (
                nice_df[nice_df["defender_name"].astype(str).str.strip() != ""]["defender_name"]
                .value_counts()
                .rename_axis("defender_name")
                .reset_index(name="count")
            )
            st.dataframe(defender_counts, use_container_width=True, hide_index=True)

            if "nice_defense_type" in nice_df.columns:
                st.write("ナイスディフェンス種類別 件数")
                nice_type_counts = (
                    nice_df[nice_df["nice_defense_type"].astype(str).str.strip() != ""]["nice_defense_type"]
                    .value_counts()
                    .rename_axis("nice_defense_type")
                    .reset_index(name="count")
                )
                st.dataframe(nice_type_counts, use_container_width=True, hide_index=True)

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
        "team_b_member",
        "team_b_defense_type",
        "team_b_force",
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
        "team_b_member": f"{team_b_name_display}_メンバー",
        "team_b_defense_type": f"{team_b_name_display}_Dタイプ",
        "team_b_force": f"{team_b_name_display}_フォース",
    }
)
show_df = show_df.rename(columns={"A_score": team_a_name_display, "B_score": team_b_name_display})
st.dataframe(show_df, use_container_width=True, hide_index=True)

st.subheader("イベント詳細")
if events_df.empty:
    st.write("イベント詳細はありません。")
else:
    detail_df = events_df.copy()
    detail_df["mistake_team"] = detail_df["mistake_team"].replace(
        {"A": team_a_name_display, "B": team_b_name_display}
    )
    st.dataframe(detail_df, use_container_width=True, hide_index=True)