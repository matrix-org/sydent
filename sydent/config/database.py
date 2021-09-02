import configparser

from sydent.config.server import BaseConfig


class DatabaseConfig(BaseConfig):
    def parse_legacy_config(self, cfg: configparser):
        self.database_path = self.sydent.cfg.get("db", "db.file")