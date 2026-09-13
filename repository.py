import json
from pathlib import Path
from typing import Any

from engine import MotorFinanciero
from models import MetaProrrateo, Transaccion


class RepositorioFinanciero:

    def __init__(self, ruta_archivo: str = "estado_financiero.json") -> None:
        self.ruta_archivo = Path(ruta_archivo)

    def guardar(self, motor: MotorFinanciero) -> None:
        datos: dict[str, Any] = {
            "saldo_fisico": motor.saldo_fisico,
            "saldo_digital": motor.saldo_digital,
            "caja_ahorro_intocable": motor.caja_ahorro_intocable,
            "pct_ahorro": motor.pct_ahorro,
            "metas_prorrateo": [
                meta.__dict__ for meta in motor.metas_prorrateo.values()
            ],
            "historial": [tx.__dict__ for tx in motor.historial],
        }
        with open(self.ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

    def cargar(self) -> MotorFinanciero:
        if not self.ruta_archivo.exists():
            return MotorFinanciero()

        try:
            with open(self.ruta_archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)

            motor = MotorFinanciero(pct_ahorro=datos.get("pct_ahorro", 0.10))
            motor.saldo_fisico = float(datos.get("saldo_fisico", 0.0))
            motor.saldo_digital = float(datos.get("saldo_digital", 0.0))
            motor.caja_ahorro_intocable = float(datos.get("caja_ahorro_intocable", 0.0))

            for meta_dict in datos.get("metas_prorrateo", []):
                meta = MetaProrrateo(**meta_dict)
                motor.metas_prorrateo[meta.id] = meta

            for tx_dict in datos.get("historial", []):
                tx = Transaccion(**tx_dict)
                motor.historial.append(tx)

            return motor
        except (json.JSONDecodeError, KeyError, TypeError):
            return MotorFinanciero()
