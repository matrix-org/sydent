from configparser import ConfigParser

from sydent.config._base import BaseConfig


class DatabaseConfig(BaseConfig):
    def parse_config(self, cfg: ConfigParser):
        self.database_path = cfg.get("db", "db.file")
