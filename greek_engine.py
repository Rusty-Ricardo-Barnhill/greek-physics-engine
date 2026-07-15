from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import numpy as np
import pandas as pd
from scipy.stats import norm
import math
import yfinance as yf
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# ==========================================
# FASTAPI APP INITIALIZATION
# ==========================================
app = FastAPI(
    title="Greek Physics Options Engine",
    description="A high-performance, stateless API for calculating second-order Greeks and Gamma Exposure (GEX).",
    version="1.1.0"
)

# ==========================================
# DATA MODELS (PYDANTIC)
# ==========================================
class OptionRequest(BaseModel):
    put_call: str = Field(..., description="'C' for Call, 'P' for Put")
    spot: float = Field(..., gt=0, description="Current price of the underlying asset")
    strike: float = Field(..., gt=0, description="Strike price of the option")
    tte: float = Field(..., gt=0, description="Time to expiration in years (e.g., 1-DTE = 1/252 = 0.0039)")
    iv: float = Field(..., gt=0, description="Implied Volatility as a decimal (e.g., 40% = 0.40)")
    rfr: float = Field(0.053, description="Risk-Free Rate as a decimal (Default: 5.3%)")
    open_interest: Optional[int] = Field(1, description="Number of open contracts (Used for GEX calculation)")

class GreekResponse(BaseModel):
    delta: float
    gamma: float
    vanna: float
    charm: float
    vomma: float
    gex: float

class ChainRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol (e.g., NVDA, SPY)")
    expiry: Optional[str] = Field(None, description="Expiration date (YYYY-MM-DD). If omitted, pulls nearest expiration.")

class GexNodeResponse(BaseModel):
    ticker: str
    spot_price: float
    expiry: str
    max_pain: float
    call_wall: float
    put_wall: float
    gex_flip: float
    net_gex_mil: float

# ==========================================
# QUANTITATIVE PHYSICS ENGINE
# ==========================================
def calculate_d1_d2(S: float, K: float, T: float, r: float, iv: float):
    """Calculates the standard d1 and d2 parameters for Black-Scholes."""
    d1 = (math.log(S / K) + (r + 0.5 * iv**2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    return d1, d2

def calculate_gamma(spot_price: float, strike: float, T: float, risk_free_rate: float, impliedVolatility: float):
    """Standalone Gamma calculation for vectorized chain processing."""
    if impliedVolatility <= 0 or T <= 0: return 0.0
    d1 = (math.log(spot_price / strike) + (risk_free_rate + 0.5 * impliedVolatility**2) * T) / (impliedVolatility * math.sqrt(T))
    return norm.pdf(d1) / (spot_price * impliedVolatility * math.sqrt(T))

def get_greeks(req: OptionRequest) -> GreekResponse:
    """Calculates all primary and second-order greeks for a given option."""
    S, K, T, r, iv = req.spot, req.strike, req.tte, req.rfr, req.iv
    
    # Prevent division by zero mathematically
    if T <= 0.0001: T = 0.0001
    if iv <= 0.01: iv = 0.01

    d1, d2 = calculate_d1_d2(S, K, T, r, iv)

    # 1. DELTA (Directional Exposure)
    if req.put_call.upper() == 'C':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1.0

    # 2. GAMMA (Acceleration of Delta)
    gamma = norm.pdf(d1) / (S * iv * math.sqrt(T))

    # 3. VANNA (Sensitivity of Delta to Implied Volatility)
    vanna = -norm.pdf(d1) * d2 / iv

    # 4. CHARM (Sensitivity of Delta to Time Decay)
    charm = -norm.pdf(d1) * ((r / (iv * math.sqrt(T))) - (d2 / (2 * T)))
    if req.put_call.upper() == 'P':
        charm += r * math.exp(-r * T) # Put adjustment

    # 5. VOMMA (Volatility of Volatility)
    vega = S * math.sqrt(T) * norm.pdf(d1)
    vomma = vega * (d1 * d2) / iv

    # 6. GEX (Gamma Exposure)
    raw_gex = gamma * req.open_interest * 100 * S
    gex = raw_gex if req.put_call.upper() == 'C' else -raw_gex

    return GreekResponse(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        vanna=round(vanna, 6),
        charm=round(charm, 6),
        vomma=round(vomma, 6),
        gex=round(gex, 2)
    )

# ==========================================
# API ENDPOINTS
# ==========================================
@app.post("/api/v1/greeks/single", response_model=GreekResponse, tags=["Options Physics"])
async def calculate_single_option(request: OptionRequest):
    """
    Calculates the exact Greek payload for a single options contract.
    """
    try:
        return get_greeks(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Physics calculation failed: {str(e)}")

@app.post("/api/v1/greeks/batch", response_model=List[GreekResponse], tags=["Options Physics"])
async def calculate_batch_options(requests: List[OptionRequest]):
    """
    Process an entire array of options simultaneously.
    """
    try:
        return [get_greeks(req) for req in requests]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Batch physics calculation failed: {str(e)}")

@app.post("/api/v1/greeks/nodes", response_model=GexNodeResponse, tags=["Structural Mapping"])
async def calculate_gex_nodes(request: ChainRequest):
    """
    Dynamically fetches options data via yfinance for a specific ticker and expiration,
    calculating the absolute structural boundaries: Max Pain, Call Wall, Put Wall, and GEX Flip.
    """
    try:
        tkr = yf.Ticker(request.ticker.upper())
        
        # Fetch Spot Price
        spot = tkr.fast_info.get('lastPrice')
        if not spot:
            hist = tkr.history(period="1d")
            if hist.empty:
                raise ValueError(f"Could not fetch spot price for {request.ticker}.")
            spot = hist['Close'].iloc[-1]
            
        # Fetch Expirations
        expirations = tkr.options
        if not expirations:
            raise ValueError(f"No options chains available for {request.ticker}.")
            
        target_expiry = request.expiry if request.expiry else expirations[0]
        if target_expiry not in expirations:
            raise ValueError(f"Expiry '{target_expiry}' not found. Available: {expirations[:3]}...")
            
        # Fetch Chain
        chain = tkr.option_chain(target_expiry)
        calls = chain.calls
        puts = chain.puts
        
        if calls.empty or puts.empty:
            raise ValueError("Options chain is empty for this expiration.")
            
        # Calculate Time to Expiry (TTE)
        exp_date = datetime.strptime(target_expiry, '%Y-%m-%d').date()
        today = datetime.now().date()
        days_to_expiry = (exp_date - today).days
        tte = max(days_to_expiry / 252.0, 0.0013) # Prevent div by zero
        rfr = 0.053
        
        # Calculate GEX for all rows
        calls['Gamma'] = calls.apply(lambda r: calculate_gamma(spot, r['strike'], tte, rfr, max(r['impliedVolatility'], 0.01)), axis=1)
        calls['GEX'] = calls['Gamma'] * calls['openInterest'].fillna(0) * 100 * spot
        
        puts['Gamma'] = puts.apply(lambda r: calculate_gamma(spot, r['strike'], tte, rfr, max(r['impliedVolatility'], 0.01)), axis=1)
        puts['GEX'] = -puts['Gamma'] * puts['openInterest'].fillna(0) * 100 * spot
        
        # Aggregate Profile
        gex_profile = pd.concat([
            calls[['strike', 'GEX']].rename(columns={'GEX': 'Call_GEX'}),
            puts[['strike', 'GEX']].rename(columns={'GEX': 'Put_GEX'})
        ]).groupby('strike').sum().fillna(0)
        
        gex_profile['Net_GEX'] = gex_profile['Call_GEX'] + gex_profile['Put_GEX']
        
        # Find Structural Walls
        call_wall = float(gex_profile['Call_GEX'].idxmax())
        put_wall = float(gex_profile['Put_GEX'].idxmin())
        
        # Find GEX Flip
        search_range = gex_profile.loc[min(put_wall, call_wall) : max(put_wall, call_wall)]
        gex_flip = float(search_range['Net_GEX'].abs().idxmin()) if not search_range.empty else spot
        
        # Find Max Pain
        all_strikes = sorted(list(set(calls['strike'].tolist() + puts['strike'].tolist())))
        pain_levels = {}
        for s in all_strikes:
            call_intrinsic = np.maximum(0, s - calls['strike']) * calls['openInterest'].fillna(0)
            put_intrinsic = np.maximum(0, puts['strike'] - s) * puts['openInterest'].fillna(0)
            pain_levels[s] = call_intrinsic.sum() + put_intrinsic.sum()
            
        max_pain = float(min(pain_levels, key=pain_levels.get)) if pain_levels else spot
        
        net_gex_mil = gex_profile['Net_GEX'].sum() / 1_000_000

        return GexNodeResponse(
            ticker=request.ticker.upper(),
            spot_price=round(spot, 2),
            expiry=target_expiry,
            max_pain=max_pain,
            call_wall=call_wall,
            put_wall=put_wall,
            gex_flip=gex_flip,
            net_gex_mil=round(net_gex_mil, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health", tags=["System"])
async def health_check():
    """Confirms the API engine is awake and ready to process matrices."""
    return {"status": "ONLINE", "module": "Greek Physics Engine"}