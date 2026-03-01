import yfinance as yf
import pandas as pd
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

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


def send_email(file_path, pr_count, nr_count):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = f"NSE Cardwell Alert: {pr_count} Bullish | {nr_count} Bearish"

    body = (f"Daily Cardwell RSI scan for {datetime.now().strftime('%Y-%m-%d')} is complete.\n\n"
            f"Positive Reversals (Bullish): {pr_count}\n"
            f"Negative Reversals (Bearish): {nr_count}\n\n"
            "Detailed report is attached.")

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


def run_automated_cardwell_scan():
    alerts = []
    print(f"--- Starting Scan: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 50: continue

            # Clean multi-index columns if they exist
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['RSI'] = get_rsi(df['Close'])
            w_rsi = get_rsi(df['Close'].resample('W').last()).reindex(df.index, method='ffill')
            m_rsi = get_rsi(df['Close'].resample('M').last()).reindex(df.index, method='ffill')

            # Current Values
            curr_low = df['Low'].iloc[-1].item()
            curr_high = df['High'].iloc[-1].item()
            curr_rsi = df['RSI'].iloc[-1].item()
            curr_close = df['Close'].iloc[-1].item()

            # Historical Window (lookback for previous swing)
            lookback = df.iloc[-30:-5]
            prev_low = lookback['Low'].min()
            prev_rsi_low = lookback['RSI'].min()
            prev_high = lookback['High'].max()
            prev_rsi_high = lookback['RSI'].max()

            # --- CARDWELL POSITIVE REVERSAL (BULLISH) ---
            is_pr = (curr_low > prev_low) and (curr_rsi < prev_rsi_low)
            is_bullish_trend = (w_rsi.iloc[-1].item() > 60) or (m_rsi.iloc[-1].item() > 60)

            if is_pr and is_bullish_trend and (curr_rsi > 40):
                target = curr_low + (lookback['High'].max() - prev_low)
                alerts.append({
                    "Ticker": ticker, "Type": "BULLISH (PR)", "Price": round(curr_close, 2),
                    "Target/Est": round(target, 2), "Daily RSI": round(curr_rsi, 2)
                })

            # --- CARDWELL NEGATIVE REVERSAL (BEARISH) ---
            # Logic: Lower Price High + Higher RSI High
            is_nr = (curr_high < prev_high) and (curr_rsi > prev_rsi_high)
            is_bearish_trend = (w_rsi.iloc[-1].item() < 40) or (m_rsi.iloc[-1].item() < 40)

            if is_nr and is_bearish_trend and (curr_rsi < 60):
                # Target for NR: Current High - (Previous High - Previous Low)
                target = curr_high - (prev_high - lookback['Low'].min())
                alerts.append({
                    "Ticker": ticker, "Type": "BEARISH (NR)", "Price": round(curr_close, 2),
                    "Target/Est": round(target, 2), "Daily RSI": round(curr_rsi, 2)
                })

        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            continue

    if alerts:
        alert_df = pd.DataFrame(alerts)
        pr_count = len(alert_df[alert_df['Type'] == "BULLISH (PR)"])
        nr_count = len(alert_df[alert_df['Type'] == "BEARISH (NR)"])

        file_path = os.path.expanduser("~/Cardwell_Daily_Report.xlsx")
        alert_df.to_excel(file_path, index=False)
        send_email(file_path, pr_count, nr_count)
    else:
        print("No signals found today.")


if __name__ == "__main__":
    run_automated_cardwell_scan()
