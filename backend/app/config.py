from functools import lru_cache
from secrets import token_urlsafe
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BitcoinNetwork = Literal["regtest", "signet", "testnet", "mainnet"]
AppEnvironment = Literal["development", "production", "test"]


class Settings(BaseSettings):
    app_name: str = "BitScope"
    app_version: str = "0.1.0"
    app_environment: AppEnvironment = "development"
    api_prefix: str = "/api"
    bitcoin_rpc_host: str = "127.0.0.1"
    bitcoin_rpc_port: int = 18443
    bitcoin_rpc_user: str = "your_rpc_user"
    bitcoin_rpc_password: str = Field(default="your_rpc_password", repr=False)
    bitcoin_rpc_wallet: str = ""
    bitcoin_rpc_timeout_seconds: float = 10.0
    bitcoin_network: BitcoinNetwork = "regtest"
    bitcoin_zmq_rawblock: str = ""
    bitcoin_zmq_rawtx: str = ""
    backend_cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    backend_trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver", "backend", "frontend"]
    max_request_body_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    bitscope_local_access_token: str = Field(default_factory=lambda: token_urlsafe(32), repr=False)
    lab_session_database_path: str = "data/lab-sessions.sqlite3"
    scenario_artifact_root: str = "data/scenario-artifacts"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("backend_cors_origins", "backend_trusted_hosts", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def rpc_url(self) -> str:
        return f"http://{self.bitcoin_rpc_host}:{self.bitcoin_rpc_port}"

    def public_dict(self) -> dict[str, object]:
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "app_environment": self.app_environment,
            "api_prefix": self.api_prefix,
            "bitcoin_rpc_host": self.bitcoin_rpc_host,
            "bitcoin_rpc_port": self.bitcoin_rpc_port,
            "bitcoin_rpc_wallet_configured": bool(self.bitcoin_rpc_wallet),
            "bitcoin_rpc_timeout_seconds": self.bitcoin_rpc_timeout_seconds,
            "bitcoin_network": self.bitcoin_network,
            "bitcoin_zmq_rawblock_configured": bool(self.bitcoin_zmq_rawblock),
            "bitcoin_zmq_rawtx_configured": bool(self.bitcoin_zmq_rawtx),
            "backend_cors_origins": self.backend_cors_origins,
            "backend_trusted_hosts": self.backend_trusted_hosts,
            "max_request_body_bytes": self.max_request_body_bytes,
            "local_access_token_configured": bool(self.bitscope_local_access_token),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
