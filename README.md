# アルティメットの分析用アプリ

Python + Streamlit で、試合中のターン/イベントを記録し、Google Sheets に保存して分析するアプリです。

## 主な機能

- 1ターン = 1得点で記録
- マルチページ構成（`data input` / `data analysis`）
- 試合フォーマット選択に応じた自動入力
	- 試合タイトル自動生成
	- 一部チーム情報の自動初期値
- 次ターンのオフェンス開始チーム自動設定
	- `O対D（O固定スタート）` 以外は「被得点側が次ターンO」
- イベント入力補助
	- `オフェンスしてたチーム` をイベント種別に応じて自動計算
	- `ナイスディフェンス` / `ミス` でオフェンス入れ替え
	- `シュート` ではオフェンス維持
- Google Sheets 同期（`turn_log` / `event_log`）
- 主キー（`match_id`, `turn_id`, `event_id`）と監査列（`created_at`, `updated_at`, `input_by`）保存

## ファイル構成と役割

- [main.py](main.py)
	- 入力ページ（`data input`）本体
	- ターン入力、イベント入力、編集UI、Google Sheets同期処理
	- ターンログ/イベントログの入力補助表示
- [pages/2_data_analysys.py](pages/2_data_analysys.py)
	- 分析ページ（`data analysis`）
	- 試合一覧KPI、試合選択後の詳細分析、条件比較
- [app/analysis_utils.py](app/analysis_utils.py)
	- 分析共通ユーティリティ
	- `turn_log` 読込、`is_break` 正規化、得点推移チャート描画
- [.streamlit/pages.toml](.streamlit/pages.toml)
	- ページ名・順序・アイコン定義
- [requirements.txt](requirements.txt)
	- 実行に必要なPython依存パッケージ

## Google Sheets 共有運用

- `turn_log`: `turn_id` ベースで UPSERT
- `event_log`: 追記中心（対象 `turn_id` の旧行置換 + `event_id` 重複時は最新採用）

### セットアップ

1. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

2. Secrets 設定
	 - `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
	 - サービスアカウント情報とスプレッドシートURL（またはID）を設定
	 - 対象スプレッドシートを `client_email` に共有（編集者）

3. シート準備
	 - ワークシート名: `turn_log`, `event_log`

## 保存カラム（主要）

### turn_log

- 基本: `turn_no`, `match_id`, `turn_id`, `match_date`, `match_title`, `match_format`
- チーム: `team_a_name`, `team_b_name`
- 監査: `created_at`, `updated_at`, `input_by`
- ターン情報: `offense_start_team`, `offense_start_team_name`, `point_winner`, `point_winner_name`
- 条件: `team_a_member`, `team_b_member`, `team_a_force`, `team_b_force`, `team_a_wind`, `team_b_wind`, `team_a_defense_type`, `team_b_defense_type`
- 得点: `score_pattern`, `score_from_player`, `score_to_player`
- イベント集約: `drop_count`, `drop_events_json`
- 指標: `is_break`

### event_log

- 基本: `event_id`, `match_id`, `turn_id`, `turn_no`, `match_date`, `match_title`
- チーム: `team_a_name`, `team_b_name`, `team`
- 監査: `created_at`, `updated_at`, `input_by`
- 条件: `wind_direction`, `defense_type`, `force`
- イベント詳細: `event_type`, `drop_type`, `shot_type`, `throw_category`, `throw_detail`, `place_side`, `place_end`, `from_player`, `to_player`, `defender_name`, `nice_defense_type`

## 編集機能

- 試合情報一括編集
	- `試合情報編集（同一match_idを一括更新）`
	- 同一 `match_id` の `match_date` / `match_title` / `match_format` / チーム名などを一括更新
- 過去ターン修正
	- `過去ターン修正`
	- 任意ターンを読み込んで内容修正 or 削除

## 入力ルール

- 文字入力が空欄の場合、保存時に `-` を補完
- 不明値は `-` で統一

## 使い方（推奨フロー）

1. `既存試合に追記/編集` か `新規試合作成` を選択
2. 試合フォーマットを選択し、必要項目を入力
3. イベントと得点を入力してターン保存
4. 必要に応じて試合情報一括編集 / 過去ターン修正
5. `data analysis` ページでKPIと詳細を確認

## ローカル実行

```bash
source .venv/bin/activate
streamlit run main.py
```

起動後、ページ一覧から `data input` / `data analysis` を切り替えて利用できます。