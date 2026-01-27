"""
Kalshi API Client

Provides methods to interact with Kalshi's trading API, including
fetching market data, portfolio information, and placing trades.
"""

import requests
from typing import Dict, List, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from kalshi_auth import KalshiAuth


class KalshiClient:
    """Client for interacting with the Kalshi prediction market API."""
    
    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        base_url: str = "https://api.elections.kalshi.com",
        timeout: int = 15,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        """
        Initialize Kalshi API client.
        
        Args:
            api_key_id: Your Kalshi API key ID
            private_key_path: Path to your private key file
            base_url: Kalshi API base URL (production or demo)
            timeout: Request timeout in seconds
            max_retries: Max retry attempts for transient errors
            backoff_factor: Exponential backoff factor between retries
        """
        self.base_url = base_url.rstrip('/')
        self.auth = KalshiAuth(api_key_id, private_key_path)
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST", "DELETE"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def _request(self, method: str, path: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> requests.Response:
        """
        Make an authenticated request to the Kalshi API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters
            json_data: JSON body for POST requests
            
        Returns:
            Response object
        """
        headers = self.auth.get_headers(method, path)
        url = self.base_url + path
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            timeout=self.timeout,
        )
        
        response.raise_for_status()
        return response
    
    def get_balance(self) -> Dict:
        """Get account balance."""
        response = self._request('GET', '/trade-api/v2/portfolio/balance')
        return response.json()

    def get_exchange_status(self) -> Dict:
        """Get exchange status."""
        response = self._request('GET', '/trade-api/v2/exchange/status')
        return response.json()
    
    def get_markets(
        self,
        ticker: Optional[str] = None,
        status: str = 'open',
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict:
        """
        Get market information.
        
        Args:
            ticker: Optional market ticker to filter by
            status: Market status (open, closed, settled)
            series_ticker: Optional series ticker to filter by
            event_ticker: Optional event ticker to filter by
            limit: Optional max results per page
            cursor: Optional pagination cursor
            
        Returns:
            Market data
        """
        params = {'status': status}
        if ticker:
            params['ticker'] = ticker
        if series_ticker:
            params['series_ticker'] = series_ticker
        if event_ticker:
            params['event_ticker'] = event_ticker
        if limit:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        
        response = self._request('GET', '/trade-api/v2/markets', params=params)
        return response.json()
    
    def get_market(self, ticker: str) -> Dict:
        """
        Get detailed information for a specific market.
        
        Args:
            ticker: Market ticker (e.g., 'KXHIGHMIA-26JAN26')
            
        Returns:
            Detailed market data
        """
        response = self._request('GET', f'/trade-api/v2/markets/{ticker}')
        return response.json()
    
    def get_market_orderbook(self, ticker: str, depth: int = 10) -> Dict:
        """
        Get the order book for a market showing bids and asks.
        
        Args:
            ticker: Market ticker
            depth: Number of price levels to return
            
        Returns:
            Order book data with bids and asks
        """
        params = {'depth': depth}
        response = self._request('GET', f'/trade-api/v2/markets/{ticker}/orderbook', params=params)
        return response.json()
    
    def get_series(self, series_ticker: str) -> Dict:
        """
        Get information about a market series.
        
        Args:
            series_ticker: Series ticker (e.g., 'KXHIGHMIA')
            
        Returns:
            Series information including all contracts
        """
        response = self._request('GET', f'/trade-api/v2/series/{series_ticker}')
        return response.json()
    
    def get_positions(self) -> Dict:
        """Get current portfolio positions."""
        response = self._request('GET', '/trade-api/v2/portfolio/positions')
        return response.json()
    
    def get_orders(self, ticker: Optional[str] = None, status: Optional[str] = None) -> Dict:
        """
        Get orders with optional filtering.
        
        Args:
            ticker: Optional market ticker to filter by
            status: Optional order status (pending, active, executed, etc.)
            
        Returns:
            Orders data
        """
        params = {}
        if ticker:
            params['ticker'] = ticker
        if status:
            params['status'] = status
        
        response = self._request('GET', '/trade-api/v2/portfolio/orders', params=params)
        return response.json()
    
    def place_order(self, ticker: str, action: str, side: str, count: int, 
                    order_type: str = 'limit', yes_price: Optional[int] = None,
                    no_price: Optional[int] = None) -> Dict:
        """
        Place an order on a market.
        
        Args:
            ticker: Market ticker
            action: 'buy' or 'sell'
            side: 'yes' or 'no'
            count: Number of contracts
            order_type: 'limit' or 'market'
            yes_price: Limit price for yes side (in cents, 1-99)
            no_price: Limit price for no side (in cents, 1-99)
            
        Returns:
            Order confirmation data
        """
        order_data = {
            'ticker': ticker,
            'action': action,
            'side': side,
            'count': count,
            'type': order_type
        }
        
        if order_type == 'limit':
            if yes_price is not None:
                order_data['yes_price'] = yes_price
            if no_price is not None:
                order_data['no_price'] = no_price
        
        response = self._request('POST', '/trade-api/v2/portfolio/orders', json_data=order_data)
        return response.json()
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            Cancellation confirmation
        """
        response = self._request('DELETE', f'/trade-api/v2/portfolio/orders/{order_id}')
        return response.json()
