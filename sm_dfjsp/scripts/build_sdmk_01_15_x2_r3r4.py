from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

from smdfjsp.data.dataset_builder import DatasetSpec, convert_mk_to_sdmk, load_dataset_spec
from smdfjsp.data.io import save_instance_json
from smdfjsp.data.mk_parser import parse_mk_file


def _choose_r_total(num_jobs: int) -> int:
    """
    SDMK01-15 scale rule for this regeneration:
    - smaller instances (<=15 jobs): R=3
    - larger instances (>=20 jobs): R=4
    """
    return 3 if num_jobs <= 15 else 4


def _split_r_by_type(r_total: int, instance_idx: int) -> list[int]:
    """
    Split total SRU count R into two type-wise counts [R1, R2], with both types covered.
    """
    if r_total == 3:
        # Alternate [2,1] / [1,2] across instances to avoid fixed type bias.
        return [2, 1] if (instance_idx % 2 == 1) else [1, 2]
    if r_total == 4:
        return [2, 2]
    raise ValueError(f"Unsupported R total: {r_total}")


def _build_spec(base: DatasetSpec, sru_per_type: list[int]) -> DatasetSpec:
    return replace(base, num_types=2, sru_per_type=sru_per_type)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    mk_dir = root / "data"
    spec_path = root / "configs" / "dataset_spec.yaml"
    out_dir = root / "data" / "sdmk01-15_x2_r3r4"
    manifest_path = out_dir / "manifest.csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_spec = load_dataset_spec(spec_path)
    mk_files = sorted(mk_dir.glob("mk*.txt"))

    rows: list[dict[str, object]] = []
    for idx, mk_file in enumerate(mk_files, start=1):
        mk = parse_mk_file(mk_file)
        r_total = _choose_r_total(len(mk.jobs))
        r_by_type = _split_r_by_type(r_total, idx)

        spec = _build_spec(base_spec, sru_per_type=r_by_type)
        inst = convert_mk_to_sdmk(mk, spec, seed_offset=idx - 1)

        # Enrich metadata for traceability.
        inst.metadata["scale_rule"] = "X=2 fixed; R=3 if jobs<=15 else R=4"
        inst.metadata["x_total"] = 2
        inst.metadata["r_total"] = r_total
        inst.metadata["r_by_type"] = r_by_type
        inst.metadata["logic_constraint"] = "0<=X<=min(N,R)"

        out_file = out_dir / f"{inst.name}.json"
        save_instance_json(inst, out_file)

        total_ops = sum(len(j.operations) for j in inst.jobs)
        total_options = sum(len(op.options) for j in inst.jobs for op in j.operations)
        rows.append(
            {
                "instance": inst.name,
                "source_mk": mk.name,
                "jobs": len(inst.jobs),
                "types_x": 2,
                "r_total": r_total,
                "r_type_1": r_by_type[0],
                "r_type_2": r_by_type[1],
                "srus": len(inst.srus),
                "ops": total_ops,
                "options": total_options,
                "seed": inst.metadata.get("seed", ""),
                "file": out_file.relative_to(root).as_posix(),
            }
        )
        print(
            f"{inst.name}: jobs={len(inst.jobs)} X=2 R={r_total} "
            f"(R1={r_by_type[0]}, R2={r_by_type[1]}) -> {out_file.as_posix()}"
        )

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "instance",
                "source_mk",
                "jobs",
                "types_x",
                "r_total",
                "r_type_1",
                "r_type_2",
                "srus",
                "ops",
                "options",
                "seed",
                "file",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"saved: {manifest_path.as_posix()}")


if __name__ == "__main__":
    main()

