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
class RabbitConfig:
    host: str
    port: int
    user: str
    password: str

    @property
    def dsn(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"


@dataclass
class Config:
    database: DatabaseConfig
    rabbit: RabbitConfig


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
        rabbit=RabbitConfig(
            host=raw["rabbit"]["host"],
            port=raw["rabbit"]["port"],
            user=raw["rabbit"]["user"],
            password=raw["rabbit"]["password"],
        ),
    )
