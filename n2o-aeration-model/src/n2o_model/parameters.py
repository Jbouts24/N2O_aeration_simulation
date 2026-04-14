"""Dataclasses that hold model configuration and parameter values."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SimulationSettings:
    duration_days: float = 3.0
    points_per_day: int = 240


@dataclass
class ReactorSettings:
    volume_m3: float = 2000.0
    hrt_days: float = 0.50
    srt_days: float = 12.0
    temperature_c: float = 20.0
    pH: float = 7.5


@dataclass
class InfluentSettings:
    nh4_mgN_L: float = 22.0
    no2_mgN_L: float = 0.1
    no3_mgN_L: float = 1.0
    cod_mgCOD_L: float = 65.0
    do_mgO2_L: float = 0.0


@dataclass
class InitialConditions:
    nh4_mgN_L: float = 16.0
    no2_mgN_L: float = 0.3
    no3_mgN_L: float = 3.0
    n2o_mgN_L: float = 0.02
    cod_mgCOD_L: float = 45.0
    do_mgO2_L: float = 1.2


@dataclass
class BiomassInitialSettings:
    aob_mgCOD_L: float = 120.0
    nob_mgCOD_L: float = 85.0
    het_mgCOD_L: float = 180.0


@dataclass
class ControllerSettings:
    type: str = "fixed"
    target_do_mg_L: float = 1.5
    kp: float = 18.0
    min_kla_per_day: float = 1.0
    max_kla_per_day: float = 90.0
    nh4_low_mgN_L: float = 2.0
    nh4_high_mgN_L: float = 8.0
    target_do_low_mg_L: float = 0.8
    target_do_mid_mg_L: float = 1.5
    target_do_high_mg_L: float = 2.5


@dataclass
class KineticSettings:
    q_aob_max_per_day: float = 0.16
    q_nob_max_per_day: float = 0.11
    q_den_max_per_day: float = 0.12
    b_aob_per_day: float = 0.03
    b_nob_per_day: float = 0.025
    b_het_per_day: float = 0.03
    y_aob_mgCOD_per_mgN: float = 0.15
    y_nob_mgCOD_per_mgN: float = 0.04
    y_het_mgCOD_per_mgN: float = 0.08
    k_nh4_mgN_L: float = 1.0
    k_no2_nob_mgN_L: float = 0.4
    k_no2_den_mgN_L: float = 0.3
    k_no3_den_mgN_L: float = 0.5
    k_cod_mgCOD_L: float = 20.0
    k_o2_aob_mg_L: float = 0.30
    k_o2_nob_mg_L: float = 0.80
    k_o2_het_mg_L: float = 0.20
    k_o2_nd_mg_L: float = 0.25
    k_do_hao_mg_L: float = 0.50
    k_no2_nd_mgN_L: float = 0.50
    k_n2o_mgN_L: float = 0.03
    nd_yield: float = 0.055
    hao_yield: float = 0.006
    den_n2o_yield_base: float = 0.020
    k_cod_incomplete_mgCOD_L: float = 15.0
    k_cod_n2o_red_mgCOD_L: float = 10.0
    k_red_per_day: float = 0.09
    theta_nitrification: float = 1.072
    theta_denitrification: float = 1.060
    theta_reduction: float = 1.040
    oxygen_per_nh4: float = 4.57
    oxygen_per_no2: float = 1.14
    cod_per_den_n: float = 2.86
    cod_per_n2o_red: float = 1.50


@dataclass
class AerationSettings:
    do_sat_mg_L: float = 8.0
    n2o_kla_factor: float = 0.80
    energy_per_kla: float = 1.0


@dataclass
class OptimizationSettings:
    enabled: bool = False
    setpoint_candidates_mg_L: list[float] = field(default_factory=lambda: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    w_emission: float = 1.0
    w_energy: float = 0.05
    w_effluent_nh4: float = 5.0


@dataclass
class ModelConfig:
    mode: str = "baseline"
    scenario_name: str = "base_case"
    output_dir: str = "results/base_case"
    simulation: SimulationSettings = field(default_factory=SimulationSettings)
    reactor: ReactorSettings = field(default_factory=ReactorSettings)
    influent: InfluentSettings = field(default_factory=InfluentSettings)
    initial_conditions: InitialConditions = field(default_factory=InitialConditions)
    biomass_initial: BiomassInitialSettings = field(default_factory=BiomassInitialSettings)
    controller: ControllerSettings = field(default_factory=ControllerSettings)
    kinetics: KineticSettings = field(default_factory=KineticSettings)
    aeration: AerationSettings = field(default_factory=AerationSettings)
    optimization: OptimizationSettings = field(default_factory=OptimizationSettings)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        return cls(
            mode=data.get("mode", "baseline"),
            scenario_name=data.get("scenario_name", "base_case"),
            output_dir=data.get("output_dir", "results/base_case"),
            simulation=SimulationSettings(**data.get("simulation", {})),
            reactor=ReactorSettings(**data.get("reactor", {})),
            influent=InfluentSettings(**data.get("influent", {})),
            initial_conditions=InitialConditions(**data.get("initial_conditions", {})),
            biomass_initial=BiomassInitialSettings(**data.get("biomass_initial", {})),
            controller=ControllerSettings(**data.get("controller", {})),
            kinetics=KineticSettings(**data.get("kinetics", {})),
            aeration=AerationSettings(**data.get("aeration", {})),
            optimization=OptimizationSettings(**data.get("optimization", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_updates(self, updates: dict[str, Any]) -> "ModelConfig":
        from .utils import deep_merge
        return ModelConfig.from_dict(deep_merge(self.to_dict(), updates))

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)
