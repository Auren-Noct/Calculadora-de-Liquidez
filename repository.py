import json
import os
from dataclasses import asdict
from typing import Literal, cast

from engine import MotorFinanciero
from models import MetaProrrateo, Transaccion

TipoCiclo = Literal["cerrado_mensual", "abierto_anual", "temporal"]
TipoMedio = Literal["fisico", "digital"]
TipoTx = Literal["INGRESO", "GASTO_CORRIENTE", "CUOTA_PRORRATEO", "PAGO_META"]


class RepositorioLocal:

    def __init__(self, filepath: str = "datos.json"):
        self.filepath = filepath

    def guardar(self, motor: MotorFinanciero) -> None:
        data = {
            "pct_ahorro": motor.pct_ahorro,
            "saldo_fisico": motor.saldo_fisico,
            "saldo_digital": motor.saldo_digital,
            "caja_ahorro_intocable": motor.caja_ahorro_intocable,
            "metas_prorrateo": {k: asdict(v) for k, v in motor.metas_prorrateo.items()},
            "historial": [asdict(t) for t in motor.historial],
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def cargar(self) -> MotorFinanciero:
        if not os.path.exists(self.filepath):
            return MotorFinanciero()

        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        motor = MotorFinanciero(pct_ahorro=data.get("pct_ahorro", 0.10))
        motor.saldo_fisico = data.get("saldo_fisico", 0.0)
        motor.saldo_digital = data.get("saldo_digital", 0.0)
        motor.caja_ahorro_intocable = data.get("caja_ahorro_intocable", 0.0)

        for meta_id, meta_data in data.get("metas_prorrateo", {}).items():
            meta_data["tipo_ciclo"] = cast(
                TipoCiclo, meta_data.get("tipo_ciclo", "abierto_anual")
            )
            motor.metas_prorrateo[meta_id] = MetaProrrateo(**meta_data)

        for tx_data in data.get("historial", []):
            tx_data["tipo"] = cast(TipoTx, tx_data.get("tipo"))
            tx_data["medio"] = cast(TipoMedio, tx_data.get("medio"))
            motor.historial.append(Transaccion(**tx_data))

        return motor
