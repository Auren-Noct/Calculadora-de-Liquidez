import json
import os
from dataclasses import asdict, fields
from datetime import datetime, timezone
from typing import cast

from engine import MotorFinanciero
from models import MetaProrrateo, TipoMedio, TipoMeta, TipoTx, Transaccion


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

        campos_meta = {f.name for f in fields(MetaProrrateo)}
        campos_tx = {f.name for f in fields(Transaccion)}
        hoy_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for meta_id, meta_data in data.get("metas_prorrateo", {}).items():
            if "tipo_ciclo" in meta_data and "tipo_meta" not in meta_data:
                meta_data["tipo_meta"] = (
                    "recurrente"
                    if meta_data.get("tipo_ciclo") != "temporal"
                    else "puntual"
                )

            if "fecha_limite" not in meta_data:
                meta_data["fecha_limite"] = meta_data.get("fecha", hoy_str)

            meta_data["tipo_meta"] = cast(
                TipoMeta, meta_data.get("tipo_meta", "puntual")
            )

            meta_limpia = {k: v for k, v in meta_data.items() if k in campos_meta}
            motor.metas_prorrateo[meta_id] = MetaProrrateo(**meta_limpia)

        for tx_data in data.get("historial", []):
            tx_data["tipo"] = cast(TipoTx, tx_data.get("tipo"))
            tx_data["medio"] = cast(TipoMedio, tx_data.get("medio"))

            tx_limpia = {k: v for k, v in tx_data.items() if k in campos_tx}
            motor.historial.append(Transaccion(**tx_limpia))

        return motor
