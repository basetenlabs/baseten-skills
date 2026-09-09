class Model:
    def __init__(self, config):
        self._divisor = config["model_metadata"]["divisor"]

    def load(self):
        pass

    def predict(self, model_input: dict) -> dict:
        if self._divisor <= 0:
            raise ValueError("model_metadata.divisor must be positive; update the deployment config")
        return {"result": model_input.get("value", 1) / self._divisor}
