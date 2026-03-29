# アルティメットの分析用のアプリ
pythonのstreamlitを使う
# 予定
- streamlitの練習をする

## Google Sheets 共有運用（本番）

このアプリは、得点入力/削除/リセット時に Google Sheets へ自動同期します。

### 1. 依存パッケージ

```bash
pip install -r requirements.txt
```

### 2. Secrets 設定

1. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. サービスアカウント情報とスプレッドシートURL（またはID）を設定
3. 対象スプレッドシートをサービスアカウントの `client_email` に共有（編集者）

### 3. シート準備

- ワークシート名: `turn_log`

### 4. Streamlit Cloud で公開

- アプリのSecretsに `.streamlit/secrets.toml` と同等内容を登録
- 公開URLから入力すると、同じ `turn_log` に反映されます