"""Edge runner and ablation dispatcher for NEO-WILDER V4.

Manages active vs shadow edge execution and enforces strict isolation.
"""

import logging
from typing import Dict, List, Optional

from neo_wilder.domain.enums import EdgeStatus
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext
from neo_wilder.edges.e01_sweep_reclaim import E01SweepReclaim
from neo_wilder.edges.e03_sweep_depth import E03SweepDepth
from neo_wilder.edges.e04_liquidity_pools import E04LiquidityPools
from neo_wilder.edges.e05_structure import E05Structure
from neo_wilder.edges.e07_volume_profile import E07VolumeProfile
from neo_wilder.edges.e11_atr_volatility import E11ATRVolatility
from neo_wilder.edges.e12_dynamic_sl_buffer import E12DynamicSLBuffer
from neo_wilder.edges.e13_liq_burst import E13LiqBurst
from neo_wilder.edges.e15_cvd_turn import E15CVDTurn
from neo_wilder.edges.e16_obi import E16OBI
from neo_wilder.edges.e17_absorption import E17Absorption
from neo_wilder.edges.e21_oi_exhaustion import E21OIExhaustion
from neo_wilder.edges.e23_funding_context import E23FundingContext
from neo_wilder.edges.e24_mark_index_div import E24MarkIndexDiv
from neo_wilder.edges.e28_expiry_engine import E28ExpiryEngine
from neo_wilder.edges.new_edges import (
    X01BTCConflict,
    X02RelativeVolume,
    X03CoinDCXGate,
    X04LateEntry,
)
from neo_wilder.edges.registry import EdgeRegistry

logger = logging.getLogger(__name__)


class EdgeRunner:
    """Executes registered edges with ablation toggle support."""

    def __init__(self, registry: EdgeRegistry, edge_config: Optional[Dict[str, bool]] = None):
        self.registry = registry
        self.edge_config = edge_config or {}

        # Instantiate all implemented edge instances
        self._all_edge_instances: Dict[str, BaseEdge] = {
            "E01": E01SweepReclaim(),
            "E03": E03SweepDepth(),
            "E04": E04LiquidityPools(),
            "E05": E05Structure(),
            "E07": E07VolumeProfile(),
            "E11": E11ATRVolatility(),
            "E12": E12DynamicSLBuffer(),
            "E13": E13LiqBurst(),
            "E15": E15CVDTurn(),
            "E16": E16OBI(),
            "E17": E17Absorption(),
            "E21": E21OIExhaustion(),
            "E23": E23FundingContext(),
            "E24": E24MarkIndexDiv(),
            "E28": E28ExpiryEngine(),
            "X01": X01BTCConflict(),
            "X02": X02RelativeVolume(),
            "X03": X03CoinDCXGate(),
            "X04": X04LateEntry(),
        }

    def evaluate_all(self, ctx: FeatureContext) -> Dict[str, EdgeResult]:
        """Evaluate all active and shadow edges safely.

        Catches internal exceptions and returns abstain fail-closed.
        """
        results: Dict[str, EdgeResult] = {}

        for edge_id, edge in self._all_edge_instances.items():
            meta = self.registry.get(edge_id)

            # Check ablation flag if defined in config
            cfg_key = f"{edge_id.lower()}_{meta.name.lower().replace(' ', '_')}"
            is_enabled = self.edge_config.get(
                cfg_key, meta.status in (EdgeStatus.ACTIVE, EdgeStatus.SHADOW)
            )

            if not is_enabled:
                results[edge_id] = EdgeResult.abstain(edge_id)
                continue

            try:
                res = edge.evaluate(ctx)
                results[edge_id] = res
            except Exception as e:
                logger.error(f"Error evaluating edge {edge_id}: {e}", exc_info=True)
                results[edge_id] = EdgeResult.abstain(edge_id)

        return results

    def filter_active_confirmations(self, results: Dict[str, EdgeResult]) -> List[str]:
        """Return list of passed confirming edge IDs."""
        passed = []
        for edge_id, res in results.items():
            meta = self.registry.get(edge_id)
            if meta.status == EdgeStatus.ACTIVE and res.passed:
                passed.append(edge_id)
        return passed
