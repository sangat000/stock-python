import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import yfinance as yf
import pandas as pd
import numpy as np

# --- Email Configuration ---
# You must update these with your sender credentials
SENDER_EMAIL = "sangat000@gmail.com"
SENDER_PASSWORD = "tobqrjnabkbqkjuo"  # Use a Gmail App Password, not your regular password
RECIPIENT_EMAIL = "sangat000@gmail.com"

# Nifty 50 Tickers
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


def calculate_rsi(series, period=14):
    series = pd.to_numeric(series, errors='coerce')
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def send_email_with_attachment(recipient, file_path):
    print("\nPreparing to send email...")

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient
    msg['Subject'] = "Cardwell Strategy Nifty 50 Report"

    body = "Hello,\n\nPlease find the attached Cardwell Strategy report for the Nifty 50.\n\nBest regards,\nYour Trading Bot"
    msg.attach(MIMEText(body, 'plain'))

    # Attach the Excel file
    try:
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {filename}")
        msg.attach(part)

        # Connect to server and send
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, recipient, text)
        server.quit()

        print(f"Success! Email sent to {recipient}")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")


def generate_detailed_report(hold_days=10):
    trade_log = []

    print("Processing Nifty 50 for Cardwell Strategy... This may take a moment.")

    for ticker in nifty50:
        try:
            df = yf.download(ticker, period="3y", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df = df.dropna(subset=['Close'])

            # Indicators
            df['RSI_D'] = calculate_rsi(df['Close'], 14)
            w_rsi = calculate_rsi(df['Close'].resample('W').last(), 14).reindex(df.index, method='ffill')
            m_rsi = calculate_rsi(df['Close'].resample('M').last(), 14).reindex(df.index, method='ffill')

            # Cardwell Bull Floor Signal
            df['Signal'] = (df['RSI_D'] > 40) & (df['RSI_D'].shift(1) <= 40) & (w_rsi > 60) & (m_rsi > 60)

            signals = df[df['Signal'] == True].index
            for buy_date in signals:
                idx = df.index.get_loc(buy_date)
                if idx + hold_days < len(df):
                    sell_date = df.index[idx + hold_days]
                    buy_price = float(df.iloc[idx]['Close'])
                    sell_price = float(df.iloc[idx + hold_days]['Close'])
                    pnl_pct = ((sell_price - buy_price) / buy_price) * 100

                    trade_log.append({
                        "Ticker": ticker,
                        "Buy Date": buy_date.date(),
                        "Buy Price": round(buy_price, 2),
                        "Sell Date": sell_date.date(),
                        "Sell Price": round(sell_price, 2),
                        "P/L %": round(pnl_pct, 2),
                        "Status": "PROFIT" if pnl_pct > 0 else "LOSS"
                    })
        except:
            continue

    # Convert to DataFrame
    report_df = pd.DataFrame(trade_log)

    if not report_df.empty:
        # Create Loss Profile (Summarized by Share)
        loss_df = report_df[report_df['Status'] == "LOSS"]
        loss_profile = loss_df.groupby('Ticker').agg({
            'P/L %': ['count', 'mean', 'min']
        }).reset_index()
        loss_profile.columns = ['Ticker', 'Loss Count', 'Avg Loss %', 'Max Single Loss %']

        # Save to Excel
        desktop_path = os.path.expanduser("~/Cardwell_Nifty50_Report.xlsx")

        with pd.ExcelWriter(desktop_path) as writer:
            report_df.to_excel(writer, sheet_name='Buy-Sale Report', index=False)
            loss_profile.to_excel(writer, sheet_name='Loss Profile by Share', index=False)

        print("\nSuccess! 'Cardwell_Nifty50_Report.xlsx' created.")

        # Trigger the email sending function
        send_email_with_attachment(RECIPIENT_EMAIL, desktop_path)

        return report_df, loss_profile
    else:
        print("No signals found.")
        return None, None


# Run the report
if __name__ == "__main__":
    trade_log, loss_profile = generate_detailed_report()
