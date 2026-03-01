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
APP_PASSWORD = "tobqrjnabkbqkjuo"  # Your 16-character Google App Password

# Nifty 50 List
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


def send_email(file_path, alert_count):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = f"NSE Cardwell PR Alert: {alert_count} Signals Found"

    body = f"The daily Cardwell RSI scan for {datetime.now().strftime('%Y-%m-%d')} is complete.\n\nFound {alert_count} Positive Reversals. Report attached."
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
    alerts = []  # Fixed: Initialized at the start of the scan
    print(f"--- Starting Scan: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['RSI'] = get_rsi(df['Close'])
            w_rsi = get_rsi(df['Close'].resample('W').last()).reindex(df.index, method='ffill')
            m_rsi = get_rsi(df['Close'].resample('M').last()).reindex(df.index, method='ffill')

            # Cardwell Positive Reversal Logic
            curr_low = df['Low'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]
            prev_segment = df.iloc[-25:-5]
            prev_low = prev_segment['Low'].min()
            prev_rsi_low = prev_segment['RSI'].min()

            is_pr = (curr_low > prev_low) and (curr_rsi < prev_rsi_low)
            is_bullish = (w_rsi.iloc[-1] > 60) and (m_rsi.iloc[-1] > 60)

            # Cross up through 40 floor
            if is_pr and is_bullish and (curr_rsi > 40) and (df['RSI'].iloc[-2] <= 40):
                prior_high = df['High'].iloc[-25:].max()
                target = curr_low + (prior_high - prev_low)

                alerts.append({
                    "Ticker": ticker,
                    "Price": round(df['Close'].iloc[-1], 2),
                    "Target Price": round(target, 2),
                    "Daily RSI": round(curr_rsi, 2),
                    "Weekly RSI": round(w_rsi.iloc[-1], 2),
                    "Monthly RSI": round(m_rsi.iloc[-1], 2)
                })
                print(f"Signal Found: {ticker}")
        except:
            continue

    if alerts:
        alert_df = pd.DataFrame(alerts)
        file_path = os.path.expanduser("~/Cardwell_Daily_Report.xlsx")
        alert_df.to_excel(file_path, index=False)
        send_email(file_path, len(alerts))
    else:
        print("No signals found today.")



if __name__ == "__main__":
    run_automated_cardwell_scan()

