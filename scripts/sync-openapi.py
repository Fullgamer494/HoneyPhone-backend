"""Refresh implemented P0 from FastAPI; retain explicitly planned P1 only."""
from pathlib import Path
import sys
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from honeyphone.main import app

path = ROOT / "contracts/openapi.yaml"
contract = yaml.safe_load(path.read_text())
generated = app.openapi()
planned_paths = {key: value for key, value in contract["paths"].items() if "/honeypot/" in key and key != "/api/v1/honeypot/sessions"}
planned_names = {"Source", "Error", "HoneypotSession", "HoneypotEvent", "EventBatch", "BatchResult", "SessionPage", "EventPage"}
planned_schemas = {key: value for key, value in contract["components"]["schemas"].items() if key in planned_names}
contract["info"] = {**generated["info"], "description": generated["info"].get("description", "") + " Rutas honeypot x-phase P1 son solo diseño, no están implementadas."}
contract["paths"] = {**generated["paths"], **planned_paths}
contract["components"]["schemas"] = {**planned_schemas, **generated["components"]["schemas"]}
path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True))
for route, value in generated["paths"].items():
    assert contract["paths"][route] == value
for name, value in generated["components"]["schemas"].items():
    assert contract["components"]["schemas"][name] == value
print("Contrato P0 sincronizado con FastAPI; P1 conserva etiqueta planificada.")
