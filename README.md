# AI Stock Market Analysis & Prediction System

A comprehensive Flask-based web application for stock market analysis and prediction with AI capabilities, designed to function like a mini trading platform.

## Features

### 🔐 Authentication System
- **Secure Login**: User authentication with username and password
- **Registration**: New user sign-up with password confirmation
- **Session Management**: Flask sessions for secure user tracking
- **Protected Routes**: All main features require authentication
- **Database Storage**: SQLite database for secure credential storage

### 🏠 Main Dashboard
- Real-time market overview (NIFTY/SENSEX simulation)
- Top gainers and losers
- AI-powered market insights
- Today's trading recommendations

### ⭐ Sector Analysis
- Analysis of major sectors: IT, Banking, Pharma, FMCG
- Sector performance metrics (growth, risk level, trend)
- Comparative sector charts
- AI-generated sector insights

- Analysis of major sectors: IT, Banking, Pharma, FMCG
- Sector performance metrics (growth, risk level, trend)
- Comparative sector charts
- AI-generated sector insights

### ⚖️ Risk Analysis
- Advanced Streamlit-based risk analysis dashboard with interactive 3D charts
- Volatility-based risk classification using daily returns (Low/Medium/High)
- Integrated predictive insights for short-term trend analysis
- KPI cards for risk category counts, safest and riskiest stocks
- Structured comparison table with conditional formatting and gradient-based color coding
- Risk vs return scatter plots and 3D visualizations

### 💼 Portfolio Optimization
- Multi-stock portfolio creation
- AI-based allocation optimization
- Pie chart visualization
- Optimal portfolio recommendations

### ✨ Market Mind 2.0 Additions
- **Ask AI chatbot**: Uses OpenAI or a local Ollama model with relevant project documentation, recent chat turns, and locally calculated stock metrics as context. Ollama answers stream into the chat as they are generated.
- **Explainable AI**: Shows recent daily return, annualized recent volatility, moving-average relationship, and historical price change for a selected stock.
- **News Sentiment Analysis**: Tries Yahoo Finance first, then falls back to Google News RSS when Yahoo returns no headlines. It deduplicates headlines and classifies them as positive, negative, or neutral with an explainable keyword baseline.
- **Dark / Light Theme Switch**: Toggle the interface theme from the right side of the top navigation bar; the preference is saved in the browser.

Ask AI requires either an OpenAI API key and internet access or a running local Ollama model. Ollama output streams into the chat, and project questions receive relevant README context. News headlines require an internet connection; the app tries two providers and shows a provider-specific message if both are unavailable. The Investment Advisor handles unsupported/short stock series individually, reports input errors, and uses a pandas-version-compatible month-end resampling alias. Sentiment labels are not financial advice, and explainability indicators describe historical data rather than guaranteeing future movements.


## How to use the new Market Mind features

### Investment Advisor (🤖)
1. Log in and open **Investment Advisor** from the left sidebar.
2. Choose a sector or leave **All Sectors** selected for a comparison across IT, Banking, Pharma, and FMCG.
3. Optionally enter a positive budget, select Low / Balanced / High Growth risk preference, and choose a date range. Leave dates empty to use all available historical data.
4. Click **Generate Recommendation**. The app scores available stocks using historical return, volatility/risk, and its existing price-trend projection. It displays the best-scoring sector, up to three stock picks, whole-share estimates for a budget, and charts.
5. These are educational model scenarios, not guaranteed outcomes. If a date range has too little history, the system falls back to the full available history; if data cannot be processed, the page displays an error.

### AI Investment Advisor Chatbot (💬)
Open **Ask AI**, ask a natural-language question about the project, and press **Send**. The model receives README sections relevant to the question, recent chat turns, and locally calculated stock metrics when relevant. It does not receive the project's source code. Ollama responses appear progressively as the local model generates them.

### News Sentiment Analysis (📰)
Choose a stock and click **Analyze Latest News**. The backend tries Yahoo Finance and then Google News RSS. Each fetched headline receives a transparent Positive / Negative / Neutral keyword score. If both news providers are unreachable or return no matching headlines, the page explains that rather than presenting zero sentiment counts as if they were meaningful. A working internet connection is required.

### Troubleshooting
- Run commands from the extracted project folder: `pip install -r requirements.txt`, then `python app.py`.
- Keep the terminal open while using the site. If a page shows an error, check the terminal for the detailed Python error.
- If the browser shows a login/session error, log in again and retry.
- If News Sentiment cannot load headlines, check internet access and try again later; the providers may rate-limit or temporarily change their feeds.

## Installation

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://127.0.0.1:5000`

5. **Access the Risk Analysis Dashboard**:
   - Register/Login to access the dashboard
   - Navigate to the "Risk Analysis" page to see the embedded advanced Streamlit dashboard

## User Registration & Login

1. **First Time Users**:
   - Visit the application
   - Click "Sign Up" on the login page
   - Create a username and password
   - Confirm password
   - Click "Create Account"

2. **Returning Users**:
   - Enter your username and password
   - Click "Sign In"

3. **Logout**:
   - Click the "Logout" button in the top navigation

## Data Management

- **Automatic Data Updates**: The system fetches stock data from Yahoo Finance
- **Dynamic Date Range**: Update data with custom start dates (end date is always current)
- **Sector Organization**: Stocks are organized by sectors for independent analysis

## Supported Stocks

### IT Sector
- INFY (Infosys)
- TCS (Tata Consultancy Services)
- WIPRO (Wipro)
- HCLTECH (HCL Technologies)

### Banking Sector
- HDFCBANK (HDFC Bank)
- SBIN (State Bank of India)
- ICICIBANK (ICICI Bank)
- AXISBANK (Axis Bank)

### Pharma Sector
- SUNPHARMA (Sun Pharmaceutical)
- CIPLA (Cipla)
- DRREDDY (Dr. Reddy's Laboratories)

### FMCG Sector
- HINDUNILVR (Hindustan Unilever)
- ITC (ITC Limited)
- NESTLEIND (Nestle India)
- BRITANNIA (Britannia Industries)

## Technical Stack

- **Backend**: Flask (Python) with integrated risk analysis engine
- **Advanced Analytics**: Custom risk calculation algorithms (volatility, predictive insights)
- **Frontend**: HTML, CSS, JavaScript with Chart.js for interactive visualizations
- **Data Analysis**: Pandas, NumPy, Scikit-learn for ML-based predictions
- **Visualization**: Chart.js (scatter plots), Streamlit (optional 3D visualizations)
- **Data Source**: Yahoo Finance (yfinance library)
- **Database**: SQLite
- **Security**: Werkzeug password hashing, Flask sessions

## Usage

1. **Update Data**: Use the sidebar to update stock data with your preferred start date
2. **Dashboard**: View market overview and AI insights
3. **Sector Analysis**: Click on sector cards for detailed analysis
4. **Risk Analysis**: Select a sector and click "Analyze Risk" to view comprehensive risk metrics, predictive insights, and interactive charts directly in the page
5. **Portfolio**: Select multiple stocks for optimization

### Advanced Risk Analysis Features
The risk analysis dashboard provides:
- **Risk Summary Cards**: Count of stocks by risk category (Low/Medium/High)
- **Risk Highlights**: Safest and riskiest stocks identification
- **Interactive Scatter Plot**: Risk vs Return analysis with bubble sizing by price
- **Predictive Insights**: AI-powered trend analysis for each stock
- **Detailed Metrics Table**: Comprehensive risk metrics with conditional formatting
- **3D Visualization Access**: Link to full Streamlit dashboard for advanced 3D charts

All features are now directly integrated into the main Flask application for seamless user experience.

## AI Features

- **Risk Assessment**: Volatility-based risk classification
- **Sector Intelligence**: Performance analysis and trend prediction
- **Portfolio Optimization**: Equal-weight allocation strategy
- **Market Insights**: Simulated AI-generated recommendations
- **Explainability and News Sentiment**: Transparent historical indicators and headline keyword scoring

## Security Features

- **Password Hashing**: Secure password storage using Werkzeug
- **Session Management**: Secure user sessions
- **Route Protection**: All sensitive routes require authentication
- **SQL Injection Prevention**: Parameterized queries
- **CSRF Protection**: Flask-WTF integration ready

## File Structure

```
├── app.py                 # Flask application with authentication
├── sector_analysis.py     # Sector analysis script
├── sector_analysis_streamlit.py # Advanced Streamlit risk analysis dashboard
├── update_data.py         # Data update script
├── users.db              # SQLite database (created automatically)
├── requirements.txt       # Python dependencies
├── templates/
│   ├── index.html         # Main dashboard (protected)
│   ├── login.html         # Login page
│   └── register.html      # Registration page
├── static/
│   ├── script.js          # Frontend JavaScript
│   ├── style.css          # CSS styling
│   ├── auth.css          # Authentication page styling
│   └── (generated charts) # Dynamic chart images
└── data/
    └── (sector_stock.csv) # Stock data files
```

## Notes

- This is a demonstration system for educational purposes
- Real trading decisions should not be based solely on this system
- The AI models are trained on historical data and may not predict future performance accurately
- Market data is fetched from Yahoo Finance and may have delays
- User credentials are stored securely in SQLite database

## Future Enhancements

- Real-time data integration
- Advanced portfolio optimization algorithms
- Sentiment analysis from news
- User authentication and portfolio tracking
- Mobile-responsive design improvements
- Email verification for registration
- Password reset functionality
- Two-factor authentication
## Investment Advisor: beginner-friendly workflow (updated)

1. Open **🤖 Investment Advisor** from the left sidebar.
2. Choose a sector, or leave **All Sectors** selected to compare the tracked sectors.
3. Enter an investment budget (for example, `10000`) to see whole-share estimates. The budget can be left blank if you only want stock rankings.
4. Select Low Risk, Balanced, or High Growth. The help text below the control explains each choice.
5. Optionally choose a start and end date. Leave them blank to use the available historical data.
6. Click **Generate Recommendation**. The app analyzes the data and shows the recommended/selected sector, ranked stocks, price and return estimates, risk, share quantities (if a budget was entered), and charts.
7. Read the “How to read these numbers” guide. Predicted prices and expected profit are estimates, not guarantees.

The advisor now waits for the user to click **Generate Recommendation** instead of automatically running while they are still changing fields. This makes the workflow easier to follow and prevents repeated background analysis while entering a budget.


## Ask AI setup

The floating **Ask AI** chat uses a language model with the project README, recent conversation turns, and locally calculated stock metrics as context. Choose one provider in `.env`.

### Free local option: Ollama

Ollama runs a model on your computer. It does not require an OpenAI API key or API billing, but uses local disk, memory, and processing power. Install Ollama from [ollama.com/download](https://ollama.com/download), then open PowerShell and download a model:
   ```powershell
   ollama pull llama3.2:3b
   ```
Copy `.env.example` to `.env` in the `mmupdate` folder and set:
   ```text
   AI_PROVIDER=ollama
   OLLAMA_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.2:3b
   ```
Keep Ollama running, restart Flask with `python app.py`, then use Ask AI. The first model response may take longer while the model loads; generation speed and answer quality depend on your computer.

### OpenAI option

Set `AI_PROVIDER=openai`, provide `OPENAI_API_KEY` and `OPENAI_MODEL=gpt-4o-mini` in `.env`, then restart Flask. OpenAI API usage may incur charges. Project documentation and stock metrics are sent to the selected model with each request; do not put private information in chat messages.

Install dependencies with `pip install -r requirements.txt`. The app loads `.env` automatically when it starts. Keep `.env` private and do not commit it.

## Premium theme layer (Dark / Light)

`static/theme.css` (loaded after the existing stylesheets) and `static/theme.js` add the FinTech-style
backgrounds, glass/solid card surfaces and chart re-theming for both modes. The toggle and the
`marketmind-theme` localStorage key are unchanged; login/register now have a toggle too.
No backend, route or data files were modified.


## User reviews and feedback system

See [README_REVIEWS.md](README_REVIEWS.md) for setup, PostgreSQL/SQLite configuration, admin dashboard, Ollama sentiment analysis, and Render deployment. The public form is available at `/reviews`; private administration is at `/admin/reviews`.
