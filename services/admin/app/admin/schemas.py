from pydantic import BaseModel, ConfigDict


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminResponse(BaseModel):
    id: int
    email: str

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdateRequest(BaseModel):
    chat_id: int
    initial_balance: int | None = None
    target_balance: int | None = None
    bet_amount: int | None = None


class SettingsResponse(BaseModel):
    chat_id: int
    initial_balance: int
    target_balance: int
    bet_amount: int

    model_config = ConfigDict(from_attributes=True)


class GameStatsResponse(BaseModel):
    total_games: int
    finished_games: int
    active_games: int


class PlayerStatsItem(BaseModel):
    vk_id: int
    name: str
    games_played: int
    total_wins: int
