import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import json

# Sector definitions
SECTORS = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}

class AdvancedRiskAnalyzer:
    def __init__(self):
        self.scaler = StandardScaler()

    def assign_dynamic_risk_categories(self, stock_analyses):
        """Assign Low/Medium/High based on volatility distribution."""
        if not stock_analyses:
            return

        volatilities = [s["volatility"] for s in stock_analyses]
        unique_vols = len(set(volatilities))

        # If the spread is too narrow, keep absolute fallback buckets.
        if unique_vols < 3:
            for stock in stock_analyses:
                if stock["volatility"] < 0.18:
                    stock["risk_category"] = "Low"
                elif stock["volatility"] < 0.32:
                    stock["risk_category"] = "Medium"
                else:
                    stock["risk_category"] = "High"
            return

        low_cutoff = np.percentile(volatilities, 33)
        high_cutoff = np.percentile(volatilities, 66)

        for stock in stock_analyses:
            vol = stock["volatility"]
            if vol <= low_cutoff:
                stock["risk_category"] = "Low"
            elif vol <= high_cutoff:
                stock["risk_category"] = "Medium"
            else:
                stock["risk_category"] = "High"
        
    def calculate_volatility(self, prices):
        """Calculate daily volatility and annualized volatility"""
        if len(prices) < 2:
            return 0, 0
        
        daily_returns = prices.pct_change().dropna()
        daily_vol = daily_returns.std()
        annualized_vol = daily_vol * np.sqrt(252)  # Annualized volatility
        
        return daily_vol, annualized_vol
    
    def calculate_var(self, returns, confidence_level=0.05):
        """Calculate Value at Risk (VaR)"""
        if len(returns) == 0:
            return 0
        return np.percentile(returns, confidence_level * 100)
    
    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """Calculate Sharpe Ratio"""
        if len(returns) == 0 or returns.std() == 0:
            return 0
        excess_returns = returns - risk_free_rate/252
        return np.sqrt(252) * excess_returns.mean() / returns.std()
    
    def calculate_max_drawdown(self, prices):
        """Calculate Maximum Drawdown"""
        if len(prices) < 2:
            return 0
        
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        return drawdown.min()
    
    def calculate_beta(self, stock_returns, market_returns):
        """Calculate Beta relative to market"""
        if len(stock_returns) < 2 or len(market_returns) < 2:
            return 1.0  # Default beta
        
        covariance = np.cov(stock_returns, market_returns)[0][1]
        market_variance = np.var(market_returns)
        
        if market_variance == 0:
            return 1.0
        
        return covariance / market_variance
    
    def generate_predictive_insight(self, prices, volatility, trend_days=7):
        """Generate predictive insights based on historical patterns"""
        if len(prices) < trend_days * 2:
            return {
                "trend": "insufficient_data",
                "predicted_move": 0,
                "confidence": "Low",
                "insight": "Insufficient historical data for reliable prediction"
            }
        
        # Recent trend analysis
        recent_prices = prices.tail(trend_days)
        recent_returns = recent_prices.pct_change().dropna()
        
        # Historical pattern analysis
        historical_returns = prices.pct_change().dropna()
        
        # Trend detection
        avg_recent_return = recent_returns.mean()
        if avg_recent_return > 0.005:  # > 0.5% daily return
            trend = "bullish"
        elif avg_recent_return < -0.005:  # < -0.5% daily return
            trend = "bearish"
        else:
            trend = "sideways"
        
        # Predict next week's movement based on recent volatility and trend
        predicted_daily_move = avg_recent_return
        predicted_weekly_move = predicted_daily_move * trend_days
        
        # Confidence based on volatility + trend consistency.
        # Prior formula pushed almost everything to Low for normal market vols (~0.20-0.35).
        trend_consistency = (recent_returns > 0).mean() if avg_recent_return >= 0 else (recent_returns < 0).mean()
        consistency_boost = (trend_consistency - 0.5) * 0.3  # -0.15 to +0.15 range
        adjusted_volatility = volatility - consistency_boost

        if adjusted_volatility < 0.18:
            confidence = "High"
        elif adjusted_volatility < 0.30:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        # Generate insight text
        if trend == "bullish":
            insight = f"Stock showing upward momentum with {predicted_weekly_move*100:.1f}% expected gain over next {trend_days} days"
        elif trend == "bearish":
            insight = f"Stock showing downward pressure with {abs(predicted_weekly_move)*100:.1f}% expected decline over next {trend_days} days"
        else:
            insight = f"Stock trading sideways with minimal movement expected over next {trend_days} days"
        
        return {
            "trend": trend,
            "predicted_move": predicted_weekly_move * 100,  # Convert to percentage
            "confidence": confidence,
            "insight": insight
        }
    
    def analyze_stock_risk(self, stock_data, stock_symbol):
        """Comprehensive risk analysis for a single stock"""
        if stock_data.empty or len(stock_data) < 30:
            return None
        
        prices = stock_data['Close']
        returns = prices.pct_change().dropna()
        
        # Basic metrics
        daily_vol, annual_vol = self.calculate_volatility(prices)
        var_5 = self.calculate_var(returns, 0.05)
        sharpe = self.calculate_sharpe_ratio(returns)
        max_dd = self.calculate_max_drawdown(prices)
        
        # Predictive insights
        predictive = self.generate_predictive_insight(prices, annual_vol)
        
        # Risk classification
        if annual_vol < 0.2:
            risk_category = "Low"
        elif annual_vol < 0.4:
            risk_category = "Medium"
        else:
            risk_category = "High"
        
        # Additional metrics
        current_price = prices.iloc[-1]
        avg_price = prices.mean()
        price_range = prices.max() - prices.min()
        
        return {
            "symbol": stock_symbol.replace('.NS', ''),
            "risk_category": risk_category,
            "volatility": round(annual_vol, 4),
            "daily_volatility": round(daily_vol, 4),
            "var_5": round(var_5 * 100, 2),  # Convert to percentage
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_dd * 100, 2),  # Convert to percentage
            "current_price": round(current_price, 2),
            "avg_price": round(avg_price, 2),
            "price_range": round(price_range, 2),
            "percent_return": round(((current_price - prices.iloc[0]) / prices.iloc[0]) * 100, 2),
            "predictive_insight": predictive,
            "total_return": round(((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]) * 100, 2)
        }
    
    def analyze_sector_risk(self, sector):
        """Analyze risk for all stocks in a sector or all sectors"""
        if sector == "All":
            # Analyze all sectors
            all_stock_analyses = []
            all_risk_counts = {"Low": 0, "Medium": 0, "High": 0}
            total_volatility = 0
            total_return = 0
            
            for sector_name in SECTORS.keys():
                sector_result = self._analyze_single_sector(sector_name)
                if "error" not in sector_result:
                    all_stock_analyses.extend(sector_result["stock_analyses"])
                    for risk_level, count in sector_result["risk_counts"].items():
                        all_risk_counts[risk_level] += count
                    total_volatility += sector_result["avg_volatility"]
                    total_return += sector_result["avg_return"]
            
            if not all_stock_analyses:
                return {"error": "No valid data available for any sector"}
            
            # Calculate overall metrics
            avg_volatility = total_volatility / len(SECTORS)
            avg_return = total_return / len(SECTORS)
            
            # Find safest and riskiest across all sectors
            safest_stock = min(all_stock_analyses, key=lambda x: x["volatility"])["symbol"]
            riskiest_stock = max(all_stock_analyses, key=lambda x: x["volatility"])["symbol"]
            
            # Generate overall sector insight
            sector_insight = self.generate_overall_insight(all_stock_analyses, avg_volatility, avg_return)
            
            return {
                "sector": "All",
                "stock_analyses": all_stock_analyses,
                "risk_counts": all_risk_counts,
                "avg_volatility": avg_volatility,
                "avg_return": avg_return,
                "safest_stock": safest_stock,
                "riskiest_stock": riskiest_stock,
                "sector_insight": sector_insight,
                "total_stocks": len(all_stock_analyses)
            }
        else:
            return self._analyze_single_sector(sector)
    
    def _analyze_single_sector(self, sector):
        """Analyze risk for a single sector"""
        if sector not in SECTORS:
            return {"error": "Invalid sector"}
        
        stocks = SECTORS[sector]
        stock_analyses = []
        
        for stock in stocks:
            filename = f"data/{sector}_{stock}.csv"
            if os.path.exists(filename):
                try:
                    df = pd.read_csv(filename)
                    if not df.empty and 'Close' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'])
                        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                        df = df.dropna(subset=['Close', 'Date'])
                        df = df.sort_values('Date')
                        
                        analysis = self.analyze_stock_risk(df, stock)
                        if analysis:
                            stock_analyses.append(analysis)
                except Exception as e:
                    print(f"Error analyzing {stock}: {e}")
                    continue
        
        if not stock_analyses:
            return {"error": f"No valid data available for {sector} sector"}
        
        # Re-assign risk categories dynamically per analyzed set
        self.assign_dynamic_risk_categories(stock_analyses)

        # Sector-level metrics
        risk_counts = {"Low": 0, "Medium": 0, "High": 0}
        total_volatility = 0
        total_return = 0
        
        safest_stock = None
        riskiest_stock = None
        min_volatility = float('inf')
        max_volatility = 0
        
        for analysis in stock_analyses:
            risk_counts[analysis["risk_category"]] += 1
            total_volatility += analysis["volatility"]
            total_return += analysis["total_return"]
            
            if analysis["volatility"] < min_volatility:
                min_volatility = analysis["volatility"]
                safest_stock = analysis["symbol"]
            
            if analysis["volatility"] > max_volatility:
                max_volatility = analysis["volatility"]
                riskiest_stock = analysis["symbol"]
        
        avg_volatility = total_volatility / len(stock_analyses)
        avg_return = total_return / len(stock_analyses)
        
        # Generate sector-level insights
        sector_insight = self.generate_sector_insight(sector, stock_analyses, avg_volatility, avg_return)
        
        return {
            "sector": sector,
            "stock_analyses": stock_analyses,
            "risk_counts": risk_counts,
            "avg_volatility": round(avg_volatility, 4),
            "avg_return": round(avg_return, 2),
            "safest_stock": safest_stock,
            "riskiest_stock": riskiest_stock,
            "sector_insight": sector_insight,
            "total_stocks": len(stock_analyses)
        }
    
    def generate_overall_insight(self, all_stock_analyses, avg_volatility, avg_return):
        """Generate overall market insight for all sectors"""
        risk_distribution = f"Risk distribution: {sum(1 for s in all_stock_analyses if s['risk_category'] == 'Low')} Low, {sum(1 for s in all_stock_analyses if s['risk_category'] == 'Medium')} Medium, {sum(1 for s in all_stock_analyses if s['risk_category'] == 'High')} High"
        
        if avg_volatility < 0.25:
            risk_profile = "conservative"
            outlook = "stable"
        elif avg_volatility < 0.4:
            risk_profile = "moderate"
            outlook = "balanced"
        else:
            risk_profile = "aggressive"
            outlook = "volatile"
        
        bullish_stocks = sum(1 for s in all_stock_analyses if s['predictive_insight']['trend'] == 'bullish')
        bearish_stocks = sum(1 for s in all_stock_analyses if s['predictive_insight']['trend'] == 'bearish')
        
        sentiment = "bullish" if bullish_stocks > bearish_stocks else "bearish" if bearish_stocks > bullish_stocks else "neutral"
        
        insight = f"Overall market shows {risk_profile} risk profile with {outlook} outlook. {risk_distribution}. Current sentiment is {sentiment} with {bullish_stocks} stocks showing bullish trends and {bearish_stocks} showing bearish trends."
        
        return {
            "risk_profile": risk_profile,
            "outlook": outlook,
            "sentiment": sentiment,
            "insight_text": insight,
            "bullish_count": bullish_stocks,
            "bearish_count": bearish_stocks,
            "neutral_count": len(all_stock_analyses) - bullish_stocks - bearish_stocks
        }
    
    def generate_sector_insight(self, sector, stock_analyses, avg_volatility, avg_return):
        """Generate sector-level predictive insights"""
        risk_distribution = f"Risk distribution: {sum(1 for s in stock_analyses if s['risk_category'] == 'Low')} Low, {sum(1 for s in stock_analyses if s['risk_category'] == 'Medium')} Medium, {sum(1 for s in stock_analyses if s['risk_category'] == 'High')} High"
        
        if avg_volatility < 0.25:
            risk_profile = "conservative"
            outlook = "stable"
        elif avg_volatility < 0.4:
            risk_profile = "moderate"
            outlook = "balanced"
        else:
            risk_profile = "aggressive"
            outlook = "volatile"
        
        bullish_stocks = sum(1 for s in stock_analyses if s['predictive_insight']['trend'] == 'bullish')
        bearish_stocks = sum(1 for s in stock_analyses if s['predictive_insight']['trend'] == 'bearish')
        
        sentiment = "bullish" if bullish_stocks > bearish_stocks else "bearish" if bearish_stocks > bullish_stocks else "neutral"
        
        insight = f"{sector} sector shows {risk_profile} risk profile with {outlook} outlook. {risk_distribution}. Current sentiment is {sentiment} with {bullish_stocks} stocks showing bullish trends and {bearish_stocks} showing bearish trends."
        
        return {
            "risk_profile": risk_profile,
            "outlook": outlook,
            "sentiment": sentiment,
            "insight_text": insight,
            "bullish_count": bullish_stocks,
            "bearish_count": bearish_stocks,
            "neutral_count": len(stock_analyses) - bullish_stocks - bearish_stocks
        }

def main():
    analyzer = AdvancedRiskAnalyzer()
    
    # Example usage
    sector = "IT"
    result = analyzer.analyze_sector_risk(sector)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
