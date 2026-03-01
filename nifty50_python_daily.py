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
    "TATACONSUM.NS", "TMPV.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
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
    msg['Subject'] = f"NSE Cardwell Report: {pr_count} PR | {nr_count} NR"

    body = (f"Scan completed for {datetime.now().strftime('%Y-%m-%d')}.\n\n"
            f"--- TODAY'S SIGNALS ---\n"
            f"Positive Reversals: {pr_count}\n"
            f"Negative Reversals: {nr_count}\n\n"
            f"--- 3-MONTH BACKTEST ---\n"
            f"Historical Signals Found: {backtest_count}\n\n"
            "Attached Excel contains today's picks and the 3-month performance history.")

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


def run_cardwell_with_backtest():
    current_alerts = []
    historical_alerts = []

    # 3-Month Date Range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    print(f"--- Starting Scan & Backtest ---")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            df['RSI'] = get_rsi(df['Close'])
            w_rsi = get_rsi(df['Close'].resample('W').last()).reindex(df.index, method='ffill')

            # Logic Loop: Scan every day for the last 90 days
            for i in range(len(df) - 65, len(df)):
                curr_slice = df.iloc[:i + 1]
                lookback = df.iloc[i - 30:i - 5]

                if lookback.empty: continue

                c_low = curr_slice['Low'].iloc[-1]
                c_high = curr_slice['High'].iloc[-1]
                c_rsi = curr_slice['RSI'].iloc[-1]

                p_low = lookback['Low'].min()
                p_rsi_low = lookback['RSI'].min()
                p_high = lookback['High'].max()
                p_rsi_high = lookback['RSI'].max()

                signal_type = None
                target = None

                # Positive Reversal (PR)
                if (c_low > p_low) and (c_rsi < p_rsi_low) and (c_rsi > 40) and (w_rsi.iloc[i] > 60):
                    signal_type = "BULLISH (PR)"
                    target = c_low + (p_high - p_low)

                # Negative Reversal (NR)
                elif (c_high < p_high) and (c_rsi > p_rsi_high) and (c_rsi < 60) and (w_rsi.iloc[i] < 40):
                    signal_type = "BEARISH (NR)"
                    target = c_high - (p_high - lookback['Low'].min())

                if signal_type:
                    date_str = curr_slice.index[-1].strftime('%Y-%m-%d')
                    entry_price = curr_slice['Close'].iloc[-1]

                    # Check Result for historical signals
                    outcome = "Pending"
                    if i < len(df) - 1:
                        future_data = df.iloc[i + 1:]
                        if signal_type == "BULLISH (PR)" and (future_data['High'] >= target).any():
                            outcome = "Success (Target Hit)"
                        elif signal_type == "BEARISH (NR)" and (future_data['Low'] <= target).any():
                            outcome = "Success (Target Hit)"

                    alert_data = {
                        "Date": date_str, "Ticker": ticker, "Type": signal_type,
                        "Price": round(entry_price, 2), "Target": round(target, 2), "Outcome": outcome
                    }

                    if i == len(df) - 1:
                        current_alerts.append(alert_data)
                    else:
                        historical_alerts.append(alert_data)

        except Exception as e:
            continue

    # Prepare Report
    file_path = os.path.expanduser("~/Cardwell_Full_Report.xlsx")
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame(current_alerts).to_excel(writer, sheet_name='Today_Signals', index=False)
        pd.DataFrame(historical_alerts).to_excel(writer, sheet_name='3Month_Backtest', index=False)

    send_email(file_path, len(current_alerts),
               len([x for x in current_alerts if "BEARISH" in x['Type']]),
               len(historical_alerts))


if __name__ == "__main__":
    run_cardwell_with_backtest()
