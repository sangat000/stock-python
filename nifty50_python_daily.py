import yfinance as yf
import pandas as pd
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SENDER_EMAIL = "sangat000@gmail.com"
RECEIVER_EMAIL = "sangat000@gmail.com"
APP_PASSWORD = "tobqrjnabkbqkjuo"

nifty50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "SHRIRAMFIN.NS", "JIOFIN.NS"
]


def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def send_email(file_path, pr_count, nr_count, backtest_count):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = f"NSE Cardwell (>5d Filter): {pr_count} PR | {nr_count} NR"

    body = (f"Scan completed for {datetime.now().strftime('%Y-%m-%d')}.\n"
            f"Filter Applied: Previous reference point must be > 5 days old.\n\n"
            f"--- TODAY'S SIGNALS ---\n"
            f"Positive Reversals: {pr_count}\n"
            f"Negative Reversals: {nr_count}\n\n"
            f"--- 3-MONTH BACKTEST ---\n"
            f"Historical Signals Found: {backtest_count}\n\n"
            "See attached Excel for 'Today_Signals' and '3Month_Backtest' tabs.")

    msg.attach(MIMEText(body, 'plain'))
    with open(file_path, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(file_path)}")
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")


def run_cardwell_with_filters():
    current_alerts = []
    historical_alerts = []

    print(f"--- Starting Scan (Logic: Reference Point > 5 days ago) ---")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            df['RSI'] = get_rsi(df['Close'])
            w_rsi = get_rsi(df['Close'].resample('W').last()).reindex(df.index, method='ffill')

            # Loop for last 40 trading days
            for i in range(len(df) - 65, len(df)):
                # Window excludes the last 5 days to satisfy your request
                # This ensures the 'previous' low/high is at least 5 days old
                lookback = df.iloc[i - 35:i - 5]
                if lookback.empty: continue

                curr_bar = df.iloc[i]
                c_low, c_high, c_rsi, c_close = curr_bar['Low'], curr_bar['High'], curr_bar['RSI'], curr_bar['Close']

                p_low = lookback['Low'].min()
                p_rsi_low = lookback['RSI'].min()
                p_high = lookback['High'].max()
                p_rsi_high = lookback['RSI'].max()

                signal_type = None
                target = None

                # 1. Positive Reversal (BULLISH)
                if (c_low > p_low) and (c_rsi < p_rsi_low) and (c_rsi > 40) and (w_rsi.iloc[i] > 60):
                    signal_type = "BULLISH (PR)"
                    target = c_low + (p_high - p_low)

                # 2. Negative Reversal (BEARISH)
                elif (c_high < p_high) and (c_rsi > p_rsi_high) and (c_rsi < 60) and (w_rsi.iloc[i] < 40):
                    signal_type = "BEARISH (NR)"
                    target = c_high - (p_high - lookback['Low'].min())

                if signal_type:
                    outcome = "Pending"
                    pl_pct = 0.0
                    if i < len(df) - 1:
                        future = df.iloc[i + 1:]
                        if signal_type == "BULLISH (PR)":
                            if (future['High'] >= target).any():
                                outcome = "Success"
                                pl_pct = ((target - c_close) / c_close) * 100
                        else:  # Bearish
                            if (future['Low'] <= target).any():
                                outcome = "Success"
                                pl_pct = ((c_close - target) / c_close) * 100

                    alert_data = {
                        "Date": df.index[i].strftime('%Y-%m-%d'),
                        "Ticker": ticker,
                        "Type": signal_type,
                        "Entry Price": round(c_close, 2),
                        "Target Price": round(target, 2),
                        "Est Profit %": f"{round(pl_pct, 2)}%",
                        "Status": outcome
                    }

                    if i == len(df) - 1:
                        current_alerts.append(alert_data)
                    else:
                        historical_alerts.append(alert_data)

        except Exception:
            continue

    # File Generation
    file_path = os.path.expanduser("~/Cardwell_Filtered_Report.xlsx")
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame(current_alerts).to_excel(writer, sheet_name='Today_Signals', index=False)
        pd.DataFrame(historical_alerts).to_excel(writer, sheet_name='3Month_Backtest', index=False)

    send_email(file_path,
               len([x for x in current_alerts if "BULLISH" in x['Type']]),
               len([x for x in current_alerts if "BEARISH" in x['Type']]),
               len(historical_alerts))


if __name__ == "__main__":
    run_cardwell_with_filters()
