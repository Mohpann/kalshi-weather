"""
Kalshi API Authentication Module

Handles loading private keys and signing requests according to Kalshi's
authentication requirements using RSA-PSS with SHA256.
"""

import base64
import datetime
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAuth:
    """Manages authentication for Kalshi API requests."""
    
    def __init__(self, api_key_id: str, private_key_path: str):
        """
        Initialize authentication with API credentials.
        
        Args:
            api_key_id: Your Kalshi API key ID
            private_key_path: Path to your private key .pem file
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_path)
    
    def _load_private_key(self, key_path: str):
        """Load the RSA private key from PEM file."""
        path = Path(key_path)
        if not path.exists():
            raise FileNotFoundError(f"Private key not found at {key_path}")
        
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
    
    def create_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Create an RSA-PSS signature for a Kalshi API request.
        
        Args:
            timestamp: Current time in milliseconds (as string)
            method: HTTP method (GET, POST, etc.)
            path: API path WITHOUT query parameters
            
        Returns:
            Base64-encoded signature string
        """
        # Strip query parameters before signing (per Kalshi docs)
        path_without_query = path.split('?')[0]
        
        # Create message: timestamp + method + path
        message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Return base64 encoded
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, path: str) -> dict:
        """
        Generate authentication headers for a Kalshi API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            
        Returns:
            Dictionary of headers ready to use in requests
        """
        timestamp = str(int(datetime.datetime.now().timestamp() * 1000))
        signature = self.create_signature(timestamp, method, path)
        
        return {
            'KALSHI-ACCESS-KEY': self.api_key_id,
            'KALSHI-ACCESS-SIGNATURE': signature,
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
