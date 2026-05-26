"""Shared minimal Model used by most eval fixtures.

Does no real ML — just echoes input. Cheap to deploy, cold-start fast.
Copied (not symlinked) into each fixture's model/ dir so each fixture is
a self-contained Truss.
"""


class Model:
    def load(self):
        pass

    def predict(self, model_input: dict) -> dict:
        return {"echo": model_input}
