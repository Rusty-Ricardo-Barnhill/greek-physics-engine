# Greek Physics Options Engine
The Greek Physics Options Engine is a high-performance, stateless REST API that calculates advanced second-order options Greeks and structural Gamma Exposure (GEX).

🌟 Highlights

⚡ Lightning Fast: Built on FastAPI for asynchronous, rapid-fire calculations.

🧠 Advanced Kinetics: Calculates Delta, Gamma, and crucial second-order Greeks (Vanna, Charm, Vomma).

⚖️ True Dealer Exposure: Computes absolute Gamma Exposure (GEX) dollar values by weighting against Open Interest.

📦 Batch Processing: Send entire options chains in a single payload for instant structural mapping (Call Walls, Put Walls, GEX Flips).

🔌 Stateless & Portable: Zero database required. Feed it raw telemetry, get back pure physics.

ℹ️ Overview

Most open-source financial libraries (like yfinance) are great for pulling raw prices, but they fall short when you need to calculate the structural gravity of the options market. Calculating Net GEX, Call Walls, and second-order metrics like Charm (time-decay of Delta) and Vanna (volatility impact on Delta) usually requires building clunky, bloated quantitative platforms from scratch.

This engine solves that friction point. It is a lightweight, mathematically rigorous API wrapper around Black-Scholes and Merton jump-diffusion math. It acts as a translation layer: you feed it raw JSON arrays of options data, and it instantly returns the underlying Market Maker exposure. Whether you are building an automated trading algorithm, a Discord bot, or a personal charting dashboard, this API acts as the quantitative brain for your operations.

✍️ Author: Engineered by Ricardo for the Aegis protocol.

⬇️ Installation

The engine requires Python 3.8+ and relies on a few core data science libraries.

Clone the repository and install the required dependencies:

git clone [https://github.com/yourusername/greek-physics-engine.git](https://github.com/yourusername/greek-physics-engine.git)
cd greek-physics-engine
pip install fastapi uvicorn scipy numpy pydantic yfinance


To boot the engine locally:

uvicorn greek_engine:app --reload


The engine will spin up on http://127.0.0.1:8000.

🚀 Usage

Once the server is running, FastAPI automatically generates a beautiful, interactive Swagger UI where you can test payloads directly in your browser. Just navigate to: http://127.0.0.1:8000/docs

If you are wiring this into a Python trading bot, hitting the API is incredibly simple. Here is a minimal example of calculating the gravity of a single 0-DTE option:

import requests

# Target: NVDA $210 Put (0-DTE)
payload = {
  "put_call": "P",
  "spot": 212.50,
  "strike": 210.00,
  "tte": 0.0013,       # Time to Expiry in years (e.g., Half-day / 0-DTE)
  "iv": 0.1514,        # 15.14% Implied Volatility
  "rfr": 0.053,        # 5.3% Risk-Free Rate
  "open_interest": 7859
}

response = requests.post("[http://127.0.0.1:8000/api/v1/greeks/single](http://127.0.0.1:8000/api/v1/greeks/single)", json=payload)
greeks = response.json()

print(f"Delta: {greeks['delta']}")
print(f"Charm: {greeks['charm']}")
print(f"Total GEX: ${greeks['gex']:,.2f}")


Note: For dynamic structural mapping, you can use the /api/v1/greeks/nodes endpoint to automatically fetch live yfinance data and return the exact strike coordinates for Max Pain, Call Walls, and GEX Flips.

💭 Feedback and Contributions

If you find this engine useful for your own algorithmic trading, or if you spot a mathematical optimization that could reduce compute latency, I'd love to hear about it!

Have a question or a feature idea? Please start a Discussion.

Found a bug in the math? Open an Issue.

Want to contribute? Feel free to fork the repository and submit a Pull Request.

Happy hunting.

📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
