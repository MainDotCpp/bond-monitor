import tomli
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.toml')

class Config:
    def __init__(self):
        self.enable_sync = True
        try:
            with open(CONFIG_PATH, 'rb') as f:
                data = tomli.load(f)
                self.enable_sync = bool(data.get('enableSync', False))
        except Exception:
            self.enable_sync = True  # 默认开启

config = Config() 