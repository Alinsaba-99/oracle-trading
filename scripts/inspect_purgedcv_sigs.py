"""Print signatures and types of purgedcv API to verify our wrapper."""

from __future__ import annotations

import inspect

from purgedcv import CombinatorialPurgedCV, PurgedKFold
from purgedcv import deflated_sharpe_ratio as dsr
from purgedcv import probabilistic_sharpe_ratio as psr
from purgedcv import probability_of_backtest_overfitting as pbo


def main() -> None:
    print("deflated_sharpe_ratio:", inspect.signature(dsr))
    print("probabilistic_sharpe_ratio:", inspect.signature(psr))
    print("probability_of_backtest_overfitting:", inspect.signature(pbo))
    print()
    print("PBO return annotation:", inspect.signature(pbo).return_annotation)
    print("PBO module:", pbo.__module__)
    try:
        from purgedcv._pbo import PBOResult

        print(
            "PBOResult fields:",
            getattr(PBOResult, "__dataclass_fields__", getattr(PBOResult, "_fields", "?")),
        )
        print("PBOResult:", inspect.getsource(PBOResult)[:500])
    except Exception as e:
        print("PBOResult introspection failed:", e)
    print()
    print("CombinatorialPurgedCV.__init__:", inspect.signature(CombinatorialPurgedCV.__init__))
    print("CombinatorialPurgedCV.split:", inspect.signature(CombinatorialPurgedCV.split))
    print()
    print("PurgedKFold.__init__:", inspect.signature(PurgedKFold.__init__))
    print("PurgedKFold.split:", inspect.signature(PurgedKFold.split))


if __name__ == "__main__":
    main()
