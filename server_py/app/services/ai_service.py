"""
AI service module for generating cryptocurrency trading recommendations.
Uses OpenAI's GPT models to analyze portfolio and market data.
"""

from typing import Dict, List, Any
import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

class AIService:
    """
    Service class for generating AI-powered cryptocurrency trading recommendations.
    Utilizes OpenAI's GPT models to analyze portfolio composition and market trends.
    """

    _instance = None

    def __new__(cls):
        """Implement singleton pattern to ensure only one AI service instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initialize the AI service with OpenAI API credentials.
        Checks environment variables for API key and feature flag.
        """
        # Skip initialization if already done
        if hasattr(self, 'initialized'):
            return
            
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.enable_ai_recommendations = os.getenv("ENABLE_AI_RECOMMENDATIONS", "true").lower() == "true"
        
        if not self.api_key or self.api_key == "your_openai_api_key":
            logging.warning("Missing or invalid OPENAI_API_KEY")
            self.client = None
        else:
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                logging.info("Successfully initialized OpenAI client")
            except Exception as e:
                logging.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        
        self.initialized = True

    async def get_recommendations(self, portfolio: List[Dict[str, Any]], market_data: List[Dict[str, Any]]) -> str:
        """
        Generate cryptocurrency trading recommendations based on portfolio and market data.
        
        Args:
            portfolio: List of dictionaries containing current holdings
            market_data: List of dictionaries containing price and historical data
        
        Returns:
            String containing newline-separated recommendations
        """
        if not self.enable_ai_recommendations:
            return "AI recommendations are disabled. Please enable them in the .env file."

        if not self.client:
            return "AI recommendations are not available. Please check your OPENAI_API_KEY configuration."

        try:
            prompt = f"""As a cryptocurrency expert analyst, provide specific buy, sell, or hold recommendations based on the following portfolio and market data:

Portfolio: {portfolio}
Recent Market Data: {market_data}

Please analyze the current market conditions, trends, and portfolio composition to provide:
1. Specific recommendations for each holding
2. Potential new investments to consider
3. Risk assessment
4. Market trend analysis

Provide concise, actionable insights."""

            response = await self.client.chat.completions.create(
                model="gpt-4.1",
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
            logging.error(f"OpenAI API error: {e}")
            return "Unable to generate recommendations at this time. Please try again later."