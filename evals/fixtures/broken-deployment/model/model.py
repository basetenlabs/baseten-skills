class Model:
    def load(self):
        pass

    def predict(self, model_input: dict) -> dict:
        return {"echo": model_input}
