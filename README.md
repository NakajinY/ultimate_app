# アルティメットの分析用アプリ

Python + Streamlit で、試合中のターン/イベントを記録し、Google Sheets に保存して分析するアプリです。

## 主な機能

- 1ターン=1得点で記録
- イベント記録（`ミス` / `ナイスディフェンス` / `シュート`）
- 風向き記録（チームごと）
- 入力対象を選択（`既存試合に追記/編集` / `新規試合作成`）
- 試合情報一括編集（同一 `match_id` の `match_date` / `match_title` / チーム名を一括更新）
- Google Sheets 同期（`turn_log` / `event_log`）
- 主キー（`match_id`, `turn_id`, `event_id`）と監査列（`created_at`, `updated_at`, `input_by`）を保存
- `turn_no` は試合単位で採番（同一 `match_id` 内で `max + 1`）
- 不明値は `-` で統一

## Google Sheets 共有運用（本番）

このアプリは Google Sheets へ同期します。

- `turn_log`: `turn_id` ベースで UPSERT
- `event_log`: 追記中心（保存対象 `turn_id` の旧行を置換 + `event_id` 重複時は最新を採用）

### 1. 依存パッケージ

```bash
pip install -r requirements.txt
```

### 2. Secrets 設定

1. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. サービスアカウント情報とスプレッドシートURL（またはID）を設定
3. 対象スプレッドシートをサービスアカウントの `client_email` に共有（編集者）

### 3. シート準備

- ワークシート名: `turn_log`, `event_log`

## 保存カラム

### turn_log

- `turn_no`
- `match_id`
- `turn_id`
- `match_date`
- `match_title`
- `team_a_name`
- `team_b_name`
- `created_at`
- `updated_at`
- `input_by`
- `offense_start_team`
- `offense_start_team_name`
- `point_winner`
- `point_winner_name`
- `team_a_member`
- `team_b_member`
- `team_a_force`
- `team_b_force`
- `team_a_wind`
- `team_b_wind`
- `team_a_defense_type`
- `team_b_defense_type`
- `score_pattern`
- `score_from_player`
- `score_to_player`
- `drop_count`
- `drop_events_json`
- `is_break`

### event_log

- `event_id`
- `match_id`
- `turn_id`
- `turn_no`
- `match_date`
- `match_title`
- `team_a_name`
- `team_b_name`
- `created_at`
- `updated_at`
- `input_by`
- `event_type`
- `team`
- `wind_direction`
- `defense_type`
- `force`
- `drop_type`
- `shot_type`
- `throw_category`
- `throw_detail`
- `place_side`
- `place_end`
- `from_player`
- `to_player`
- `defender_name`
- `nice_defense_type`

## 入力ルール（重要）

- 文字入力が空欄の場合は保存時に自動で `-` を補完
- 不明な値は `-` で運用

## 使い方（推奨フロー）

1. 既存試合に追記する場合
	- 入力対象で `既存試合に追記/編集` を選択
	- 対象試合を選択してターンを追加
2. 新規試合を作る場合
	- 入力対象で `新規試合作成` を選択
	- 試合情報を入力してターンを追加
3. 試合情報をまとめて直す場合
	- `試合情報編集（同一match_idを一括更新）` で更新
4. ターン内容のみ直す場合
	- `過去ターン修正` で対象ターンを編集

### 4. Streamlit Cloud で公開

- アプリのSecretsに `.streamlit/secrets.toml` と同等内容を登録
- 公開URLから入力すると、同じ `turn_log` / `event_log` に反映されます

## ローカル実行

```bash
source .venv/bin/activate
streamlit run main.py
```