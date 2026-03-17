from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass
class AdminConfig:
    email: str
    password: str


@dataclass
class SessionConfig:
    key: str


@dataclass
class Config:
    database: DatabaseConfig
    admin: AdminConfig
    session: SessionConfig
    host: str
    port: int


def setup_config(config_path: str) -> Config:
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return Config(
        database=DatabaseConfig(
            host=raw["database"]["host"],
            port=raw["database"]["port"],
            user=raw["database"]["user"],
            password=raw["database"]["password"],
            database=raw["database"]["database"],
        ),
        admin=AdminConfig(
            email=raw["admin"]["email"],
            password=raw["admin"]["password"],
        ),
        session=SessionConfig(key=raw["session"]["key"]),
        host=raw.get("host", "0.0.0.0"),
        port=raw.get("port", 8080),
    )
