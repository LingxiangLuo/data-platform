from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:changeme@localhost:3306/portal_db"
    SECRET_KEY: str = "changeme-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    COOKIE_SECURE: bool = False  # 生产环境设为 True（HTTPS）
    DS_API_URL: str = "http://dolphinscheduler:12345/dolphinscheduler"
    DS_ADMIN_USER: str = "admin"
    DS_ADMIN_PASSWORD: str = "changeme"
    OM_API_URL: str = "http://localhost:8585"

    class Config:
        env_file = ".env"


settings = Settings()
