import sqlite3
from datetime import datetime
import yfinance as yf

# 対象インデックスの定義
# MSCI ACWIはYahoo Finance上のMSCI直接指数（STRD=配当再投資なしの価格指数）を使用。
# MSCI エマージング・マーケットは直接指数（^891800-USD-STRD）だと過去データが
# 取得できなかったため、連動するiSharesのETF（EEM）で代用。
TARGET_INDEXES = [
    # 世界
    {"category": "世界", "name": "MSCI ACWI", "ticker": "^892400-USD-STRD"},
    {"category": "世界", "name": "MSCI エマージング・マーケット・インデックス", "ticker": "EEM"},
    # 日本
    {"category": "日本", "name": "日経平均", "ticker": "^N225"},
    # 米国
    {"category": "米国", "name": "S&P 500", "ticker": "^GSPC"},
    {"category": "米国", "name": "NYダウ", "ticker": "^DJI"},
    {"category": "米国", "name": "NASDAQ100", "ticker": "^NDX"},
]

#出力先データベースパス
DB_PATH = "stock_data.db"

def init_db():
    """DBテーブルの初期化"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_closes (
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()
    conn.close()

def fetch_30year_history():
    """過去30年分の全データを取得してDBに一括保存"""
    init_db()
    
    # 30年前の開始年月日（1996-01-01）
    start_date = "1996-01-01"
    
    print(f"[{datetime.now()}] 過去30年分（{start_date}〜）のデータ取得を開始します...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for item in TARGET_INDEXES:
        category = item["category"]
        name = item["name"]
        ticker = item["ticker"]

        print(f"\n--- {name} ({ticker}) 取得中 ---")

        try:
            stock = yf.Ticker(ticker)
            # 指定日以降の日次データを取得
            df = stock.history(start=start_date, interval="1d")

            if df.empty:
                print(f"  [警告] {name} のデータが取得できませんでした。")
                continue

            # Close が欠損（NaN）の行を除外
            # ※ SQLiteはNaNをバインドするとNULLとして扱うため、
            #   NOT NULL制約違反を防ぐには事前の除外が必須
            before_count = len(df)
            df = df.dropna(subset=['Close'])
            dropped = before_count - len(df)
            if dropped > 0:
                print(f"  [情報] Closeが欠損している {dropped} 件のデータをスキップしました。")

            if df.empty:
                print(f"  [警告] {name} は有効なデータがありませんでした。")
                continue

            records = []
            for date_idx, row in df.iterrows():
                date_str = date_idx.strftime('%Y-%m-%d')
                close_price = round(float(row['Close']), 2)
                records.append((date_str, category, name, ticker, close_price))

            # executemany で高速一括挿入
            cursor.executemany("""
                INSERT INTO daily_closes (date, category, name, ticker, close)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET 
                    close=excluded.close,
                    name=excluded.name,
                    category=excluded.category
            """, records)

            print(f"  [完了] {len(records)} 件のデータを保存しました。（最古: {records[0][0]} 〜 最新: {records[-1][0]}）")

        except Exception as e:
            print(f"  [エラー] {name} ({ticker}): {e}")

    conn.commit()
    conn.close()
    print(f"\n[{datetime.now()}] すべての初期データ取得が完了しました。")

if __name__ == "__main__":
    fetch_30year_history()