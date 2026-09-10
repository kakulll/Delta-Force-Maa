from importlib import import_module

RECO_MODULES = (
    "general",
    "price_evaluator",
)


def register_all() -> None:
    for module_name in RECO_MODULES:
        import_module(f"custom.reco.{module_name}")


__all__ = ["register_all"]
