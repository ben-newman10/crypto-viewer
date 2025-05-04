import os
from typing import List, Dict, Any
from openai import AsyncOpenAI

class AIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key":
            print("Warning: Missing or invalid OPENAI_API_KEY")
        else:
            self.client = AsyncOpenAI(api_key=api_key)

    async def get_recommendations(self, portfolio: List[Dict[str, Any]], market_data: List[Dict[str, Any]]) -> str:
        if not hasattr(self, 'client'):
            return "AI recommendations are not available. Please configure your OPENAI_API_KEY in the .env file."

        prompt = f"""As a cryptocurrency expert analyst, provide specific buy, sell, or hold recommendations based on the following portfolio and market data:

Portfolio: {portfolio}
Recent Market Data: {market_data}

Please analyze the current market conditions, trends, and portfolio composition to provide:
1. Specific recommendations for each holding
2. Potential new investments to consider
3. Risk assessment
4. Market trend analysis

Provide concise, actionable insights."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency analyst with deep knowledge of market trends, technical analysis, and risk management."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return "Unable to generate recommendations at this time. Please try again later."