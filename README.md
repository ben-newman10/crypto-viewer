# Crypto Viewer

Crypto Viewer is a web application built with React, TypeScript, and Vite for tracking cryptocurrency portfolios and prices. It includes a Python FastAPI backend that interfaces with the Coinbase Advanced Trade API for real-time data and OpenAI for AI-powered crypto analysis and recommendations.

![Crypto Dashboard Viewer](dashboard.png)

## Features

- View your cryptocurrency portfolio with real-time updates (30-second refresh)
- Fetch live cryptocurrency prices with 24-hour change indicators
- Get AI-powered cryptocurrency recommendations based on your portfolio
- Responsive design using Chakra UI components
- Real-time integration with Coinbase Advanced Trade API
- Historical price data visualization

## Prerequisites

Before you begin, ensure you have the following installed:

- [Node.js](https://nodejs.org/) (version 16 or higher)
- [Python](https://www.python.org/) (version 3.9 or higher)
- [Git](https://git-scm.com/) for version control

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/crypto-viewer.git
cd crypto-viewer
```

### 2. Install Frontend Dependencies

Install the required dependencies in the root directory:

```bash
npm install
```

### 3. Set Up the Backend

Navigate to the backend directory and set up a Python virtual environment:

```bash
cd server_py
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the `server_py` directory with the following variables:

```env
COINBASE_API_KEY=your_coinbase_api_key
COINBASE_API_SECRET=your_coinbase_api_secret
OPENAI_API_KEY=your_openai_api_key
```

Replace the placeholder values with your actual API credentials:
- Get Coinbase API credentials from [Coinbase Developer Portal](https://docs.cloud.coinbase.com/advanced-trade-api/docs/rest-api-auth)
- Get OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys)

## Running the Application

### 1. Start the Backend Server

Run the following command in the `server_py` directory:

```bash
cd server_py
source venv/bin/activate  # On Windows: venv\Scripts\activate
python run.py
```

The backend server will start at `http://127.0.0.1:3001`.

### 2. Start the Frontend Development Server

Navigate back to the root directory and start the frontend:

```bash
npm run dev
```

The frontend will be available at `http://127.0.0.1:5173`.

### 3. One-Command Development Setup

Alternatively, you can start both frontend and backend simultaneously from the root directory:

```bash
npm run dev
```

This command automatically starts both the backend server and frontend development server.

## API Endpoints

The backend provides the following API endpoints:

- **GET /api/crypto/portfolio**: Fetches the user's cryptocurrency portfolio with balances
- **GET /api/crypto/price/{product_id}**: Fetches current price for a trading pair (e.g., BTC-GBP)
- **GET /api/crypto/historical/{product_id}**: Fetches historical price data for a trading pair
- **GET /api/recommendations/**: Generates AI-powered cryptocurrency recommendations
- **GET /api/recommendations/analysis**: Provides detailed AI analysis of portfolio and market data

## Development

### Linting and Formatting

- Run ESLint for linting:

  ```bash
  npm run lint
  ```

### Testing

- Backend tests can be run using `pytest`:

  ```bash
  cd server_py
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pytest
  ```

  Run specific test files:
  ```bash
  pytest test_ai_service.py
  pytest test_coinbase_service.py
  pytest test_crypto_router.py
  pytest test_recommendations_router.py
  ```

## Deployment

To deploy the application, build the frontend and serve it with the backend:

1. Build the frontend:

   ```bash
   npm run build
   ```

2. The built files will be in the `dist` directory.

3. Deploy the backend using a production server like Gunicorn:

   ```bash
   cd server_py
   pip install gunicorn
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m 'Add feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Coinbase Advanced Trade API](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)
- [Chakra UI](https://chakra-ui.com/)
- [React Query](https://tanstack.com/query/latest)
- [Chart.js](https://www.chartjs.org/)
