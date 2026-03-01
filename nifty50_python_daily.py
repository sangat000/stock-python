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
# Pulls securely from GitHub Actions Secrets
#APP_PASSWORD = os.environ.get("EMAIL_PASSWORD") 
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


def send_email(file_path, alert_count, last_historical_signal=None):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    
    if alert_count > 0:
        msg['Subject'] = f"NSE Cardwell PR Alert: {alert_count} Signals Found"
        body = f"The daily Cardwell RSI scan for {datetime.now().strftime('%Y-%m-%d')} is complete.\n\nFound {alert_count} Positive Reversals. Report attached."
        msg.attach(MIMEText(body, 'plain'))

        # Only attach the file if there are alerts
        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(file_path)}")
            msg.attach(part)
    else:
        msg['Subject'] = "NSE Cardwell PR Alert: No Signals Today"
        body = f"The daily Cardwell RSI scan for {datetime.now().strftime('%Y-%m-%d')} is complete.\n\nNo new Positive Reversal signals were found today."
        
        if last_historical_signal and last_historical_signal['date']:
            body += f"\n\nFor context, the most recent historical buy signal occurred on {last_historical_signal['date']} for {last_historical_signal['ticker']}."
            
        msg.attach(MIMEText(body, 'plain'))

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
    # Dictionary to track the most recent signal found in the past 60 days
    recent_history = {"date": None, "ticker": None, "timestamp": pd.Timestamp.min}
    
    print(f"--- Starting Scan: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['RSI'] = get_rsi(df['Close'])
            w_rsi = get_rsi(df['Close'].resample('W').last()).reindex(df.index, method='ffill')
            m_rsi = get_rsi(df['Close'].resample('M').last()).reindex(df.index, method='ffill')

            # Helper function to check PR conditions at any given index
            def check_signal_at_index(i):
                if i < 25: return False
                curr_low = df['Low'].iloc[i]
                curr_rsi = df['RSI'].iloc[i]
                prev_segment = df.iloc[i-25:i-5]
                prev_low = prev_segment['Low'].min()
                prev_rsi_low = prev_segment['RSI'].min()

                is_pr = (curr_low > prev_low) and (curr_rsi < prev_rsi_low)
                is_bullish = (w_rsi.iloc[i] > 60) and (m_rsi.iloc[i] > 60)
                return is_pr and is_bullish and (curr_rsi > 40) and (df['RSI'].iloc[i-1] <= 40)

            # 1. Check for a signal TODAY (index -1)
            if check_signal_at_index(-1):
                prior_high = df['High'].iloc[-25:].max()
                prev_low = df.iloc[-25:-5]['Low'].min()
                curr_low = df['Low'].iloc[-1]
                target = curr_low + (prior_high - prev_low)

                alerts.append({
                    "Ticker": ticker,
                    "Price": round(df['Close'].iloc[-1], 2),
                    "Target Price": round(target, 2),
                    "Daily RSI": round(df['RSI'].iloc[-1], 2),
                    "Weekly RSI": round(w_rsi.iloc[-1], 2),
                    "Monthly RSI": round(m_rsi.iloc[-1], 2)
                })
                print(f"Signal Found Today: {ticker}")

            # 2. Lookback 60 days to find the most recent historical signal for context
            for i in range(len(df)-2, max(25, len(df)-60), -1):
                if check_signal_at_index(i):
                    sig_date = df.index[i]
                    if sig_date > recent_history["timestamp"]:
                        recent_history["timestamp"] = sig_date
                        recent_history["date"] = sig_date.strftime('%Y-%m-%d')
                        recent_history["ticker"] = ticker
                    break # Found the most recent for this ticker, stop looking back further

        except Exception as e:
            continue

    # Path changed to local directory for cloud compatibility
    file_path = "Cardwell_Daily_Report.xlsx" 

    if alerts:
        alert_df = pd.DataFrame(alerts)
        alert_df.to_excel(file_path, index=False)
        send_email(file_path, len(alerts))
    else:
        print("No signals found today. Sending notification email.")
        send_email(file_path, 0, recent_history)

if __name__ == "__main__":
    run_automated_cardwell_scan()
