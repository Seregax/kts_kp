from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class VkConfig:
    token: str
    group_id: int


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
    vk: VkConfig
    rabbit: RabbitConfig


def setup_config(config_path: str) -> Config:
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return Config(
        vk=VkConfig(
            token=raw["vk"]["token"],
            group_id=raw["vk"]["group_id"],
        ),
        rabbit=RabbitConfig(
            host=raw["rabbit"]["host"],
            port=raw["rabbit"]["port"],
            user=raw["rabbit"]["user"],
            password=raw["rabbit"]["password"],
        ),
    )
