import json, time, os, pathlib

class JsonLogger:
    def __init__(self, path: str = "logs/bot.jsonl"):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def log(self, level: str, msg: str, **kv):
        rec = {"ts": time.time(), "level": level, "msg": msg}
        rec.update(kv)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
