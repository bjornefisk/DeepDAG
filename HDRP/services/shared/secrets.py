"""Secret management abstraction layer for HDRP.

Provides pluggable secret providers for retrieving sensitive configuration
values like API keys, DSNs, and database credentials.

Supported providers:
- Environment variables (default, for local development)
- AWS Secrets Manager (for production deployments)
- HashiCorp Vault (alternative production option)
"""

from abc import ABC, abstractmethod
from typing import Optional, Protocol


class SecretProvider(Protocol):
    """Protocol for secret retrieval providers."""
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret value by key.
        
        Args:
            key: Secret identifier (e.g., "google_api_key")
        
        Returns:
            Secret value if found, None otherwise
        """
        ...


class EnvironmentSecretProvider:
    """Retrieve secrets from environment variables.
    
    This is the default provider for local development and when
    no external secret manager is configured.
    """
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable.
        
        Args:
            key: Environment variable name
        
        Returns:
            Value from environment or None
        """
        import os
        return os.getenv(key)


class AWSSecretsManagerProvider:
    """Retrieve secrets from AWS Secrets Manager.
    
    Requires boto3 to be installed and AWS credentials configured.
    """
    
    def __init__(self, region: str = "us-west-2", prefix: str = "hdrp/"):
        """Initialize AWS Secrets Manager provider.
        
        Args:
            region: AWS region for Secrets Manager
            prefix: Prefix for secret names (e.g., "hdrp/production/")
        """
        self.region = region
        self.prefix = prefix
        self._client = None
    
    def _get_client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("secretsmanager", region_name=self.region)
            except ImportError:
                raise ImportError(
                    "boto3 is required for AWS Secrets Manager. "
                    "Install with: pip install boto3"
                )
        return self._client
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager.
        
        Args:
            key: Secret key (will be prefixed with self.prefix)
        
        Returns:
            Secret value or None if not found
        """
        secret_name = f"{self.prefix}{key}"
        
        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_name)
            
            # AWS Secrets Manager returns either SecretString or SecretBinary
            if "SecretString" in response:
                return response["SecretString"]
            else:
                # For binary secrets, decode as UTF-8
                import base64
                return base64.b64decode(response["SecretBinary"]).decode("utf-8")
        
        except Exception as e:
            # Log error but don't crash - fall back to environment variables
            import logging
            logging.warning(f"Failed to retrieve secret '{secret_name}' from AWS: {e}")
            return None


class VaultProvider:
    """Retrieve secrets from HashiCorp Vault.
    
    Requires hvac to be installed and VAULT_ADDR/VAULT_TOKEN configured.
    """
    
    def __init__(self, address: str = "http://localhost:8200", 
                 token: Optional[str] = None, mount_path: str = "secret/hdrp"):
        """Initialize Vault provider.
        
        Args:
            address: Vault server address
            token: Vault authentication token (or read from VAULT_TOKEN env var)
            mount_path: KV secrets engine mount path
        """
        self.address = address
        self.token = token
        self.mount_path = mount_path
        self._client = None
    
    def _get_client(self):
        """Lazy-load hvac client."""
        if self._client is None:
            try:
                import hvac
                import os
                
                vault_token = self.token or os.getenv("VAULT_TOKEN")
                if not vault_token:
                    raise ValueError("VAULT_TOKEN not configured")
                
                self._client = hvac.Client(url=self.address, token=vault_token)
                
                if not self._client.is_authenticated():
                    raise ValueError("Vault authentication failed")
                
            except ImportError:
                raise ImportError(
                    "hvac is required for HashiCorp Vault. "
                    "Install with: pip install hvac"
                )
        return self._client
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from Vault.
        
        Args:
            key: Secret key within mount_path
        
        Returns:
            Secret value or None if not found
        """
        try:
            client = self._get_client()
            
            # Read from KV v2 secrets engine
            secret_path = f"{self.mount_path}/{key}"
            response = client.secrets.kv.v2.read_secret_version(path=secret_path)
            
            # Extract value from response
            return response["data"]["data"].get("value")
        
        except Exception as e:
            # Log error but don't crash
            import logging
            logging.warning(f"Failed to retrieve secret '{key}' from Vault: {e}")
            return None


def get_secret_provider(provider_type: Optional[str] = None) -> SecretProvider:
    """Factory to create secret provider based on configuration.
    
    Args:
        provider_type: Type of provider ("environment", "aws_secrets_manager", "vault")
                      If None, reads from settings
    
    Returns:
        SecretProvider instance
    """
    if provider_type is None:
        from HDRP.services.shared.settings import get_settings
        settings = get_settings()
        provider_type = settings.secrets.provider
    
    if provider_type == "aws_secrets_manager":
        from HDRP.services.shared.settings import get_settings
        settings = get_settings()
        return AWSSecretsManagerProvider(
            region=settings.secrets.aws.region,
            prefix=settings.secrets.aws.secret_name_prefix
        )
    
    elif provider_type == "vault":
        from HDRP.services.shared.settings import get_settings
        settings = get_settings()
        
        token = None
        if settings.secrets.vault.token:
            token = settings.secrets.vault.token.get_secret_value()
        
        return VaultProvider(
            address=settings.secrets.vault.address,
            token=token,
            mount_path=settings.secrets.vault.mount_path
        )
    
    else:
        # Default to environment variables
        return EnvironmentSecretProvider()
