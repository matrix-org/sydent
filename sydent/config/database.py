from configparser import ConfigParser

from sydent.config._base import BaseConfig


class DatabaseConfig(BaseConfig):
    def parse_config(self, cfg: ConfigParser):
        """
        Parse the database section of the config

        Args:
            cfg (ConfigParser): the configuration to be parsed
        """
        self.database_path = cfg.get("db", "db.file")
